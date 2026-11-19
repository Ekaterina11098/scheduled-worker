import io
import json
import unittest
import zipfile
from PIL import Image
import content_photo_bridge as m

def card(article='57-NoelBag-red',nm=123):
    return {'vendorCode':article,'nmID':nm,'photos':[{'big':'https://basket-47.wbbasket.ru/vol14732/part1473243/1473243823/images/big/1.webp'}]}

class Fake:
    def __init__(self):
        b=io.BytesIO();Image.new('RGB',(20,30),'red').save(b,'WEBP');self.photo=b.getvalue();self.upload=None;self.unsigned=False
    def call(self,url,**kwargs):
        if url.endswith('.webp'):return self.photo
        if 'object/sign' in url:
            self.unsigned=kwargs.get('auth') is False
            return self.upload
        return self.photo
    def storage_upload(self,path,raw,mime):
        assert path.startswith(m.STORAGE_ROOT)
        if mime=='application/zip':self.upload=raw
    def signed_url(self,path):
        return 'https://example.supabase.co/storage/v1/object/sign/'+path
    def reserve_archive(self,ident,path,size,images=None):self.reserved=size
    def finish_archive(self,ident):self.finished=True

class Tests(unittest.TestCase):
    def setUp(self):self.req={'cabinet':'china','family':'NoelBag','max_photos':24}
    def test_family_exact_and_case_insensitive(self):
        selected,_=m.select_cards([card(),card('59-Noelbag-blue',124),card('60-OtherBag-red',125)],self.req)
        self.assertEqual(len(selected),2)
    def test_exact_articles_not_substrings(self):
        req={'cabinet':'china','articles':['57-noelbag-RED'],'max_photos':1}
        self.assertEqual(m.select_cards([card(),card('157-NoelBag-red',125)],req)[0][0]['nmID'],123)
    def test_missing_requested_article_fails(self):
        with self.assertRaisesRegex(m.Stop,'missing'):m.select_cards([card()],{'cabinet':'china','articles':['absent']})
    def test_duplicate_card_identity_fails(self):
        with self.assertRaises(m.Stop):m.select_cards([card(),card()],self.req)
    def test_duplicate_article_fails(self):
        with self.assertRaises(m.Stop):m.select_cards([card(),card(nm=124)],self.req)
    def test_empty_gallery_fails(self):
        c=card();c['photos']=[]
        with self.assertRaises(m.Stop):m.select_cards([c],self.req)
    def test_selection_limits(self):
        with self.assertRaises(m.Stop):m.select_cards([card(str(n)+'-NoelBag-red',n+1) for n in range(61)],self.req)
    def test_wrong_cabinet_and_arbitrary_selector_rejected(self):
        for req in ({'cabinet':'ooo','family':'NoelBag'},{'cabinet':'china','family':'NoelBag','articles':['a']},{'cabinet':'china','family':'https://evil'},{'cabinet':'china','family':'NoelBag','max_photos':True}):
            with self.assertRaises(m.Stop):m.valid_request(req)
    def test_photo_host_path_and_credentials_constrained(self):
        good=card()['photos'][0]['big'];self.assertEqual(m.photo_url({'big':good}),good)
        for url in ('http://localhost/a','https://evil.test/x','https://basket-47.wbbasket.ru.evil.test/x','https://user:pass@basket-47.wbbasket.ru/vol1/part1/1/images/big/1.webp',good+'?secret=x',good.replace('/images/','/../images/')):
            with self.assertRaises(m.Stop):m.photo_url({'big':url})
    def test_archive_real_images_identity_and_unsigned_download(self):
        client=Fake();result=m.export(client,self.req,'00000000-0000-4000-8000-000000000000',[card()])
        self.assertEqual(result['status'],'ready');self.assertEqual(result['wb_writes'],0);self.assertTrue(client.unsigned)
        with zipfile.ZipFile(io.BytesIO(client.upload)) as z:
            manifest=json.loads(z.read('MANIFEST.json'))
            self.assertEqual(manifest['cards'][0]['article'],'57-NoelBag-red')
            self.assertEqual(z.read('123/01.webp'),client.photo)
            self.assertIsNone(z.testzip())
    def test_corrupt_image_not_uploaded(self):
        c=Fake();c.photo=b'not an image'
        with self.assertRaises(Exception):m.export(c,self.req,'id',[card()])
        self.assertIsNone(c.upload)
    def test_corrupt_storage_readback_fails(self):
        c=Fake();original=c.call
        c.call=lambda url,**kw: b'corrupt' if 'object/sign' in url else original(url,**kw)
        with self.assertRaisesRegex(m.Stop,'hash_mismatch'):m.export(c,self.req,'id',[card()])
    def test_storage_budget_blocks_upload(self):
        c=Fake()
        def reject(*args):raise m.Stop('photo_cache_budget_reached')
        c.reserve_archive=reject
        with self.assertRaisesRegex(m.Stop,'budget'):m.export(c,self.req,'id',[card()])
        self.assertIsNone(c.upload)
    def test_drive_route_returns_verified_archive_without_storage_links(self):
        c=Fake();c.get=lambda key:{'delivery':'google_drive'}
        captured=[]
        c.drive_upload=lambda ident,raw:captured.append(raw) or {'file_id':'fixtureFile123','server_verified':True}
        r=m.export(c,self.req,'00000000-0000-4000-8000-000000000000',[card()])
        self.assertEqual(r['status'],'ready');self.assertTrue(r['drive']['server_verified'])
        self.assertIsNone(c.upload);self.assertNotIn('archive_url',r)
        with zipfile.ZipFile(io.BytesIO(captured[0])) as z:
            self.assertEqual(z.read('123/01.webp'),c.photo)

if __name__=='__main__':unittest.main()
