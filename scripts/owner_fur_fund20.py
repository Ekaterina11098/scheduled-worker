import json,math,time,requests
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from china_advertising_state import AdvertisingIO
ROOT='china_agent:fur_funding:2026-11-20:v1'
CID=42022679
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO()
 prior=io.get(ROOT+':execution')
 if prior: 
  assert prior['status']=='verified','Existing journal: no blind retry'
  print('Already verified');return
 def req(path,method='GET',body=None):
  r=requests.request(method,'https://advert-api.wildberries.ru'+path,headers={'Authorization':io.token},json=body,timeout=45)
  r.raise_for_status();return r.json() if r.content else {}
 def camp():return req('/api/advert/v2/adverts?ids='+str(CID))['adverts'][0]
 def cash():return req('/api/advert/v2/budget','POST',{'advertIds':[CID]})['adverts'][0]['total']
 before=camp();initial=cash();cfg=req('/api/advert/v1/config');wallet=req('/adv/v1/balance')
 assert before['id']==CID and before['currency']==cfg['currency']==wallet['currency']=='CNY'
 assert before['status']==9 and before['settings']['placements']=={'search':False,'recommendations':True}
 expected={2215883910:40,2216111729:38,2216167898:40}
 assert {n['nm_id']:n['bids_kopecks']['recommendations'] for n in before['nm_settings']}==expected
 assert all(n['bids_kopecks']['search']==0 for n in before['nm_settings'])
 # Existing observed 13:37-14:37 consumption 7.60 CNY/hour, conservative flat-24h scenario, not a daily limit.
 daily=7.6*24;reserve=round(daily*3,2)
 amount=max(0,math.ceil((reserve-initial)/50)*50)
 if amount:amount=max(amount,math.ceil(cfg['minTopUp']/100/50)*50)
 assert amount<=550,'Unexpected funding needs: stop for review'
 source=0 if wallet.get('balance',0)>=amount else 1 if wallet.get('net',0)>=amount else None
 assert source is not None
 e=dict(status='preflight',created_at=now(),before=before,before_budget=initial,amount_cny=amount,reserve_cny=reserve,daily_scenario_cny=daily,scenario_basis='Observed 13:37-14:37 spend7.60/hour x24; not guaranteed future spend or daily cap',owner_instruction='Fund continuation of current fur experiment; no search or bid changes',telegram_calls=0,model_calls=0,wb_writes=0)
 assert io.create(ROOT+':execution',e)
 def save():io.put(ROOT+':execution',e)
 def same(after):return all(after[k]==before[k] for k in ('id','status','currency','settings','nm_settings'))
 try:
  assert same(camp()) and cash()<=initial+1,'State or cash changed; do not duplicate'
  if amount:
   e.update(status='submitting',request=dict(path='/adv/v1/budget/deposit?id='+str(CID),body=dict(sum=amount,type=source)));save()
   try:e['response']=req(e['request']['path'],'POST',e['request']['body'])
   except Exception:e['status']='uncertain';save();raise
   e.update(status='accepted',wb_writes=1);save()
  for i in range(8):
   after=camp();balance=cash()
   if same(after) and balance>=initial+amount-2:break
   time.sleep(3)
  else:raise ValueError('Funding readback unresolved; do not repeat deposit')
  e.update(status='verified',after=after,after_budget=balance,verified_at=now());save()
  registry=io.get('china_agent:verified_campaign_state:v1')or{};registry[str(CID)]=ROOT+':execution';io.put('china_agent:verified_campaign_state:v1',registry)
 except Exception as ex:
  if e['status']!='verified':e.update(status='uncertain' if e['status']in('submitting','accepted','uncertain') else 'blocked',error=str(ex)[:250]);save()
  raise
 print(json.dumps({k:e[k]for k in('status','before_budget','after_budget','amount_cny','reserve_cny','wb_writes','verified_at')}))
if __name__=='__main__':main()
