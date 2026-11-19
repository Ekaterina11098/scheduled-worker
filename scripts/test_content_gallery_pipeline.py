import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import zipfile
if (Path(__file__).parent/'deps').exists():sys.path.insert(0,str(Path(__file__).parent/'deps'))
import numpy as np
from PIL import Image,ImageDraw
from content_gallery_pipeline import (GalleryError,NeedsSourceReview,extract_product,
    render_pages,placements,candidate_indices,build_gallery,png,sha,product_asset)


def product():
    image=Image.new('RGB',(700,900),'white');draw=ImageDraw.Draw(image)
    draw.rounded_rectangle((140,320,560,700),radius=45,fill=(70,30,20))
    draw.rectangle((330,410,370,455),fill=(180,140,25))
    draw.arc((220,160,480,410),180,360,fill=(25,20,15),width=14)
    return png(image)


def items(n):
    return [{'article':f'{i}-ExampleBag-black','nmID':1473000000+i,
             'image':Image.new('RGBA',(300,200),(40,30,20,255))} for i in range(n)]


class LayoutTests(unittest.TestCase):
    def test_twenty_items_are_fourteen_plus_six_with_same_body_width(self):
        pages,qa=render_pages(items(20),'ExampleBag')
        self.assertEqual([p['count'] for p in pages],[14,6])
        self.assertEqual(len(set(p['label'] for p in qa['placements'])),20)
        first=qa['placements'][0];second=qa['placements'][14]
        self.assertEqual(first['product_rect'],second['product_rect'])
        for p in pages:self.assertEqual(Image.open(io.BytesIO(p['raw'])).size,(1086,1448))

    def test_last_two_are_centered_without_enlargement(self):
        self.assertEqual(placements(14)[-2:],[(369,1220),(717,1220)])
        self.assertEqual(placements(6),[(195,180),(543,180),(891,180),(195,440),(543,440),(891,440)])

    def test_one_and_two_item_pages_are_centered(self):
        self.assertEqual(placements(1),[(543,180)])
        self.assertEqual(placements(2),[(369,180),(717,180)])

    def test_duplicate_and_invalid_ids_are_rejected(self):
        rows=items(2);rows[1]['nmID']=rows[0]['nmID']
        with self.assertRaises(GalleryError):render_pages(rows,'ExampleBag')
        rows=items(1);rows[0]['nmID']='123'
        with self.assertRaises(GalleryError):render_pages(rows,'ExampleBag')

    def test_background_and_render_are_deterministic(self):
        a,_=render_pages(items(2),'ExampleBag');b,_=render_pages(items(2),'ExampleBag')
        self.assertEqual(a[0]['raw'],b[0]['raw'])
        self.assertEqual(Image.open(io.BytesIO(a[0]['raw'])).getpixel((5,1400)),(244,244,245))


