"""Deterministic gallery assembly from conservative, unaltered source-photo masks.

No generative product reconstruction. The accepted source RGB pixels are retained;
only an alpha mask, scaling and placement are applied. Ambiguous sources fail closed.
"""
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import zipfile
import uuid
import urllib.parse
import time

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

VERSION = 'gallery-v1.0.0'
BG = (244, 244, 245)
SIZE = (1086, 1448)
ROWS = (180, 440, 700, 960, 1220)
CENTERS = (195, 543, 891)
ROOT='content_photo_bridge:v1:'
STORAGE='content-photo-bridge/v1/gallery/'


class GalleryError(Exception):
    pass


class NeedsSourceReview(GalleryError):
    def __init__(self, issues):
        super().__init__('gallery_source_requires_review')
        self.issues = issues


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def png(image):
    out = io.BytesIO()
    image.save(out, format='PNG', optimize=True)
    return out.getvalue()


def face_count(rgb):
    small = cv2.resize(rgb, (0, 0), fx=.55, fy=.55)
    gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
    count = 0
    for name in ('haarcascade_frontalface_default.xml', 'haarcascade_profileface.xml'):
        detector = cv2.CascadeClassifier(cv2.data.haarcascades + name)
        if detector.empty():
            raise GalleryError('gallery_face_detector_unavailable')
        for test in (gray, cv2.flip(gray, 1)):
            count += len(detector.detectMultiScale(test, scaleFactor=1.1, minNeighbors=5, minSize=(24,24)))
    return count


