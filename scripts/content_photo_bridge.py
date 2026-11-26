"""Private WB China photo export. No WB mutations, models or public artifacts."""
import collections
import datetime as dt
import hashlib
import http.client
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
import requests
from PIL import Image
from content_photo_drive import Delivery as DriveDelivery

PROJECT = 'abxgjoqlddhtcmjcjwxw'
ROOT = 'content_photo_bridge:v1:'
BUCKET = 'owner-media-recovery'
STORAGE_ROOT = 'content-photo-bridge/v1/'
MAX_FILES = 600
MAX_BYTES = 100 * 1024 * 1024
URL_TTL = 3600
STORAGE_BUDGET = 256 * 1024 * 1024

class Stop(Exception):
    pass

def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def valid_request(value):
    if value.get('operation','source') not in ('source','gallery'):
        raise Stop('operation_not_supported')
    if value.get('cabinet') != 'china':
        raise Stop('cabinet_not_supported')
    articles, family = value.get('articles') or [], value.get('family')
    if bool(articles) == bool(family):
        raise Stop('choose_articles_or_family')
    if not isinstance(articles,list) or len(articles)>60 or any(not isinstance(s,str) or not re.fullmatch(r'[\w .-]{1,120}',s) for s in articles):
        raise Stop('invalid_articles')
    if family and (not isinstance(family,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9]{1,39}',family)):
        raise Stop('invalid_family')
    limit = value.get('max_photos',24)
    if type(limit) is not int or not 1 <= limit <= 24:
        raise Stop('invalid_photo_limit')
    return articles,family,limit

def select_cards(cards, request):
    articles,family,limit = valid_request(request)
    by_nm = {}
    for card in cards:
        nm = card.get('nmID')
        if type(nm) is not int or nm <= 0 or nm in by_nm:
            raise Stop('invalid_or_duplicate_card_identity')
        by_nm[nm]=card
    wanted={s.casefold() for s in articles}
    selected=[c for c in cards if str(c.get('vendorCode','')).casefold() in wanted] if articles else [c for c in cards if len(str(c.get('vendorCode','')).split('-'))>1 and c['vendorCode'].split('-')[1].casefold()==family.casefold()]
    counts=collections.Counter(str(c['vendorCode']).casefold() for c in selected)
    if any(n!=1 for n in counts.values()):
        raise Stop('ambiguous_article')
    if articles and set(counts) != {s.casefold() for s in articles}:
        raise Stop('requested_articles_missing')
    if not selected or len(selected)>60:
        raise Stop('selection_empty_or_too_large')
    selected.sort(key=lambda c:(c['vendorCode'].casefold(),c['nmID']))
    if any(not isinstance(c.get('photos'),list) or not c['photos'] for c in selected):
        raise Stop('card_without_photos')
    if sum(min(limit,len(c['photos'])) for c in selected)>MAX_FILES:
        raise Stop('photo_count_limit_select_smaller_batch')
    return selected,limit

def photo_url(photo):
    url=photo.get('big') or photo.get('c516x688')
    parsed=urllib.parse.urlsplit(url or '')
    if parsed.scheme!='https' or parsed.username or parsed.password or parsed.port or not re.fullmatch(r'basket-\d+\.(?:wbbasket\.ru|wbcontent\.net)',parsed.hostname or ''):
        raise Stop('unexpected_photo_host')
    if not re.fullmatch(r'/vol\d+/part\d+/\d+/images/(?:big|c516x688)/\d+\.(?:webp|jpg|jpeg|png)',parsed.path) or parsed.query or parsed.fragment:
        raise Stop('unexpected_photo_path')
    return url

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise Stop('redirect_prohibited')

class Client:
    def __init__(self):
        self.base=os.environ['SUPABASE_URL'].rstrip('/')
        if self.base!='https://'+PROJECT+'.supabase.co':raise Stop('project_mismatch')
        self.key=os.environ['SUPABASE_SECRET_KEY']
        self.opener=urllib.request.build_opener(NoRedirect())
        self.last_wb=0
    def call(self,url,method='GET',body=None,headers=None,limit=MAX_BYTES,auth=True):
        headers=dict(headers or {})
        if auth and url.startswith(self.base+'/'):
            headers['apikey']=self.key
            if not self.key.startswith('sb_secret_'):headers['Authorization']='Bearer '+self.key
        data=body if isinstance(body,bytes) else json.dumps(body).encode() if body is not None else None
        if body is not None and not isinstance(body,bytes):headers['Content-Type']='application/json'
        req=urllib.request.Request(url,data=data,headers=headers,method=method)
        retryable = method=='GET' or url=='https://content-api.wildberries.cn/content/v2/get/cards/list'
        for attempt in range(3):
            try:
                with requests.request(method,url,data=data,headers=headers,timeout=(20,90),allow_redirects=False,stream=True) as response:
                    if 300<=response.status_code<400:raise Stop('redirect_prohibited')
                    if response.status_code in (429,500,502,503,504) and retryable and attempt<2:
                        time.sleep(2*(attempt+1));continue
                    if response.status_code>=400:raise Stop('http_'+str(response.status_code))
                    chunks=[];size=0
                    for chunk in response.iter_content(65536):
                        size+=len(chunk)
                        if size>limit:raise Stop('response_size_limit')
                        chunks.append(chunk)
                    return b''.join(chunks)
            except urllib.error.HTTPError as error:
                if error.code in (429,500,502,503,504) and retryable and attempt<2:
                    time.sleep(2*(attempt+1));continue
                raise Stop('http_'+str(error.code)) from None
            except (TimeoutError,urllib.error.URLError,http.client.IncompleteRead,ConnectionError,requests.exceptions.RequestException):
                if retryable and attempt<2:time.sleep(2*(attempt+1));continue
                raise Stop('transport_error') from None
    def cache(self,query,method='GET',body=None,prefer='return=representation'):
        raw=self.call(self.base+'/rest/v1/telegram_api_cache?'+urllib.parse.urlencode(query),method,body,{'Prefer':prefer})
        return json.loads(raw) if raw else []
    def get(self,key):
        rows=self.cache({'cache_key':'eq.'+key,'select':'payload'})
        if len(rows)>1:raise Stop('duplicate_cache_record')
        return rows[0]['payload'] if rows else None
    def put(self,key,payload):
        if not key.startswith(ROOT):raise Stop('cache_scope')
        expiry='2030-01-01T00:00:00Z' if key.startswith((ROOT+'artifact:',ROOT+'gallery_asset:')) else (dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=8)).isoformat()
        body={'cache_key':key,'payload':payload,'updated_at':stamp(),'expires_at':expiry}
        self.cache({'on_conflict':'cache_key'},'POST',body,'resolution=merge-duplicates,return=representation')
        if self.get(key)!=payload:raise Stop('cache_readback_mismatch')
    def claim(self,ident):
        body={'cache_key':ROOT+'claim:'+ident,'payload':{'at':stamp(),'run_id':os.environ.get('GITHUB_RUN_ID')},'updated_at':stamp(),'expires_at':'2030-01-01T00:00:00Z'}
        return bool(self.cache({'on_conflict':'cache_key'},'POST',body,'resolution=ignore-duplicates,return=representation'))
    def catalog(self):
        cursor={'limit':100};cards=[];seen=set()
        for page in range(40):
            time.sleep(max(0,1-(time.monotonic()-self.last_wb)));self.last_wb=time.monotonic()
            body={'settings':{'sort':{'ascending':True},'cursor':cursor,'filter':{'withPhoto':-1}}}
            raw=self.call('https://content-api.wildberries.cn/content/v2/get/cards/list','POST',body,{'Authorization':os.environ['WB_TOKEN_3']},limit=8_000_000)
            data=json.loads(raw);data=data.get('data',data) if 'cards' not in data else data
            rows=data['cards']
            if not isinstance(rows,list):raise Stop('invalid_card_page')
            cards.extend(rows)
            if len(rows)<100:return cards
            marker=(data['cursor']['updatedAt'],data['cursor']['nmID'])
            if marker in seen:raise Stop('pagination_loop')
            seen.add(marker);cursor={'limit':100,'updatedAt':marker[0],'nmID':marker[1]}
        raise Stop('incomplete_catalog')
    def storage_upload(self,path,raw,mime):
        if not path.startswith(STORAGE_ROOT):raise Stop('storage_scope')
        encoded=urllib.parse.quote(BUCKET+'/'+path,safe='/')
        self.call(self.base+'/storage/v1/object/'+encoded,'POST',raw,{'Content-Type':mime,'x-upsert':'true'},limit=10000)
    def signed_url(self,path):
        raw=self.call(self.base+'/storage/v1/object/sign/'+urllib.parse.quote(BUCKET+'/'+path,safe='/'),'POST',{'expiresIn':URL_TTL},limit=10000)
        value=json.loads(raw)['signedURL']
        if not value.startswith('/object/sign/'+BUCKET+'/'):raise Stop('unexpected_signed_path')
        return self.base+'/storage/v1'+value
    def drive_upload(self,ident,raw):
        credentials=json.loads(self.call(self.base+'/rest/v1/rpc/content_photo_drive_credentials','POST',{}))
        def transport(method,url,**kwargs):
            try:return requests.request(method,url,**kwargs)
            except requests.exceptions.RequestException:raise ConnectionError('drive_transport') from None
        return DriveDelivery(credentials,transport).upload(ident,raw)
    def reserve_archive(self,ident,path,size,images=None):
        rows=self.cache({'cache_key':'like.'+ROOT+'artifact:*','payload->>status':'neq.deleted','select':'cache_key,payload','limit':1000})
        if len(rows)>=1000:raise Stop('artifact_inventory_limit')
        used=0
        for row in rows:
            item=row['payload']
            if item.get('status')=='deleted':continue
            old=dt.datetime.fromisoformat(item['created_at'].replace('Z','+00:00'))
            if dt.datetime.now(dt.timezone.utc)-old>dt.timedelta(days=7):
                old_paths=[item['path']]+item.get('images',[])
                if any(not re.fullmatch(re.escape(STORAGE_ROOT)+r'requests/[a-f0-9-]{36}/(?:sources\.zip|\d+/\d+\.(?:webp|jpg|png))',p) for p in old_paths):raise Stop('cleanup_scope')
                for offset in range(0,len(old_paths),100):
                    self.call(self.base+'/storage/v1/object/'+BUCKET,'DELETE',{'prefixes':old_paths[offset:offset+100]},limit=10000)
                self.put(row['cache_key'],{**item,'status':'deleted','deleted_at':stamp()})
            else:used+=item['bytes']
        if used+size>STORAGE_BUDGET:raise Stop('photo_cache_budget_reached_select_smaller_batch')
        self.put(ROOT+'artifact:'+ident,{'path':path,'images':images or [],'bytes':size,'status':'reserved','created_at':stamp()})
    def finish_archive(self,ident):
        key=ROOT+'artifact:'+ident;item=self.get(key)
        self.put(key,{**item,'status':'stored','stored_at':stamp()})

