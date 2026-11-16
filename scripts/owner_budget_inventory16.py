"""One explicit owner-requested cabinet budget inventory, read-only marketplace."""
import os,json,time
from datetime import datetime,timezone
import requests
ROOT='china_agent:owner_funding_fix:2026-11-16:v1'
def collect(io,slot):
 from china_cloud_cost_control import stamp
 def req(path,method='GET',body=None):
  assert(path.split('?')[0],method)in {('/adv/v1/promotion/count','GET'),('/api/advert/v2/adverts','GET'),('/api/advert/v2/budget','POST')}
  time.sleep(1.5)
  r=requests.request(method,'https://advert-api.wildberries.ru'+path,headers={'Authorization':os.environ['WB_TOKEN_3']},json=body,timeout=50)
  if not r.ok:raise RuntimeError('Budget inventory WB HTTP '+str(r.status_code))
  return r.json()
 inventory=req('/adv/v1/promotion/count');ids={}
 for group in inventory.get('adverts',[]):
  for a in group.get('advert_list',[]):
   if a['advertId']in ids:raise ValueError('Duplicate campaign in inventory')
   ids[a['advertId']]=dict(status=group['status'],type=group['type'])
 live={};budgets={}
 wanted=sorted(cid for cid,v in ids.items()if v['status']in(4,9,11))
 for start in range(0,len(wanted),50):
  chunk=wanted[start:start+50];data=req('/api/advert/v2/adverts?ids='+','.join(map(str,chunk)))['adverts']
  assert {x['id']for x in data}==set(chunk)
  for x in data:
   assert x['currency']=='CNY';live[x['id']]=x
 active=sorted(cid for cid,x in live.items()if x['status']in(9,11))
 for start in range(0,len(active),50):
  chunk=active[start:start+50];data=req('/api/advert/v2/budget','POST',dict(advertIds=chunk))['adverts']
  assert {x['advertId']for x in data}==set(chunk)
  for x in data:
   assert x['currency']=='CNY' and type(x['total'])in(int,float);budgets[x['advertId']]=x
 reference=io.get(ROOT+':reserve_reference');refs={int(x['id']):x for x in reference['rows']}
 rows=[]
 for cid,meta in sorted(ids.items()):
  state=live.get(cid,{});b=budgets.get(cid);ref=refs.get(cid,{})
  amount=b['total']if b else None;need=ref.get('budget_reference_need');avg=ref.get('budget_average_daily')
  rows.append(dict(id=cid,name=state.get('name')or ref.get('name'),status=state.get('status',meta['status']),balance_cny=amount,three_day_reference_cny=need,completed_days=ref.get('budget_days'),reference_average_daily_cny=avg,estimated_days_remaining=amount/avg if type(amount)in(int,float)and type(avg)in(int,float)and avg>0 else None,three_day_gap_cny=max(0,need-amount)if type(need)in(int,float)and type(amount)in(int,float)else None,reference_decision=ref.get('budget_audit_state'),reference_economics=ref.get('budget_economics_status'),unknown_reference=cid not in refs))
 out=dict(status='complete',cabinet='token_3',observed_at=stamp(),inventory=inventory,states=list(live.values()),budgets=list(budgets.values()),rows=rows,wb_writes=0,telegram_calls=0,model_calls=0,reference_day=reference['day'])
 if io.get(ROOT+':audit:'+slot):raise ValueError('Audit slot already recorded; no duplicate read')
 io.create(ROOT+':audit:'+slot,out)
 print(json.dumps(dict(audit_slot=slot,campaigns=len(rows),active=sum(x['status']==9 for x in rows),paused=sum(x['status']==11 for x in rows),WB_writes=0)))
 return out
if __name__=='__main__':
 from china_cloud_cost_control import Cache
 collect(Cache(),'before-recovery')

