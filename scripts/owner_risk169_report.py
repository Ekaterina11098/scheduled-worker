"""Completed-day 41298169 cost proposals; preserve justified additions, no WB execution."""
import copy
from datetime import datetime,timezone
CID=41298169;ROOT='china_agent:owner_169_cost_review:2026-11-16:v1';SOURCE=None
EXPECTED={1473244337:('ad_set_bid',35,28),1473243900:('ad_set_bid',30,28),1473243890:('ad_exclude_sku',28,None),1473242754:('ad_exclude_sku',28,None)}

def review(current,prior,inputs):
 from china_advertising_economic_review import apply
 out=copy.deepcopy(current);original=next(c for c in out['campaigns']if c['id']==CID);part=copy.deepcopy(out)
 part['campaigns']=[copy.deepcopy(original)];part['campaigns'][0]['focus']=[r for r in original['focus']if r['nm']in EXPECTED]
 assert {r['nm']for r in part['campaigns'][0]['focus']}==set(EXPECTED)
 assert all(not r.get('pending_first_day')and inputs['first_full_days'][str(r['nm'])]<='2026-11-15'for r in part['campaigns'][0]['focus'])
 raw=copy.deepcopy(inputs['stats'])
 for d in raw['days']:
  for app in d['apps']:app['nms']=[n for n in app['nms']if n['nmId']in EXPECTED]
 source=dict(catalogue=dict(rows=inputs['catalogue']),economics=dict(rows=inputs['economics']),executions=[],batches={'0':dict(campaigns=dict(adverts=[inputs['campaign']]),stats=[raw])})
 minima={str(CID)+':'+str(n):28 for n in EXPECTED}
 checked=apply(part,source,minima);rows={r['nm']:r for r in checked['campaigns'][0]['focus']if r.get('action')}
 assert set(rows)==set(EXPECTED)
 for nm,(kind,old,target)in EXPECTED.items():
  a=rows[nm]['action'];assert(a['kind'],a['old_minor'],a.get('target_minor'))==(kind,old,target)
 original['focus']=[copy.deepcopy(rows.get(r['nm'],r))for r in original['focus']];original['attention']=[r for r in original['focus']if r.get('action')]
 for nm,r in rows.items():
  key='reduce'if r['action']['kind']=='ad_set_bid'else'exclude';section=out['recommendation_directions'][key]
  assert not any(x.get('nm_id')==nm and x.get('campaign_id')==CID for x in section['rows'])
  section['rows'].append(dict(article=r['article'],campaign_id=CID,nm_id=nm,action=r['action'],decision=r['decision'],period=r['period'],evaluation_days=(r.get('comparison')or{}).get('to_days',[]),economics=r['economics'],ready=True))
 # The owner's current clarification permits sound additions alongside cost cuts.
 # Restore the two existing checked umbrella proposals; never recreate a return ban.
 c=next(c for c in out['campaigns']if c['id']==41325637)
 candidates=[r for pc in prior['campaigns']if pc['id']==41325637 for r in pc['focus']if(r.get('action')or{}).get('kind')=='ad_add_sku']
 assert len(candidates)==2
 for r in candidates:
  if any(x['nm']==r['nm']and x.get('action')for x in c['focus']):continue
  e=r['action']['growth_evidence'];assert e['expected_margin_before_ads_cny']>0 and e['stock_free']>0 and e['published_stock']>0
  assert 0<=(datetime.now(timezone.utc)-datetime.fromisoformat(e['observed_at'])).total_seconds()<24*3600
  c['focus'].append(copy.deepcopy(r))
  row=next(x for x in prior['recommendation_directions']['add']['rows']if x.get('nm_id')==r['nm']and x.get('campaign_id')==41325637 and x.get('ready'))
  out['recommendation_directions']['add']['rows'].append(copy.deepcopy(row))
 c['attention']=[r for r in c['focus']if r.get('action')]
 for section in out['recommendation_directions'].values():section.update(count=len(section['rows']),ready_count=sum(r.get('ready')is True for r in section['rows']))
 out['owner_169_cost_review']=dict(campaign_id=CID,proposals=4,keep_667=True,restore_checked_umbrella_additions=True,wb_writes=0)
 out.get('owner_umbrella_target5',{})['remove_new_additions']=False
 return out

def preflight(io,bundle):
 global SOURCE
 import owner_risk16_restore as publish
 from china_advertising_v2 import http
 SOURCE=io.get(ROOT+':input');assert SOURCE['period_to']=='2026-11-15'
 live=http(io,'/api/advert/v2/adverts?ids=41298169,41325637')['adverts'];states={c['id']:c for c in live};assert set(states)=={CID,41325637}
 for cid in states:
  old=next(c for c in bundle['campaigns']if c['id']==cid);assert states[cid]['status']==9
  assert {n['nm_id']for n in states[cid]['nm_settings']}=={r['nm']for r in old['current_articles']}
 for n in states[CID]['nm_settings']:
  if n['nm_id']in EXPECTED:assert n['bids_kopecks']['search']==EXPECTED[n['nm_id']][1]and n['subject']['id']==50
 q=http(io,'/api/advert/v1/bids/min','POST',dict(advert_id=CID,nm_ids=sorted(EXPECTED),payment_type='cpc',placement_types=['search']))
 assert {r['nm_id']for r in q['bids']}==set(EXPECTED)
 assert all([b['value']for b in r['bids']if b['type']=='search'and b['currency']=='CNY']==[28]for r in q['bids'])
 u=http(io,'/api/advert/v1/bids/min','POST',dict(advert_id=41325637,nm_ids=[1556488181],payment_type='cpc',placement_types=['search']))
 assert [b['value']for r in u['bids']for b in r['bids']if b['type']=='search'and b['currency']=='CNY']==[27]
 SOURCE['campaign']=states[CID]
 prior=io.get('china_agent:owner_two_campaign_cost_review:2026-11-16:v1:review')
 restored={r['action']['id']for c in prior['campaigns']if c['id']==41325637 for r in c['focus']if(r.get('action')or{}).get('kind')=='ad_add_sku'}
 publish.EXPECTED_ADDED={str(CID)+':'+str(n)for n in EXPECTED}|restored;publish.EXPECTED_REMOVED=set()
 return dict(live=live,minimum_quotes=[q,u],observed_at=datetime.now(timezone.utc).isoformat(),wb_writes=0)

def main():
 import owner_risk16_restore as publish
 publish.ROOT=ROOT;publish.SLOT='cost-review-169';publish.OWNER_REQUEST='Эффективно расходовать бюджет; новые обоснованные добавления разрешены параллельно.667 не снимать.'
 publish.restore=lambda b,p:review(b,p,SOURCE);publish.PREFLIGHT=preflight;publish.ALLOW_UMBRELLA_READS=True;publish.READ_CAMPAIGN_IDS={CID,41325637}
 publish.main()
if __name__=='__main__':main()