class ExtractionTests(unittest.TestCase):
    def test_original_rgb_is_preserved_and_thin_strap_is_removed(self):
        raw=product();asset,qa=extract_product(raw)
        rgb=np.array(Image.open(io.BytesIO(raw)).convert('RGB'))
        x0,y0,x1,y1=qa['mask_bbox'];rgba=np.array(asset);active=rgba[:,:,3]>0
        self.assertTrue(np.array_equal(rgba[:,:,:3][active],rgb[y0:y1,x0:x1][active]))
        self.assertGreater(y0,280)
        self.assertEqual(qa['generated_product_pixels'],0)

    def test_detected_face_is_always_rejected(self):
        with patch('content_gallery_pipeline.face_count',return_value=1):
            with self.assertRaisesRegex(GalleryError,'contains_face'):extract_product(product())

    def test_original_product_panel_below_infographic_is_recovered(self):
        im=Image.new('RGB',(700,1800),'white');d=ImageDraw.Draw(im)
        d.rectangle((40,100,660,650),fill=(160,130,100))
        im.paste(Image.open(io.BytesIO(product())),(0,900))
        raw=png(im);asset,qa=extract_product(raw)
        self.assertEqual(qa['source_crop'],[0,900,700,1800])
        self.assertEqual(qa['source_sha256'],sha(raw))
        x0,y0,x1,y1=qa['mask_bbox'];a=np.array(asset);active=a[:,:,3]>0
        self.assertTrue(np.array_equal(a[:,:,:3][active],np.array(im)[y0:y1,x0:x1][active]))

    def test_attached_upper_handle_is_preserved_without_reconstruction(self):
        im=Image.open(io.BytesIO(product())).convert('RGB');d=ImageDraw.Draw(im)
        d.line((220,270,220,350),fill=(25,20,15),width=14)
        d.line((480,270,480,350),fill=(25,20,15),width=14)
        asset,qa=extract_product(png(im))
        self.assertLess(qa['mask_bbox'][1],200)
        self.assertGreater(qa['body_bbox'][1],280)
        self.assertEqual(qa['generated_product_pixels'],0)

    def test_busy_background_is_rejected(self):
        im=Image.new('RGB',(700,900),(80,90,100))
        with self.assertRaisesRegex(GalleryError,'nonisolated'):extract_product(png(im))

    def test_clipped_object_is_rejected(self):
        im=Image.new('RGB',(700,900),'white');ImageDraw.Draw(im).rectangle((0,320,550,700),fill='black')
        with self.assertRaises(GalleryError):extract_product(png(im))

    def test_multiple_large_objects_are_rejected(self):
        im=Image.new('RGB',(900,1200),'white');d=ImageDraw.Draw(im)
        d.rectangle((80,350,400,800),fill='black');d.rectangle((500,350,820,800),fill='brown')
        with self.assertRaisesRegex(GalleryError,'multiple'):extract_product(png(im))

    def test_blank_image_is_rejected(self):
        with self.assertRaises(GalleryError):extract_product(png(Image.new('RGB',(700,900),'white')))

    def test_candidates_are_bounded_and_product_views_precede_covers(self):
        self.assertEqual(candidate_indices(1),[0])
        self.assertEqual(candidate_indices(10),[9,8,7,4,0])
        self.assertLessEqual(len(candidate_indices(24)),6)


class PackageTests(unittest.TestCase):
    def test_package_has_real_finals_and_matching_nested_zip(self):
        class Client:
            def call(self,*args,**kwargs):return product()
            def drive_upload(self,ident,raw):self.raw=raw;return {'file_id':'fixture','server_verified':True}
        client=Client();cards=[{'vendorCode':'1-ExampleBag-brown','nmID':123,'photos':[{'url':'unused'}]}]
        result=build_gallery(client,{'family':'ExampleBag'},'00000000-0000-0000-0000-000000000001',cards,lambda p:'fixture')
        self.assertEqual(result['page_counts'],[1]);self.assertEqual(result['paid_calls'],0)
        with zipfile.ZipFile(io.BytesIO(client.raw)) as package:
            manifest=json.loads(package.read('MANIFEST.json'))
            page=manifest['pages'][0]
            actual=package.read('final/'+page['file'])
            self.assertEqual(sha(actual),page['sha256'])
            with zipfile.ZipFile(io.BytesIO(package.read('FINAL_GALLERY.zip'))) as final:
                self.assertEqual(final.read(page['file']),actual)

    def test_unsafe_sources_get_review_package_not_a_fake_ready_gallery(self):
        class Client:
            def call(self,*args,**kwargs):return png(Image.new('RGB',(700,900),(80,90,100)))
            def drive_upload(self,ident,raw):return {'file_id':'review-fixture'}
        with self.assertRaises(NeedsSourceReview) as cm:
            build_gallery(Client(),{'family':'ExampleBag'},'00000000-0000-0000-0000-000000000001',
                          [{'vendorCode':'1-ExampleBag-brown','nmID':123,'photos':[{}]}],lambda p:'fixture')
        self.assertEqual(cm.exception.review_result['drive']['file_id'],'review-fixture')
        self.assertEqual(cm.exception.issues[0]['nmID'],123)

    def test_asset_cache_cannot_escape_its_private_prefix(self):
        class Client:
            def get(self,key):return {'path':'unrelated-business-file.png'}
        with self.assertRaisesRegex(GalleryError,'cache_scope'):product_asset(Client(),product())


if __name__=='__main__':unittest.main()
