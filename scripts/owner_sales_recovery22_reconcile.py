"""Read-only reconcile exact recovery22 package; zero marketplace mutations."""
import copy,json,time
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
from china_advertising_v2 import http
from owner_sales_recovery22_apply import ROOT,norm,expected_campaign
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();e=io.get(ROOT+':execution');assert e
 audit=dict(status='reading',started_at=now(),reads=[],diffs={},wb_writes=0,telegram_calls=0,model_calls=0)
 ids=sorted({g['cid']for g in e['groups']}|{42088552})
 key=ROOT+':reconcile'
 def save():io.put(key,audit)if io.get(key)else io.create(key,audit)
 for attempt in range(3):
  rows=http(io,'/api/advert/v2/adverts?ids='+','.join(map(str,ids))+'&readback_nonce='+str(time.time_ns()))['adverts']
  assert {c['id']for c in rows}==set(ids)
  audit['reads'].append(dict(observed_at=now(),campaigns=rows));save();time.sleep(3)
 for g in e['groups']:
  cid=g['cid'];expected=g.get('after')or expected_campaign(g['before'],g['spec'],status=7 if g['spec'].get('archive')else None)
  reads=[next(c for c in r['campaigns']if c['id']==cid)for r in audit['reads']]
  if all(norm(c)==norm(expected)for c in reads):
   g.update(status='verified',after=reads[-1],verified_at=g.get('verified_at')or now(),read_only_reconciled_at=now())
   e['errors'].pop('campaign:'+str(cid),None);e['errors'].pop('final:'+str(cid),None)
   child=ROOT+':campaign:'+str(cid);value=dict(g,id=cid)
   io.put(child,value)if io.get(child)else io.create(child,value)
   reg=io.get('china_agent:verified_campaign_state:v1')or{};reg[str(cid)]=child;io.put('china_agent:verified_campaign_state:v1',reg)
  else:
   actual=reads[-1];wanted=norm(expected);got=norm(actual)
   audit['diffs'][str(cid)]={k:dict(expected=wanted[k],actual=got[k])for k in wanted if wanted[k]!=got[k]}
 protected=[next(c for c in r['campaigns']if c['id']==42088552)for r in audit['reads']]
 assert all(norm(c)==norm(e['preflight']['protected'])for c in protected)
 e['package_readback']=audit['reads'][-1]['campaigns'];e['read_only_reconciliation_key']=key
 e['status']='verified'if all(g['status']=='verified'for g in e['groups'])and all(x['status']=='applied'for x in e['items'])and all(x['status']=='verified'for x in e['funding'])else'partial_attention'
 e['completed_at']=now();io.put(ROOT+':execution',e)
 audit.update(status='complete',completed_at=now(),execution_status=e['status']);save()
 print(json.dumps(dict(status=e['status'],diff_campaigns=list(audit['diffs']),wb_writes=0)))
if __name__=='__main__':main()
