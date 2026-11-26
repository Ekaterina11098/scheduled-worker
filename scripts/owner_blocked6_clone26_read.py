import os,json,time,requests,re
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner_blocked6_clone26:v1'
TARGET={1473243449:'539-AdaBag-coffee',1473243239:'542-CelineaBag-darkbrown',1473244992:'502-AlessiaBag-cream',1473244989:'38-GretaBag-green',1473244985:'042-EvaBag-brown',1473243829:'674-NoelBag-pink'}
def stamp():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();assert not io.get(ROOT+':discovery'),'Existing discovery retained'
 out=dict(status='reading',started_at=stamp(),cards={},wb_writes=0,telegram_calls=0,model_calls=0);assert io.create(ROOT+':discovery',out)
 def save():io.put(ROOT+':discovery',json.loads(json.dumps(out)))
 original=requests.sessions.Session.request
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();ok=False
  if u.hostname==urlparse(io.url).hostname:ok=m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/')
  elif u.hostname=='content-api.wildberries.ru':ok=m=='POST'and u.path=='/content/v2/get/cards/list'or m=='GET'and u.path=='/content/v2/cards/limits'
  elif u.hostname=='seller-analytics-api.wildberries.ru':ok=m=='GET'and u.path=='/api/v1/analytics/banned-products/blocked'
  elif u.hostname=='dev.wildberries.ru':ok=m=='GET'
  assert ok,'Discovery read only';return original(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 try:
  headers={'Authorization':io.token}
  r=requests.get('https://seller-analytics-api.wildberries.ru/api/v1/analytics/banned-products/blocked',params=dict(sort='nmId',order='asc'),headers=headers,timeout=(10,50));r.raise_for_status();out['blocked_report']=r.json()['report'];assert all(any(x['nmId']==nm for x in out['blocked_report'])for nm in TARGET);save()
  for nm,article in TARGET.items():
   time.sleep(1);r=requests.post('https://content-api.wildberries.ru/content/v2/get/cards/list',headers=headers,json={'settings':{'cursor':{'limit':100},'filter':{'textSearch':article,'withPhoto':-1}}},timeout=(10,50));r.raise_for_status();allcards=r.json()['cards'];out.setdefault('matching_articles',{})[article]=[{'nmID':x['nmID'],'vendorCode':x['vendorCode']}for x in allcards];cards=[x for x in allcards if x['nmID']==nm];assert len(cards)==1 and cards[0]['vendorCode']==article;out['cards'][str(nm)]=cards[0];save()
  r=requests.get('https://content-api.wildberries.ru/content/v2/cards/limits',headers=headers,timeout=(10,40));out['limits']={'http':r.status_code,'response':r.json()};save()
  try:
   r=requests.get('https://dev.wildberries.ru/openapi/work-with-products',timeout=(10,40));out['docs_http']=r.status_code
   if r.ok:
    text=r.text;out['docs_size']=len(text);out['docs_fragments']=[]
    for word in ['Баркод уже','баркод уже','уникаль','/content/v2/cards/upload','/content/v2/cards/update']:
     positions=[m.start()for m in re.finditer(re.escape(word),text)];out['docs_fragments'] +=[dict(word=word,text=text[max(0,i-500):i+3500])for i in positions[:4]]
    out['docs_links']=[x for x in re.findall(r'(?:src|href)=[\"\x27]([^\"\x27]+)',text)if any(w in x for w in ['swagger','yaml','openapi','json'])][:30]
   save()
  except Exception as ex:out['docs_error']=type(ex).__name__;save()
  out.update(status='complete',completed_at=stamp());save();print(json.dumps(dict(status='complete',cards=6,wb_writes=0)))
 except Exception as ex:out.update(status='blocked',reason=type(ex).__name__+': '+str(ex)[:250]);save();raise
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()