def export(client,request,ident,cards):
    selected,limit=select_cards(cards,request)
    if request.get('operation')=='gallery':
        from content_gallery_pipeline import build_gallery
        return {**build_gallery(client,request,ident,selected,photo_url),'request':request,'ready_at':stamp(),'observed_at':stamp()}
    files=[];total_bytes=0;archive=io.BytesIO();card_info=[]
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED) as z:
        for card in selected:
            item={'article':card['vendorCode'],'nmID':card['nmID'],'total_photos':len(card['photos']),'photos':[]}
            for n,photo in enumerate(card['photos'][:limit],1):
                url=photo_url(photo);raw=client.call(url,limit=5_000_000)
                with Image.open(io.BytesIO(raw)) as image:
                    size=image.size;fmt=image.format;image.verify()
                if fmt not in ('WEBP','JPEG','PNG') or min(size)<=0:raise Stop('invalid_image')
                total_bytes+=len(raw)
                if total_bytes>MAX_BYTES:raise Stop('export_size_limit_select_smaller_batch')
                digest=hashlib.sha256(raw).hexdigest();ext={'WEBP':'webp','JPEG':'jpg','PNG':'png'}[fmt]
                filename=str(card['nmID'])+'/'+str(n).zfill(2)+'.'+ext
                z.writestr(filename,raw)
                info={'file':filename,'photo':n,'bytes':len(raw),'width':size[0],'height':size[1],'sha256':digest,'source_url':url}
                item['photos'].append(info);files.append(info)
            card_info.append(item)
        manifest={'request_id':ident,'observed_at':stamp(),'cabinet':'china','cards':card_info,'image_count':len(files),'wb_writes':0,'generated_images':0,'source':'fresh WB Content API with complete pagination','truncated_galleries':any(x['total_photos']>len(x['photos']) for x in card_info)}
        z.writestr('MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        z.writestr('README.txt','Real WB source images. Use MANIFEST.json to map nmID folders to vendorCode. Select front view visually; never invent a missing angle, color or texture. No WB data changed.')
    raw=archive.getvalue()
    if len(raw)>MAX_BYTES+2_000_000:raise Stop('archive_size_limit')
    policy=client.get(ROOT+'policy') if hasattr(client,'get') else {}
    if policy and policy.get('delivery')=='google_drive':
        delivered=client.drive_upload(ident,raw)
        return {'status':'ready','request_id':ident,'cabinet':'china','observed_at':manifest['observed_at'],
                'ready_at':stamp(),'card_count':len(card_info),'photo_count':len(files),
                'drive':delivered,'archive_bytes':len(raw),'archive_sha256':hashlib.sha256(raw).hexdigest(),
                'cards':[{'article':c['article'],'nmID':c['nmID'],'photos':len(c['photos']),'total_photos':c['total_photos']} for c in card_info],
                'request':request,'wb_writes':0,'paid_calls':0,'run_id':os.environ.get('GITHUB_RUN_ID')}
    path=STORAGE_ROOT+'requests/'+ident+'/sources.zip'
    image_paths=[STORAGE_ROOT+'requests/'+ident+'/'+f['file'] for f in files]
    client.reserve_archive(ident,path,len(raw)+total_bytes,image_paths)
    client.storage_upload(path,raw,'application/zip')
    images=[]
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for card in card_info:
            for f in card['photos']:
                image_path=STORAGE_ROOT+'requests/'+ident+'/'+f['file']
                data=z.read(f['file'])
                mime='image/'+('jpeg' if f['file'].endswith('.jpg') else f['file'].rsplit('.',1)[1])
                client.storage_upload(image_path,data,mime)
                url=client.signed_url(image_path)
                if hashlib.sha256(client.call(url,limit=5_000_000,auth=False)).hexdigest()!=f['sha256']:raise Stop('image_download_hash_mismatch')
                images.append({**f,'article':card['article'],'nmID':card['nmID'],'url':url})
    signed=client.signed_url(path)
    # Verify real authenticated-free download, bytes and archive structure before ready.
    check=client.call(signed,limit=MAX_BYTES+2_000_000,auth=False)
    if hashlib.sha256(check).digest()!=hashlib.sha256(raw).digest():raise Stop('storage_download_hash_mismatch')
    with zipfile.ZipFile(io.BytesIO(check)) as z:
        if z.testzip() is not None:raise Stop('archive_corrupt')
    client.finish_archive(ident)
    return {'status':'ready','request_id':ident,'observed_at':manifest['observed_at'],'ready_at':stamp(),'cabinet':'china','card_count':len(card_info),'photo_count':len(files),'archive_url':signed,'images':images,'url_expires_at':(dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=URL_TTL)).isoformat(),'archive_bytes':len(raw),'archive_sha256':hashlib.sha256(raw).hexdigest(),'storage_path':path,'cards':[{'article':c['article'],'nmID':c['nmID'],'photos':len(c['photos']),'total_photos':c['total_photos']} for c in card_info],'wb_writes':0,'paid_calls':0,'run_id':os.environ.get('GITHUB_RUN_ID'),'request':request}

