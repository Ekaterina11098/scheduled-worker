"""Owner requested transfer candidates. Read-only exact inventory and target cash/traffic."""
import json,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_advertising_v2 import http,save
ROOT='china_agent:owner_363_transfer:2026-11-15:v1'
def main():
 io=AdvertisingIO();old=requests.sessions.Session.request
 def guard(session,method,url,**kw):
  p=urlparse(url);m=method.upper()
  if p.hostname=='api.telegram.org'or 'openai'in(p.hostname or''):raise ValueError('No Telegram/model calls')
  if (p.hostname or'').endswith('wildberries.ru')and not((m=='GET'and p.path in ['/adv/v1/promotion/count','/api/advert/v2/adverts','/adv/v3/fullstats','/api/advert/v1/config'])or(m=='POST'and p.path in ['/api/advert/v2/budget','/api/advert/v1/bids/min'])):raise ValueError('WB mutation forbidden')
  return old(session,method,url,**kw)
 requests.sessions.Session.request=guard
 v=io.get(ROOT)or dict(status='collecting',wb_writes=0,model_calls=0,telegram_calls=0,grants_action_permission=False)
 def put():save(io,ROOT,json.loads(json.dumps(v)))
 if v.get('status')=='complete':return
 source=io.get('china_agent:owner_363_review:2026-11-15:v1');assert source['status']=='complete'
 age=(datetime.now(timezone.utc)-datetime.fromisoformat(source['observed_at'])).total_seconds();assert 0<=age<=7200,'Refresh scoped economics before using'
 members={n['nm_id']for n in source['campaign']['nm_settings']}
 if 'inventory'not in v:v['inventory']=http(io,'/adv/v1/promotion/count');put()
 ids=sorted({r['advertId']for g in v['inventory']['adverts']if g['status']in(9,11)for r in g.get('advert_list',[])})
 if 'campaigns'not in v:
  assert len(ids)<=50
  v['campaigns']=http(io,'/api/advert/v2/adverts?ids='+','.join(map(str,ids)))['adverts'];assert {c['id']for c in v['campaigns']}==set(ids);put()
 target_ids=[40933588,41055480,41270309,41332083,41298169]
 if 'budgets'not in v:v['budgets']=http(io,'/api/advert/v2/budget','POST',dict(advertIds=target_ids));put()
 if 'stats'not in v:
  raw=http(io,'/adv/v3/fullstats?ids='+','.join(map(str,target_ids))+'&beginDate=2026-11-11&endDate=2026-11-14')
  assert {c['advertId']for c in raw}==set(target_ids)
  v['stats']=[]
  for c in raw:
   cp=dict(advertId=c['advertId'],days=[])
   for d in c.get('days',[]):
    cp['days'].append(dict(date=d['date'],sum=d['sum'],sum_price=d['sum_price'],clicks=d['clicks'],orders=d['orders'],views=d['views'],apps=[dict(nms=[r for r in a['nms']if r['nmId']in members])for a in d.get('apps',[])]))
   v['stats'].append(cp)
  put()
 if 'quotes'not in v:
  v['quotes']={}
  for cid in [40933588,41055480,41270309,41332083]:
   cp=next(c for c in v['campaigns']if c['id']==cid);assert cp['status']==9 and cp['currency']=='CNY'and cp['bid_type']=='manual'and cp['settings']['payment_type']=='cpc'and cp['restrictions']['can_change_nms']
   assert {n['subject']['id']for n in cp['nm_settings']}=={50}
   placement='search'if cp['settings']['placements']['search']else'recommendation'
   representative=cp['nm_settings'][0]['nm_id']
   v['quotes'][str(cid)]=dict(quote_basis='same_subject_cpc_placement_owner_verified_v1',representative_nm=representative,subject_id=50,raw=http(io,'/api/advert/v1/bids/min','POST',dict(advert_id=cid,nm_ids=[representative],payment_type='cpc',placement_types=[placement])))
   put()
 v.update(status='complete',observed_at=datetime.now(timezone.utc).isoformat(),economics_source_key='china_agent:owner_363_review:2026-11-15:v1',duplicates={str(nm):[c['id']for c in v['campaigns']if c['status']==9 and any(n['nm_id']==nm for n in c['nm_settings'])]for nm in sorted(members)})
 put();print('Completed scoped inventory, duplicate, target budget/statistics/minimum checks; no writes/model/TG')
if __name__=='__main__':main()
