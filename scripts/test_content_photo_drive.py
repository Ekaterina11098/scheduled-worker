import hashlib
import unittest
import content_photo_drive as m

RID = '4d1ac7af-f839-49c3-bf5f-09607018d844'
FID = 'testGoogleFile1234'
RAW = b'bounded archive fixture'


class Response:
    def __init__(self, status=200, value=None, headers=None, raw=b''):
        self.status_code=status; self.value=value; self.headers=headers or {}; self.raw=raw
    def json(self): return self.value
    def iter_content(self, size): yield self.raw
    def close(self): pass


def credentials(**updates):
    return dict(folder_id=m.FOLDER, scope=m.SCOPE, client_id='test-client',
                client_secret='test-secret', refresh_token='test-refresh', **updates)


class Transport:
    def __init__(self):
        self.calls=[]; self.existing=[]; self.corrupt=False; self.writable=True
        self.foreign_parent=False; self.foreign_session=False; self.refresh_status=200
    def __call__(self, method, url, **kw):
        self.calls.append((method,url,kw))
        assert kw['allow_redirects'] is False
        if url=='https://oauth2.googleapis.com/token':
            return Response(self.refresh_status,{'access_token':'fixture-access','token_type':'Bearer','scope':m.SCOPE})
        assert kw['headers']['Authorization']=='Bearer fixture-access'
        if url==m.API+'/'+m.FOLDER:
            return Response(value={'id':m.FOLDER,'mimeType':'application/vnd.google-apps.folder',
                                   'capabilities':{'canAddChildren':self.writable}})
        if method=='GET' and url==m.API:
            return Response(value={'files':self.existing})
        if method=='POST':
            return Response(headers={'Location':('https://evil.invalid/' if self.foreign_session else
                'https://www.googleapis.com/upload/drive/v3/files?upload_id=fixture')})
        if method=='PUT': return Response(value={'id':FID})
        if kw.get('params',{}).get('alt')=='media':
            return Response(raw=b'corrupt' if self.corrupt else RAW)
        if url==m.API+'/'+FID:
            return Response(value={'id':FID,'parents':['foreign'] if self.foreign_parent else [m.FOLDER],
                'mimeType':'application/zip','size':len(RAW),'md5Checksum':hashlib.md5(RAW).hexdigest(),
                'appProperties':{'photo_request':RID,'photo_bridge':'v1'}})
        raise AssertionError('Unexpected endpoint')


class Tests(unittest.TestCase):
    def test_fresh_archive_private_fixed_parent_and_verified_bytes(self):
        t=Transport(); r=m.Delivery(credentials(),t).upload(RID,RAW)
        self.assertEqual(r['file_id'],FID); self.assertTrue(r['server_verified'])
        create=next(c for c in t.calls if c[0]=='POST' and 'upload/drive' in c[1])
        self.assertEqual(create[2]['json']['parents'],[m.FOLDER])
        self.assertNotIn('permissions',create[2]['json'])
        self.assertEqual(r['sha256'],hashlib.sha256(RAW).hexdigest())
    def test_existing_archive_reused_without_new_post(self):
        t=Transport(); t.existing=[{'id':FID}]
        m.Delivery(credentials(),t).upload(RID,RAW)
        self.assertFalse(any(c[0]=='POST' and 'upload/drive' in c[1] for c in t.calls))
    def test_two_existing_archives_stop_before_write(self):
        t=Transport(); t.existing=[{'id':FID},{'id':'otherFile1234'}]
        with self.assertRaisesRegex(m.DriveError,'duplicate_archive_conflict'):
            m.Delivery(credentials(),t).upload(RID,RAW)
        self.assertFalse(any(c[0]=='PUT' for c in t.calls))
    def test_folder_cannot_be_changed_by_configuration(self):
        c=credentials(); c['folder_id']='another-folder'
        with self.assertRaisesRegex(m.DriveError,'folder_mismatch'):m.Delivery(c,Transport())
    def test_broad_drive_scope_is_rejected(self):
        c=credentials(); c['scope']='https://www.googleapis.com/auth/drive'
        with self.assertRaisesRegex(m.DriveError,'scope_mismatch'):m.Delivery(c,Transport())
    def test_extra_google_scopes_are_rejected(self):
        c=credentials(); c['scope']+=' openid'
        with self.assertRaisesRegex(m.DriveError,'scope_mismatch'):m.Delivery(c,Transport())
    def test_missing_refresh_token_stops(self):
        c=credentials(); c['refresh_token']=''
        with self.assertRaisesRegex(m.DriveError,'authorization_missing'):m.Delivery(c,Transport())
    def test_refresh_denial_stops_before_drive_access(self):
        t=Transport(); t.refresh_status=400
        with self.assertRaisesRegex(m.DriveError,'refresh_failed'):m.Delivery(credentials(),t).upload(RID,RAW)
        self.assertEqual(len(t.calls),1)
    def test_folder_permission_required(self):
        t=Transport(); t.writable=False
        with self.assertRaisesRegex(m.DriveError,'not_writable'):m.Delivery(credentials(),t).upload(RID,RAW)
        self.assertFalse(any(c[0]=='PUT' for c in t.calls))
    def test_resumable_session_cannot_redirect_token(self):
        t=Transport(); t.foreign_session=True
        with self.assertRaisesRegex(m.DriveError,'session_rejected'):m.Delivery(credentials(),t).upload(RID,RAW)
        self.assertFalse(any(c[0]=='PUT' for c in t.calls))
    def test_metadata_parent_mismatch_stops(self):
        t=Transport(); t.foreign_parent=True
        with self.assertRaisesRegex(m.DriveError,'readback_mismatch'):m.Delivery(credentials(),t).upload(RID,RAW)
    def test_actual_download_corruption_stops(self):
        t=Transport(); t.corrupt=True
        with self.assertRaisesRegex(m.DriveError,'hash_mismatch'):m.Delivery(credentials(),t).upload(RID,RAW)
    def test_invalid_request_before_network(self):
        t=Transport()
        with self.assertRaises(ValueError):m.Delivery(credentials(),t).upload('not-an-id',RAW)
        self.assertEqual(t.calls,[])
    def test_empty_archive_before_network(self):
        t=Transport()
        with self.assertRaisesRegex(m.DriveError,'size_limit'):m.Delivery(credentials(),t).upload(RID,b'')
        self.assertEqual(t.calls,[])


if __name__=='__main__': unittest.main()