def extract_product(raw):
    """Accept only isolated product photography; never synthesize hidden areas."""
    image = Image.open(io.BytesIO(raw)).convert('RGB')
    if min(image.size) < 400 or max(image.size) > 3000 or image.width*image.height>6_000_000:
        raise GalleryError('gallery_source_dimensions')
    rgb = np.array(image)
    h, w = rgb.shape[:2]
    if face_count(rgb):
        raise GalleryError('gallery_source_contains_face')
    # Product-only source photography has a neutral, very bright perimeter.
    edge = np.concatenate((rgb[:12].reshape(-1,3), rgb[-12:].reshape(-1,3), rgb[:, :12].reshape(-1,3), rgb[:, -12:].reshape(-1,3)))
    neutral = (np.min(edge,axis=1)>235)&(np.ptp(edge.astype(np.int16),axis=1)<15)
    if float(neutral.mean()) < .96:
        raise GalleryError('gallery_nonisolated_background')
    # Remove neutral-white background and its weak shadow. Keep source RGB intact.
    white = (np.min(rgb,axis=2)>232)&(np.ptp(rgb.astype(np.int16),axis=2)<18)
    foreground = (~white).astype(np.uint8)*255
    # Opening removes text, loose thin shoulder straps and detached decorations,
    # retaining the bag body. No color, hardware or texture pixels are redrawn.
    kernel_size = max(33, min(81, int(min(w,h)*.08)//2*2+1))
    opened = cv2.morphologyEx(foreground, cv2.MORPH_OPEN,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(kernel_size,kernel_size)))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(opened,8)
    if n < 2:
        raise GalleryError('gallery_product_not_found')
    sizes = stats[1:,cv2.CC_STAT_AREA]
    index = 1+int(np.argmax(sizes))
    x,y,bw,bh,area = (int(v) for v in stats[index])
    dominance = area / max(1,int(sizes.sum()))
    if dominance < .93:
        raise GalleryError('gallery_multiple_objects_or_text')
    if not (.24*w < bw < .94*w and .20*h < bh < .78*h and .35 < bw/bh < 2.6):
        raise GalleryError('gallery_body_geometry')
    if min(x,y,w-x-bw,h-y-bh) < min(w,h)*.025:
        raise GalleryError('gallery_product_clipped')
    body = (labels==index).astype(np.uint8)*255
    # Recover original edge pixels close to the body, without regrowing straps.
    nearby=cv2.dilate(body,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(9,9)))
    mask = cv2.bitwise_and(nearby,foreground)
    n2, lab2, st2, _ = cv2.connectedComponentsWithStats(mask,8)
    main2=1+int(np.argmax(st2[1:,cv2.CC_STAT_AREA]))
    mask=(lab2==main2).astype(np.uint8)*255
    ys,xs=np.where(mask>0)
    x0,x1,y0,y1=int(xs.min()),int(xs.max()+1),int(ys.min()),int(ys.max()+1)
    fill=float((mask[y0:y1,x0:x1]>0).mean())
    if fill < .45:
        raise GalleryError('gallery_sparse_product_mask')
    # Standing/seated human silhouettes and fragments tend to be tall/asymmetric.
    local=mask[y0:y1,x0:x1]>0
    contours,hierarchy=cv2.findContours(local.astype(np.uint8),cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is not None:
        holes=[cv2.contourArea(c) for c,hx in zip(contours,hierarchy[0]) if hx[3]>=0]
        if holes and max(holes)>.015*bw*bh:
            raise GalleryError('gallery_light_product_mask_ambiguous')
    flipped=np.fliplr(local)
    symmetry=float(np.logical_and(local,flipped).sum()/max(1,np.logical_or(local,flipped).sum()))
    if symmetry < .66 or (y1-y0)/(x1-x0)>1.65:
        raise GalleryError('gallery_ambiguous_front_view')
    alpha = Image.fromarray(mask)
    rgba=image.convert('RGBA')
    rgba.putalpha(alpha)
    rgba=rgba.crop((x0,y0,x1,y1))
    # Exact source preservation before resizing is independently verifiable.
    active=mask>0
    preserved_hash=sha(rgb[active].tobytes())
    qa={'source_sha256':sha(raw),'mask_bbox':[x0,y0,x1,y1],
        'mask_fill':round(fill,4),'symmetry':round(symmetry,4),
        'perimeter_neutral':round(float(neutral.mean()),4),'dominance':round(dominance,4),
        'face_detections':0,'method':'original_rgb_with_conservative_body_alpha',
        'original_rgb_hash':preserved_hash,'generated_product_pixels':0}
    return rgba,qa


def fonts():
    candidates=[('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                 '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
                ('C:/Windows/Fonts/arial.ttf','C:/Windows/Fonts/arialbd.ttf')]
    for regular,bold in candidates:
        if Path(regular).is_file() and Path(bold).is_file():
            return regular,bold
    raise GalleryError('gallery_font_unavailable')


def placements(count):
    if not 1<=count<=14:
        raise GalleryError('gallery_invalid_page_count')
    result=[]
    for i in range(count):
        row,col=divmod(i,3)
        remaining=count-row*3
        row_centers = CENTERS if remaining>=3 else ((369,717) if remaining==2 else (543,))
        result.append((row_centers[col],ROWS[row]))
    return result


def render_pages(items, family):
    ids=[item['nmID'] for item in items]
    if len(ids)!=len(set(ids)) or not 1<=len(ids)<=60:
        raise GalleryError('gallery_duplicate_or_invalid_ids')
    if any(type(x) is not int or x<=0 for x in ids):
        raise GalleryError('gallery_invalid_nmID')
    regular,bold=fonts()
    normal=ImageFont.truetype(regular,56)
    heavy=ImageFont.truetype(bold,56)
    numbers=ImageFont.truetype(regular,29)
    pages=[];placement_info=[]
    # One body width for the WHOLE family. Never stretch shape or upscale last page.
    target_width=min(240,min(int(182*item['image'].width/item['image'].height) for item in items))
    target_width=max(80,target_width)
    for page_index in range(math.ceil(len(items)/14)):
        page=Image.new('RGB',SIZE,BG);draw=ImageDraw.Draw(page)
        first='ВЫБЕРИ ';second='СВОЙ ЦВЕТ'
        total=draw.textlength(first,font=normal)+draw.textlength(second,font=heavy)
        hx=(SIZE[0]-total)/2
        draw.text((hx,52),first,font=normal,fill='black')
        draw.text((hx+draw.textlength(first,font=normal),52),second,font=heavy,fill='black')
        selected=items[page_index*14:(page_index+1)*14]
        for item,(cx,top) in zip(selected,placements(len(selected))):
            asset=item['image']
            height=round(asset.height*target_width/asset.width)
            if height>190:
                raise GalleryError('gallery_asset_too_tall')
            scaled=asset.resize((target_width,height),Image.Resampling.LANCZOS)
            xy=(round(cx-target_width/2),top)
            page.paste(scaled,xy,scaled)
            label=str(item['nmID'])
            tw=draw.textlength(label,font=numbers)
            draw.text((cx-tw/2,top+194),label,font=numbers,fill='black')
            placement_info.append({'page':page_index+1,'article':item['article'],'nmID':item['nmID'],
                                   'product_rect':[xy[0],xy[1],target_width,height],
                                   'label':label,'label_top':top+194})
        raw=png(page)
        with Image.open(io.BytesIO(raw)) as check:
            if check.size!=SIZE or check.mode!='RGB':
                raise GalleryError('gallery_render_readback')
        pages.append({'file':f'{family}_gallery_{page_index+1:02}.png','raw':raw,
                      'sha256':sha(raw),'count':len(selected),'width':SIZE[0],'height':SIZE[1]})
    return pages,{'version':VERSION,'pages':len(pages),'item_count':len(items),
                  'counts':[p['count'] for p in pages],'body_width':target_width,
                  'background':list(BG),'placements':placement_info,
                  'font_sha256':sha(Path(regular).read_bytes()),
                  'bold_font_sha256':sha(Path(bold).read_bytes()),'wb_writes':0,'paid_calls':0}


def candidate_indices(total):
    # Prefer original product-only terminal photos over model covers/infographics.
    return list(dict.fromkeys([i for i in (total-1,total-2,total-3,7,0) if 0<=i<total]))[:5]


def product_asset(client,raw):
    digest=sha(raw);revision=sha(Path(__file__).read_bytes())[:12]
    key=ROOT+'gallery_asset:'+revision+':'+digest
    saved=client.get(key) if hasattr(client,'get') else None
    if saved:
        path=saved['path']
        if not re.fullmatch(re.escape(STORAGE)+r'assets/[a-f0-9]{12}/[a-f0-9]{64}\.png',path):
            raise GalleryError('gallery_asset_cache_scope')
        encoded=urllib.parse.quote('owner-media-recovery/'+path,safe='/')
        cached=client.call(client.base+'/storage/v1/object/authenticated/'+encoded,limit=5_000_000)
        if sha(cached)!=saved['asset_sha256']:
            raise GalleryError('gallery_asset_cache_hash_mismatch')
        return Image.open(io.BytesIO(cached)).convert('RGBA'),saved['qa'],True
    asset,qa=extract_product(raw)
    if hasattr(client,'storage_upload'):
        data=png(asset);path=STORAGE+'assets/'+revision+'/'+digest+'.png'
        rows=client.cache({'cache_key':'like.'+ROOT+'gallery_asset:*','select':'payload','limit':1000})
        if len(rows)>=1000 or sum(int(r['payload'].get('bytes',0)) for r in rows)+len(data)>128*1024*1024:
            raise GalleryError('gallery_asset_cache_budget')
        client.storage_upload(path,data,'image/png')
        encoded=urllib.parse.quote('owner-media-recovery/'+path,safe='/')
        check=client.call(client.base+'/storage/v1/object/authenticated/'+encoded,limit=5_000_000)
        if sha(check)!=sha(data):raise GalleryError('gallery_asset_storage_readback')
        client.put(key,{'path':path,'source_sha256':digest,'asset_sha256':sha(data),'bytes':len(data),'qa':qa})
    return asset,qa,False


def build_gallery(client,request,ident,cards,url_validator):
    family=request.get('family') or str(cards[0]['vendorCode']).split('-')[1]
    if not re.fullmatch('[A-Za-z][A-Za-z0-9]{1,39}',family):
        raise GalleryError('gallery_invalid_family')
    items=[];issues=[];review_files={};download_bytes=0;deadline=time.monotonic()+600
    for card in cards:
        attempts=[];accepted=None
        for index in candidate_indices(len(card['photos'])):
            if time.monotonic()>deadline:raise GalleryError('gallery_processing_deadline')
            url=url_validator(card['photos'][index])
            raw=client.call(url,limit=5_000_000)
            download_bytes+=len(raw)
            if download_bytes>100*1024*1024:raise GalleryError('gallery_source_byte_budget')
            fmt=Image.open(io.BytesIO(raw)).format.lower()
            ext={'jpeg':'jpg','webp':'webp','png':'png'}.get(fmt)
            if not ext:raise GalleryError('gallery_source_format')
            review_files[f'review/candidates/{card["nmID"]}_{index+1:02}.{ext}']=raw
            try:
                asset,qa,cached=product_asset(client,raw)
                accepted={'article':card['vendorCode'],'nmID':card['nmID'],'image':asset,
                          'qa':qa,'source_photo':index+1,'source_url':url,'asset_cache_hit':cached}
                fmt=Image.open(io.BytesIO(raw)).format.lower()
                ext={'jpeg':'jpg','webp':'webp','png':'png'}.get(fmt)
                if not ext:raise GalleryError('gallery_source_format')
                review_files[f'review/originals/{card["nmID"]}.{ext}']=raw
                review_files[f'review/cutouts/{card["nmID"]}.png']=png(asset)
                break
            except GalleryError as exc:
                attempts.append({'photo':index+1,'reason':str(exc)})
        if accepted:items.append(accepted)
        else:issues.append({'article':card['vendorCode'],'nmID':card['nmID'],'attempts':attempts})
    if issues:
        review=io.BytesIO()
        with zipfile.ZipFile(review,'w',zipfile.ZIP_STORED) as z:
            z.writestr('MANIFEST.json',json.dumps({'request_id':ident,'family':family,'issues':issues},ensure_ascii=False,indent=2))
            for name,data in review_files.items():z.writestr(name,data)
        raw=review.getvalue()
        if len(raw)>100*1024*1024:raise GalleryError('gallery_package_size_limit')
        error=NeedsSourceReview(issues)
        error.review_result={'drive':client.drive_upload(str(uuid.uuid5(uuid.UUID(ident),'source-review')),raw),
                             'archive_bytes':len(raw),'archive_sha256':sha(raw)}
        raise error
    pages,qa=render_pages(items,family)
    manifest={'pipeline':VERSION,'request_id':ident,'family':family,'cabinet':'china',
              'cards':[{k:v for k,v in item.items() if k!='image'} for item in items],
              'pages':[{k:v for k,v in p.items() if k!='raw'} for p in pages],
              'qa':qa,'source':'fresh WB Content API product-only photography',
              'product_reconstruction':False,'generated_images':0,'wb_writes':0}
    final_zip=io.BytesIO()
    with zipfile.ZipFile(final_zip,'w',zipfile.ZIP_STORED) as z:
        for page in pages:z.writestr(page['file'],page['raw'])
    package=io.BytesIO()
    with zipfile.ZipFile(package,'w',zipfile.ZIP_STORED) as z:
        for page in pages:z.writestr('final/'+page['file'],page['raw'])
        z.writestr('FINAL_GALLERY.zip',final_zip.getvalue())
        z.writestr('MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        for name,raw in review_files.items():z.writestr(name,raw)
    raw=package.getvalue()
    if len(raw)>100*1024*1024:raise GalleryError('gallery_package_size_limit')
    delivered=client.drive_upload(str(uuid.uuid5(uuid.UUID(ident),'gallery-output')),raw)
    return {'status':'ready','operation':'gallery','pipeline':VERSION,'request_id':ident,
            'cabinet':'china','family':family,'card_count':len(items),'photo_count':len(items),
            'page_count':len(pages),'page_counts':[p['count'] for p in pages],
            'pages':manifest['pages'],'qa':qa,'cards':manifest['cards'],
            'drive':delivered,'archive_bytes':len(raw),'archive_sha256':sha(raw),
            'final_zip':'FINAL_GALLERY.zip','review_required':True,
            'wb_writes':0,'paid_calls':0,'generated_images':0,'run_id':os.environ.get('GITHUB_RUN_ID')}
