"""Exact110/024 read-only content audit; current cards/photos/prices/reviews, no sends."""
import copy,json,requests,os,time,io as bio,base64
from urllib.parse import urlparse
from datetime import datetime,timezone
from PIL import Image,ImageDraw
from china_advertising_state import AdvertisingIO
from china_morning_readiness import current_prices,published_stock
ROOT='china_agent:owner_deadstock_content:2026-11-25:v1'
ITEMS={1473244987:'110-GretaBag-beige',1473244988:'024-SilviaBag-gray'}
def now():return datetime.now(timezone.utc).isoformat()
def main():
 db=AdvertisingIO();v=db.get(ROOT)
 if v and v['status']=='complete':print('Already collected');return
 if not v:v=dict(status='reading',observed_at=now(),cards={},reviews={},contact_sheets={},errors={},wb_writes=0,telegram_calls=0,model_calls=0);assert db.create(ROOT,v)
 orig=requests.sessions.Session.request;image_hosts=set()
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper()
  ok=(u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname and m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/'))or(u.hostname=='content-api.wildberries.ru'and m=='POST'and u.path=='/content/v2/get/cards/list')or(u.hostname=='discounts-prices-api.wildberries.ru'and m=='GET')or(u.hostname=='marketplace-api.wildberries.ru'and m=='POST'and u.path=='/api/v3/stocks/2126188')or(u.hostname=='feedbacks-api.wildberries.ru'and m=='GET'and u.path=='/api/v1/feedbacks')or(u.hostname in image_hosts and m=='GET')
  assert ok,'Content audit read-only scope';return orig(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def save():db.put(ROOT,copy.deepcopy(v))
 for nm,article in ITEMS.items():
  if str(nm)not in v['cards']:
   r=requests.post('https://content-api.wildberries.ru/content/v2/get/cards/list',headers={'Authorization':db.token},json=dict(settings=dict(cursor=dict(limit=100),filter=dict(textSearch=str(nm),withPhoto=-1))),timeout=(10,50));r.raise_for_status();cs=[c for c in r.json()['cards']if c['nmID']==nm and c['vendorCode'].casefold()==article.casefold()];assert len(cs)==1;v['cards'][str(nm)]=cs[0];save()
  if str(nm)not in v['reviews']:
   try:
    r=requests.get('https://feedbacks-api.wildberries.ru/api/v1/feedbacks',headers={'Authorization':db.token},params=dict(isAnswered='true',take=30,skip=0,order='dateDesc',nmId=nm),timeout=(10,45));r.raise_for_status()
    rows=r.json()['data']['feedbacks']
    v['reviews'][str(nm)]=[dict(text=x.get('text'),pros=x.get('pros'),cons=x.get('cons'),rating=x.get('productValuation'),created_at=x.get('createdDate'),product=x.get('productDetails'))for x in rows];save()
   except Exception as ex:v['errors']['reviews:'+str(nm)]=type(ex).__name__+': '+str(ex)[:100];save()
  if str(nm)not in v['contact_sheets']:
   photos=v['cards'][str(nm)].get('photos',[]);sheet=Image.new('RGB',(1000,((len(photos)+4)//5)*280),'white');draw=ImageDraw.Draw(sheet);failed=[]
   for i,p in enumerate(photos):
    url=p.get('c516x688')or p.get('big');u=urlparse(url);assert u.scheme=='https'and(u.hostname.endswith('wbbasket.ru')or u.hostname.endswith('wildberries.ru'));image_hosts.add(u.hostname)
    try:
     r=requests.get(url,timeout=(10,30));r.raise_for_status();im=Image.open(bio.BytesIO(r.content)).convert('RGB');im.thumbnail((190,250));x=(i%5)*200;y=(i//5)*280;sheet.paste(im,(x+(200-im.width)//2,y+22));draw.text((x+8,y+4),article+' #'+str(i+1),fill='black')
    except Exception as ex:failed.append(dict(index=i+1,error=type(ex).__name__))
   out=bio.BytesIO();sheet.save(out,format='JPEG',quality=82);v['contact_sheets'][str(nm)]=dict(b64=base64.b64encode(out.getvalue()).decode(),photo_count=len(photos),failed=failed);save()
 if 'prices'not in v:
  try:v['prices']=current_prices(db,list(ITEMS));save();v['published']=published_stock(db,v['prices'],list(ITEMS));save()
  except Exception as ex:v['errors']['prices']=str(ex)[:160];save()
 v.update(status='complete',completed_at=now());save();print(json.dumps(dict(status=v['status'],errors=v['errors'],photos={nm:r['photo_count']for nm,r in v['contact_sheets'].items()},wb_writes=0)))
if __name__=='__main__':main()
