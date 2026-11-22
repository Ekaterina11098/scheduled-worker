import copy,json,time,requests,os
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner_blocked5_media:2026-11-22:v1'
def now():return datetime.now(timezone.utc).isoformat()
def stable(c):return {k:v for k,v in c.items()if k not in('photos','video','updatedAt')}
def main():
 io=AdvertisingIO();a=io.get(ROOT+':approval');d=io.get(ROOT+':discovery');assert a['status']=='approved'and a['owner_id']==5122667182 and d['status']=='complete';assert len(a['nm_ids'])==5 and set(a['nm_ids'])=={r['nmId']for r in d['blocked_report']}
 assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
 e=io.get(ROOT+':execution')
 if e and e['status']=='verified':print('Already verified');return
 assert e is None,'Existing media operations must not replay'
 e=dict(status='preflight',created_at=now(),items=[],wb_writes=0,telegram_calls=0,model_calls=0,backup_key=ROOT+':discovery');assert io.create(ROOT+':execution',e)
 def save():io.put(ROOT+':execution',copy.deepcopy(e))
 original=requests.sessions.Session.request;allowed=None
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper()
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/')
  elif u.hostname=='seller-analytics-api.wildberries.ru':ok=m=='GET'and u.path=='/api/v1/analytics/banned-products/blocked'
  elif u.hostname=='content-api.wildberries.ru':ok=m=='POST'and u.path=='/content/v2/get/cards/list'or allowed is not None and(m,u.path,kw.get('json'))==allowed
  else:ok=False
  assert ok,'Only blocked5 media clearing permitted';return original(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def card(nm):
  time.sleep(1);r=requests.post('https://content-api.wildberries.ru/content/v2/get/cards/list',headers={'Authorization':io.token,'Cache-Control':'no-cache,no-store'},json={'settings':{'cursor':{'limit':100},'filter':{'textSearch':str(nm),'withPhoto':-1}}},timeout=(10,55));r.raise_for_status();rows=[c for c in r.json()['cards']if c['nmID']==nm];assert len(rows)==1;return rows[0]
 try:
  r=requests.get('https://seller-analytics-api.wildberries.ru/api/v1/analytics/banned-products/blocked',params=dict(sort='nmId',order='asc'),headers={'Authorization':io.token},timeout=(10,55));r.raise_for_status();assert {x['nmId']for x in r.json()['report']}==set(a['nm_ids']),'Blocked set changed'
  for nm in a['nm_ids']:
   before=card(nm);assert before['vendorCode']==d['cards'][str(nm)]['vendorCode'];item=dict(nm_id=nm,article=before['vendorCode'],before=before,status='preflight');e['items'].append(item);save()
  for item in e['items']:
   nm=item['nm_id'];before=item['before'];assert card(nm)==before,'Card changed since preflight'
   if before.get('photos')or before.get('video'):
    body=dict(nmId=nm,data=[]);item['operation']=dict(status='submitting',body=body,submitted_at=now());save();allowed=('POST','/content/v3/media/save',body)
    try:
     r=requests.post('https://content-api.wildberries.ru/content/v3/media/save',headers={'Authorization':io.token},json=body,timeout=(10,60));item['operation'].update(http_status=r.status_code,response=r.text[:1400]);save()
     if not r.ok:item['operation']['status']='rejected';save();r.raise_for_status()
     j=r.json();assert not j.get('error'),str(j)[:600];item['operation']['status']='accepted';e['wb_writes']+=1;save()
    except Exception:
     if item['operation']['status']=='submitting':item['operation']['status']='uncertain';save()
     raise
    finally:allowed=None
   streak=[]
   for _ in range(12):
    after=card(nm);item['last_read']=after;save()
    if not(after.get('photos')or after.get('video'))and stable(after)==stable(before):streak.append(after)
    else:streak=[]
    if len(streak)==2:break
    time.sleep(5)
   assert len(streak)==2,'Media deletion not confirmed; no write replay'
   item.update(status='verified',after=streak[-1],verified_at=now());save()
  e.update(status='verified',completed_at=now());save();print(json.dumps(dict(status='verified',cards=5,wb_writes=e['wb_writes'],telegram_calls=0)))
 except Exception as ex:e.update(status='attention_required',error=type(ex).__name__+': '+str(ex)[:500]);save();raise
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()

