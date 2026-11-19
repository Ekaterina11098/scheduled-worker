"""Private photo archive delivery to one owner-approved Google Drive folder.

No connector-token extraction, public sharing, WB writes or arbitrary destinations.
The caller supplies an HTTP transport and a dedicated offline Google authorization.
"""
import hashlib
import re
import time
import uuid

FOLDER = '1zw7vwx-Qj5Zi_AcIzX0v9L3DxwgMBUr1'
SCOPE = 'https://www.googleapis.com/auth/drive.file'
API = 'https://www.googleapis.com/drive/v3/files'
MAX_BYTES = 102 * 1024 * 1024


class DriveError(Exception):
    pass


def file_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{10,150}', value):
        raise DriveError('invalid_drive_file_identity')
    return value


class Delivery:
    def __init__(self, credentials, transport):
        if credentials.get('folder_id') != FOLDER:
            raise DriveError('drive_folder_mismatch')
        if set(str(credentials.get('scope', '')).split()) != {SCOPE}:
            raise DriveError('drive_scope_mismatch')
        if not all(isinstance(credentials.get(k), str) and credentials[k] for k in
                   ('client_id', 'client_secret', 'refresh_token')):
            raise DriveError('drive_authorization_missing')
        self.credentials = credentials
        self.transport = transport
        self.token = None

    def refresh(self):
        r = self.transport('POST', 'https://oauth2.googleapis.com/token', data={
            'grant_type': 'refresh_token', 'client_id': self.credentials['client_id'],
            'client_secret': self.credentials['client_secret'],
            'refresh_token': self.credentials['refresh_token'],
        }, timeout=(20, 60), allow_redirects=False)
        if r.status_code != 200:
            raise DriveError('drive_authorization_refresh_failed')
        b = r.json()
        if 'scope' in b and set(b['scope'].split()) != {SCOPE}:
            raise DriveError('drive_scope_mismatch')
        if not b.get('access_token') or b.get('token_type', '').lower() != 'bearer':
            raise DriveError('drive_access_token_invalid')
        self.token = b['access_token']

    def call(self, method, url, **kwargs):
        # Access tokens must never follow a redirect or reach a non-Google endpoint.
        if not url.startswith('https://www.googleapis.com/'):
            raise DriveError('drive_endpoint_rejected')
        r = self.transport(method, url, headers={
            **kwargs.pop('headers', {}), 'Authorization': 'Bearer ' + self.token,
        }, timeout=(20, 90), allow_redirects=False, **kwargs)
        if 300 <= r.status_code < 400 and r.status_code != 308:
            raise DriveError('drive_redirect_rejected')
        return r

    def metadata(self, ident):
        ident = file_id(ident)
        r = self.call('GET', API + '/' + ident, params={
            'fields': 'id,mimeType,parents,size,md5Checksum,trashed,appProperties,capabilities(canAddChildren)',
        })
        if r.status_code != 200:
            raise DriveError('drive_metadata_unavailable')
        return r.json()

    def verify_file(self, ident, request_id, raw):
        b = self.metadata(ident)
        if (b.get('id') != ident or b.get('parents') != [FOLDER] or b.get('trashed')
                or b.get('mimeType') != 'application/zip'
                or b.get('appProperties', {}).get('photo_request') != request_id
                or b.get('appProperties', {}).get('photo_bridge') != 'v1'
                or int(b.get('size', -1)) != len(raw)
                or b.get('md5Checksum') != hashlib.md5(raw).hexdigest()):
            raise DriveError('drive_file_readback_mismatch')
        r = self.call('GET', API + '/' + file_id(ident), params={'alt': 'media'}, stream=True)
        if r.status_code != 200:
            raise DriveError('drive_download_failed')
        digest = hashlib.sha256(); size = 0
        try:
            for chunk in r.iter_content(65536):
                size += len(chunk)
                if size > len(raw):
                    raise DriveError('drive_download_size_mismatch')
                digest.update(chunk)
        finally:
            r.close()
        if size != len(raw) or digest.hexdigest() != hashlib.sha256(raw).hexdigest():
            raise DriveError('drive_download_hash_mismatch')
        return {'file_id': ident, 'url': 'https://drive.google.com/file/d/' + ident + '/view',
                'folder_id': FOLDER, 'bytes': size, 'sha256': digest.hexdigest(),
                'transport': 'google_drive_connector', 'server_verified': True}

    def upload(self, request_id, raw):
        if str(uuid.UUID(request_id)) != request_id:
            raise DriveError('invalid_photo_request_identity')
        if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
            raise DriveError('drive_archive_size_limit')
        self.refresh()
        folder = self.metadata(FOLDER)
        if (folder.get('id') != FOLDER or folder.get('mimeType') != 'application/vnd.google-apps.folder'
                or folder.get('trashed') or not folder.get('capabilities', {}).get('canAddChildren')):
            raise DriveError('drive_folder_not_writable')
        # Recover a completed previous upload instead of creating a duplicate.
        q = ("'" + FOLDER + "' in parents and trashed=false and "
             "appProperties has { key='photo_request' and value='" + request_id + "' }")
        found = self.call('GET', API, params={'q': q, 'fields': 'files(id)', 'pageSize': 2})
        if found.status_code != 200:
            raise DriveError('drive_duplicate_check_failed')
        files = found.json().get('files', [])
        if len(files) > 1:
            raise DriveError('drive_duplicate_archive_conflict')
        if files:
            return self.verify_file(file_id(files[0]['id']), request_id, raw)
        started = self.call('POST', 'https://www.googleapis.com/upload/drive/v3/files',
            params={'uploadType': 'resumable', 'fields': 'id'},
            headers={'X-Upload-Content-Type': 'application/zip', 'X-Upload-Content-Length': str(len(raw))},
            json={'name': 'WB-China-sources-' + request_id + '.zip', 'parents': [FOLDER],
                  'mimeType': 'application/zip', 'appProperties': {
                      'photo_bridge': 'v1', 'photo_request': request_id,
                      'sha256': hashlib.sha256(raw).hexdigest()}})
        if started.status_code != 200:
            raise DriveError('drive_upload_start_failed')
        session = started.headers.get('Location', '')
        if not session.startswith('https://www.googleapis.com/upload/drive/v3/files?'):
            raise DriveError('drive_upload_session_rejected')
        offset = 0; deadline = time.monotonic() + 900
        while offset < len(raw):
            if time.monotonic() >= deadline:
                raise DriveError('drive_upload_deadline')
            end = min(offset + 8 * 1024 * 1024, len(raw))
            for attempt in range(3):
                try:
                    r = self.call('PUT', session, data=raw[offset:end], headers={
                        'Content-Type': 'application/zip',
                        'Content-Range': 'bytes %d-%d/%d' % (offset, end - 1, len(raw))})
                    if r.status_code in (429,500,502,503,504):
                        raise ConnectionError('drive_upload_transient')
                    break
                except (TimeoutError, ConnectionError):
                    if attempt==2:raise DriveError('drive_upload_transport_failed') from None
                    time.sleep(attempt+1)
                    r = self.call('PUT', session, data=b'', headers={'Content-Range': 'bytes */' + str(len(raw))})
                    if r.status_code in (200,201):break
                    if r.status_code!=308:raise DriveError('drive_upload_resume_failed')
                    match=re.fullmatch(r'bytes=0-(\d+)',r.headers.get('Range',''))
                    received=int(match.group(1))+1 if match else 0
                    if received>offset:break
            if r.status_code in (200, 201):
                return self.verify_file(file_id(r.json()['id']), request_id, raw)
            if r.status_code != 308:
                raise DriveError('drive_upload_failed')
            match = re.fullmatch(r'bytes=0-(\d+)', r.headers.get('Range', ''))
            next_offset = int(match.group(1)) + 1 if match else 0
            if not offset < next_offset <= end:
                raise DriveError('drive_upload_progress_invalid')
            offset = next_offset
        raise DriveError('drive_upload_completion_missing')
