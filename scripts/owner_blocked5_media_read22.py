import os,json,time,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner_blocked5_media:2026-11-22:v1'
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();old=io.get(ROOT+':discovery')
 if old and old['status']=='complete':print('Already discovered');return
 v=old or dict(status='reading',created_at=now(),cards={},errors={},wb_writes=0,telegram_calls=0)
 if not old:assert io.create(ROOT+':discovery',v)
 def save():io.put(ROOT+':discovery',v)
 original=requests.sessions.Session.request
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper()
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/')
  elif u.hostname=='seller-analytics-api.wildberries.ru':ok=m=='GET'and u.path=='/api/v1/analytics/banned-products/blocked'
  elif u.hostname=='content-api.wildberries.ru':ok=m=='POST'and u.path=='/content/v2/get/cards/list'
  else:ok=False
  assert ok,'Discovery read only';return original(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 try:
  r=requests.get('https://seller-analytics-api.wildberries.ru/api/v1/analytics/banned-products/blocked',params=dict(sort='nmId',order='asc'),headers={'Authorization':io.token},timeout=(10,55));v['blocked_response_code']=r.status_code
  if not r.ok:v['blocked_error']=r.text[:800];save()
  r.raise_for_status();rows=r.json()['report'];assert len(rows)==5 and len({r['nmId']for r in rows})==5,'Expected exactly5blockedcards'
  v['blocked_report']=rows;save();wanted={r['nmId']:r for r in rows}
  for nm,row in wanted.items():
   if str(nm)in v['cards']:continue
   time.sleep(1);r=requests.post('https://content-api.wildberries.ru/content/v2/get/cards/list',headers={'Authorization':io.token},json={'settings':{'cursor':{'limit':100},'filter':{'textSearch':str(nm),'withPhoto':-1}}},timeout=(10,55));r.raise_for_status();cards=[c for c in r.json()['cards']if c['nmID']==nm];assert len(cards)==1 and cards[0]['vendorCode']==row['vendorCode'],'Blocked identity/contentread mismatch'
   v['cards'][str(nm)]=cards[0];save()
  v.update(status='complete',completed_at=now());save();print(json.dumps(dict(status='complete',cards=[dict(nm=c['nmID'],article=c['vendorCode'],photos=len(c.get('photos')or[]),video=bool(c.get('video')))for c in v['cards'].values()])))
 except Exception as ex:v.update(status='blocked',error=type(ex).__name__+': '+str(ex)[:300]);save();raise
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()