def run():
    if os.environ.get('GITHUB_REPOSITORY')!='Ekaterina11098/scheduled-worker' or os.environ.get('GITHUB_REF')!='refs/heads/main':raise Stop('runner_identity')
    client=Client();policy=client.get(ROOT+'policy')
    if not policy or policy.get('enabled') is not True:print('Photo export disabled');return
    bucket=json.loads(client.call(client.base+'/storage/v1/bucket/'+BUCKET,limit=10000))
    if bucket.get('public') is not False:raise Stop('private_bucket_required')
    rows=client.cache({'cache_key':'like.'+ROOT+'request:*','payload->>status':'eq.queued','select':'cache_key,payload','order':'updated_at.asc','limit':5})
    cards=None;processed=0
    for row in rows:
        key=row['cache_key'];request=row['payload'];ident=key.removeprefix(ROOT+'request:')
        if str(uuid.UUID(ident))!=ident:raise Stop('request_identity')
        if not client.claim(ident):continue
        try:
            if request.get('operation') != 'media_inspect':
                valid_request(request)
            age=dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(request['created_at'].replace('Z','+00:00'))
            if not 0<=age.total_seconds()<3600:raise Stop('request_expired')
            client.put(key,{**request,'status':'running','started_at':stamp(),'run_id':os.environ.get('GITHUB_RUN_ID')})
            if request.get('operation') == 'media_inspect':
                from wb_china_media_inspect import inspect_card

                if request.get('cabinet') != 'china':
                    raise Stop('cabinet_not_supported')
                card = inspect_card(client, request.get('vendorCode'), request.get('nmID'))
                result = {
                    **request, 'status': 'ready', 'finished_at': stamp(),
                    'nmID': card['nmID'], 'photo_count': len(card['photos']),
                    'photo_field_present': card['photo_field_present'],
                    'photo_positions': list(range(1, len(card['photos']) + 1)),
                    'has_video': bool(card['video']),
                    'video_field_present': card['video_field_present'],
                    'wb_writes': 0,
                }
            else:
                if cards is None:cards=client.catalog()
                result=export(client,request,ident,cards)
            client.put(key,result);processed+=1
        except Exception as error:
            from content_photo_drive import DriveError
            from content_gallery_pipeline import GalleryError,NeedsSourceReview
            if isinstance(error,NeedsSourceReview):
                client.put(key,{**request,'status':'needs_source_review','finished_at':stamp(),'issues':error.issues,**getattr(error,'review_result',{}),'wb_writes':0,'run_id':os.environ.get('GITHUB_RUN_ID')})
                continue
            code=str(error) if isinstance(error,(Stop,DriveError,GalleryError)) else type(error).__name__
            code=re.sub('[^a-zA-Z0-9_]','',code)[:100]
            client.put(key,{**request,'status':'failed','finished_at':stamp(),'safe_error':code,'run_id':os.environ.get('GITHUB_RUN_ID'),'wb_writes':0})
    client.put(ROOT+'health',{'at':stamp(),'processed':processed,'run_id':os.environ.get('GITHUB_RUN_ID'),'wb_writes':0})
    print('Private photo export finished; WB writes=0; public artifacts=0')

if __name__=='__main__':
    try:run()
    except Exception:
        print('Photo export stopped safely; inspect private health record')
        raise SystemExit(1)
