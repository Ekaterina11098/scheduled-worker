import copy,json,time,requests
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
from owner_growth_cuts23 import ROOT,norm
def main():
 io=AdvertisingIO();e=io.get(ROOT+':execution');assert e and e['wb_writes']==4
 rounds=[]
 if not io.get(ROOT+':reconciliation'):assert io.create(ROOT+':reconciliation',dict(status='reading',rounds=[],wb_writes=0))
 for i in range(3):
  snapshot={}
  for cid in (40933588,41270309,41325622,41332083,42088552):
   time.sleep(1.5);r=requests.get('https://advert-api.wildberries.ru/api/advert/v2/adverts',params={'ids':str(cid),'owner_read':time.time_ns()},headers={'Authorization':io.token,'Cache-Control':'no-cache,no-store,max-age=0','Pragma':'no-cache'},timeout=(10,55));r.raise_for_status();c=r.json()['adverts'];assert len(c)==1 and c[0]['id']==cid;snapshot[str(cid)]=dict(state=c[0],date=r.headers.get('Date'),age=r.headers.get('Age'))
  rounds.append(snapshot);io.put(ROOT+':reconciliation',dict(status='reading',rounds=rounds,wb_writes=0));time.sleep(6)
 for cid,g in e['groups'].items():
  matches=all(norm(x[cid]['state'])==norm(g['expected'])for x in rounds)
  g['readonly_reconciliation']=[x[cid]for x in rounds]
  if matches:
   g.update(status='verified',after=rounds[-1][cid]['state'],verified_at=datetime.now(timezone.utc).isoformat());g.pop('error',None);g['operation']['status']='verified';key=ROOT+':campaign:'+cid
   if io.get(key):io.put(key,dict(g,id=int(cid)))
   else:io.create(key,dict(g,id=int(cid)))
   reg=io.get('china_agent:verified_campaign_state:v1')or{};reg[cid]=key;io.put('china_agent:verified_campaign_state:v1',reg)
 e['protected_unchanged']=all(norm(x['42088552']['state'])==norm(e['protected_before'])for x in rounds);e['status']='verified'if all(g['status']=='verified'for g in e['groups'].values())and e['protected_unchanged']else'partial_attention';e['reconciled_at']=datetime.now(timezone.utc).isoformat();io.put(ROOT+':execution',e);io.put(ROOT+':reconciliation',dict(status='complete',rounds=rounds,wb_writes=0));print(json.dumps(dict(status=e['status'],groups={cid:g['status']for cid,g in e['groups'].items()})))
if __name__=='__main__':main()