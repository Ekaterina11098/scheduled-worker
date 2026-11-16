"""Read-only final reconciliation of already verified owner writes; no mutation replay."""
import os,json,time,copy
from datetime import datetime,timezone
from urllib.parse import urlparse
import requests
from china_cloud_cost_control import Cache
ROOT='china_agent:owner_evening_four:2026-11-16:v1'
DST=40933588;SRC=41298169;ADD=1473243903
REMOVE={DST:{1473243448,1473245505},SRC:{1473244341}}
def stamp():return datetime.now(timezone.utc).isoformat()
def keyed(c):return{n['nm_id']:n for n in c['nm_settings']}
def semantic(n):return dict(nm_id=n['nm_id'],subject_id=n['subject']['id'],bids=n['bids_kopecks'])
def checks(e,campaigns):
 errors=[];differences=[]
 for cid,c in campaigns.items():
  before=e['preflight']['before'][str(cid)];old=keyed(before);new=keyed(c)
  wanted=(set(old)|({ADD}if cid==DST else set()))-REMOVE[cid]
  for field in('status','currency','bid_type','settings'):
   if c[field]!=before[field]:errors.append(str(cid)+': changed '+field)
  if set(new)!=wanted:errors.append(str(cid)+': member set mismatch')
  for nm in set(old)&set(new)-REMOVE[cid]:
   if nm==ADD and cid==DST:continue
   if semantic(old[nm])!=semantic(new[nm]):errors.append(str(cid)+': other SKU changed '+str(nm))
   elif old[nm]!=new[nm]:differences.append(dict(campaign=cid,nm_id=nm,before=old[nm],after=new[nm],kind='nonsemantic_metadata'))
  if cid==DST and(ADD not in new or new[ADD]['subject']['id']!=50 or new[ADD]['bids_kopecks'].get('recommendations')!=28):errors.append('534 exact bid/category not verified')
 return errors,differences
def main():
 db=Cache();e=db.get(ROOT+':execution');assert e['wb_writes']in(2,3)and len(e['items'])==2 and all(x['status']=='verified'for x in e['items'])and all(s['status']=='verified'for s in e['steps'])
 key=ROOT+':final_reconciliation';assert db.create(key,dict(status='reading',at=stamp(),wb_writes=0,telegram_calls=0))
 samples=[];final=None
 for attempt in range(8):
  r=requests.get('https://advert-api.wildberries.ru/api/advert/v2/adverts',params={'ids':str(DST)+','+str(SRC)},headers={'Authorization':os.environ['WB_TOKEN_3']},timeout=(10,45));r.raise_for_status();rows=r.json()['adverts'];assert {x['id']for x in rows}=={DST,SRC}
  current={x['id']:x for x in rows};errors,metadata=checks(e,current);samples.append(dict(at=stamp(),errors=errors,metadata=metadata,raw=current))
  db.put(key,dict(status='verified'if not errors else'reading',samples=samples,wb_writes=0,telegram_calls=0,observed_at=stamp()))
  if not errors:final=current;break
  if attempt<7:time.sleep(5)
 if final is None:raise RuntimeError('Final owner state remains inconsistent; no WB writes made')
 original_reason=e.get('reason');e.update(status='verified',verified_at=stamp(),final_readback=final,final_reconciliation_key=key,prior_final_check_error=original_reason,telegram_calls=0,model_calls=0,funded_cny=0);e.pop('reason',None)
 for item in e['items']:
  cid=item['campaign_id'];item['after']=final[cid];item['final_verified_at']=e['verified_at'];child=item['receipt_key'];receipt=db.get(child);assert receipt['status']=='verified';receipt.update(after=final[cid],final_verified_at=e['verified_at']);db.put(child,receipt)
 db.put(ROOT+':execution',e)
 print(json.dumps(dict(status='verified',original_wb_writes=e['wb_writes'],new_wb_writes=0,telegram_calls=0,metadata_changes=len(samples[-1]['metadata']))))
if __name__=='__main__':
 old=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);method=method.upper()
  ok=(u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname and u.path.startswith('/rest/v1/')and method in('GET','POST','PATCH'))or(u.hostname=='advert-api.wildberries.ru'and method=='GET'and u.path=='/api/advert/v2/adverts')
  assert ok,'Final verification is strictly read-only for WB, no Telegram'
  return old(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 try:main()
 finally:requests.sessions.Session.request=old

