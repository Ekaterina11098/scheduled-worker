"""Fresh read-only campaign/minimum checks for the proposed recovery, not execution."""
import os,json,time,collections,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner_sales_revival:2026-11-25:v1'
def main():
 db=AdvertisingIO();key=ROOT+':quotes-v3';old=db.get(key)
 if old:raise SystemExit('Existing quote checkpoint retained; no repeat')
 prior=db.get(ROOT+':quotes-v2');assert prior and prior.get('campaigns') and prior.get('config')
 plan=db.get(ROOT+':plan');assert plan['status']=='proposal_not_executed'and plan['target_drr_pct']==8
 snapshot=db.get('china_agent:hourly_sales_api:v1:snapshot:2026-11-25T10:MSK');known=snapshot['advertising']['campaigns']
 group=collections.defaultdict(set);items=plan['raises']+plan['additions'];scope={41967612}
 for a in plan['raises']:scope.add(a['campaign_id']);group[(a['campaign_id'],a['placement'])].add(a['nm_id'])
 origins={}
 for a in plan['additions']:
  nm=a['nm'];origin=next((int(cid)for cid,c in known.items()if c['status']==9 and int(cid)!=42088552 and any(n['nm_id']==nm for n in c['nm_settings'])),None)
  if origin:scope.add(origin);group[(origin,'search')].add(nm);origins[nm]=dict(cid=origin,nm=nm,basis='exact_product')
  else:
   ref=known['41967612']['nm_settings'][0]['nm_id'];group[(41967612,'search')].add(ref);origins[nm]=dict(cid=41967612,nm=ref,basis='same_subject_representative')
 out=dict(status='reading',observed_at=datetime.now(timezone.utc).isoformat(),quotes={},errors={},origins=origins,wb_writes=0,telegram_calls=0,model_calls=0)
 assert db.create(key,out)
 def save():db.put(key,json.loads(json.dumps(out)))
 orig=requests.sessions.Session.request
 def guard(s,method,url,*a,**kw):
  u=urlparse(url);method=method.upper();ok=u.hostname==urlparse(db.url).hostname and u.path.startswith('/rest/v1/')and method in('GET','POST','PATCH')
  if u.hostname=='advert-api.wildberries.ru':ok=(method=='GET'and u.path in('/api/advert/v2/adverts','/api/advert/v1/config'))or(method=='POST'and u.path=='/api/advert/v1/bids/min')
  if not ok:raise ValueError('Read-only quote guard')
  return orig(s,method,url,*a,**kw)
 requests.sessions.Session.request=guard
 def req(path,method='GET',body=None):
  r=requests.request(method,'https://advert-api.wildberries.ru'+path,headers={'Authorization':db.token},json=body,timeout=50)
  if not r.ok:raise ValueError('Quote API HTTP '+str(r.status_code))
  return r.json()
 states=prior['campaigns'];assert {s['id']for s in states}==scope
 out['campaigns']=states;out['config']=prior['config'];assert out['config']['currency']=='CNY';save()
 target=next(s for s in states if s['id']==41967612)
 assert target['status']==9 and target['settings']['placements']['search']and len(target['nm_settings'])+len(plan['additions'])<=50
 existing={n['nm_id']for n in target['nm_settings']};assert not existing&{a['nm']for a in plan['additions']}
 for(cid,zone),nms in group.items():
  try:
   time.sleep(3.2);result=req('/api/advert/v1/bids/min','POST',dict(advert_id=cid,nm_ids=sorted(nms),payment_type='cpc',placement_types=['search'if zone=='search'else'recommendation']))
   vals={r['nm_id']:next(b['value']for b in r['bids']if b['currency']=='CNY'and b['type']==('search'if zone=='search'else'recommendation'))for r in result['bids']}
   assert set(vals)==nms;out['quotes'][str(cid)+':'+zone]=dict(raw=result,values=vals)
  except Exception as e:out['errors'][str(cid)+':'+zone]=str(e)if isinstance(e,ValueError)else type(e).__name__
  save()
 out.update(status='complete'if not out['errors']else'partial',completed_at=datetime.now(timezone.utc).isoformat());save()
 print(json.dumps(dict(status=out['status'],quote_groups=len(group),error_groups=len(out['errors']),wb_writes=0)))
if __name__=='__main__':main()

