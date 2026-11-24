import os,json,requests,time,copy
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner_stock_without_ads:2026-11-24:v1'
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();base=io.get(ROOT);assert base['status']=='complete'
 key=ROOT+':content_reconciliation';v=io.get(key)
 if v and v.get('status')=='complete':return
 if not v:v=dict(status='reading',cards=[],cursor={'limit':100},pages=0,wb_writes=0,telegram_calls=0,observed_at=now());assert io.create(key,v)
 orig=requests.sessions.Session.request
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();ok=(u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname and m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/'))or(u.hostname=='content-api.wildberries.ru'and m=='POST'and u.path=='/content/v2/get/cards/list')
  assert ok;return orig(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 while not v.get('read_complete'):
  assert v['pages']<30
  body={'settings':{'cursor':v['cursor'],'filter':{'withPhoto':-1}}}
  time.sleep(1);r=requests.post('https://content-api.wildberries.ru/content/v2/get/cards/list',headers={'Authorization':io.token},json=body,timeout=(10,55));r.raise_for_status();j=r.json();cards=j['cards'];assert isinstance(cards,list)
  v['cards']+=[dict(nm_id=c['nmID'],article=c['vendorCode'],title=c.get('title'),photo_count=len(c.get('photos')or[]))for c in cards];v['pages']+=1
  if len(cards)<100:v['read_complete']=True
  else:
   cursor=j['cursor'];assert cursor.get('updatedAt')and cursor.get('nmID');v['cursor']={'limit':100,'updatedAt':cursor['updatedAt'],'nmID':cursor['nmID']}
  io.put(key,copy.deepcopy(v))
 assert len({x['nm_id']for x in v['cards']})==len(v['cards'])
 by={}
 for c in v['cards']:by.setdefault(c['article'].strip().casefold(),[]).append(c)
 members={}
 for c in base['campaigns']['rows']:
  for n in c['nm_settings']:members.setdefault(n['nm_id'],[]).append(dict(cid=c['id'],status=c['status'],name=c['settings']['name']))
 reconciled=[];missing=[];ambiguous=[]
 for x in base['result']['unmapped_msk_products']:
  matches=by.get(x['article'].strip().casefold(),[])
  if len(matches)>1:ambiguous.append(dict(x,matches=matches));continue
  if not matches:missing.append(x);continue
  c=matches[0];reconciled.append(dict(x,nm_id=c['nm_id'],wb_article=c['article'],photo_count=c['photo_count'],campaigns=members.get(c['nm_id'],[]),outside_all_current_campaigns=not bool(members.get(c['nm_id']))))
 v.update(status='complete',completed_at=now(),reconciled=reconciled,not_in_current_content=missing,ambiguous=ambiguous)
 io.put(key,v);print(json.dumps({'status':v['status'],'pages':v['pages'],'cards':len(v['cards']),'reconciled':len(reconciled),'missing':len(missing),'ambiguous':len(ambiguous)}))
if __name__=='__main__':main()
