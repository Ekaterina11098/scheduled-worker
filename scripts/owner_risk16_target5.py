"""Owner-requested composition proposal under the 5% target. No WB execution."""
import copy
from datetime import datetime,timezone
CID=41325637;KEEP={1556488202,1556488137,1556488446}

def target5(current,prior=None):
 out=copy.deepcopy(current);c=next(c for c in out['campaigns']if c['id']==CID)
 articles={r['nm']:r['article']for r in c['current_articles']};assert KEEP<=set(articles)
 exclude=set(articles)-KEEP;assert len(exclude)==12
 members={m['nm']:m for m in c['budget_members']}
 assert all(members[n]['first_full_day']<='2026-11-15'for n in articles)
 for nm in KEEP:
  e=members[nm]['economics'];assert e['expected_margin_before_ads_cny']>0 and e['stock_free']>0 and e['published_stock']>0
  assert 0<=(datetime.now(timezone.utc)-datetime.fromisoformat(e['observed_at'])).total_seconds()<24*3600
 c['focus']=[r for r in c['focus']if r['nm']not in exclude and(r.get('action')or{}).get('kind')!='ad_add_sku']
 section=out['recommendation_directions']['exclude'];assert not any(r.get('campaign_id')==CID for r in section['rows'])
 for nm in sorted(exclude):
  e=members[nm]['economics'];p=members[nm]['completed_traffic']or{}
  evidence=dict(target_drr_pct=5,owner_requested_cost_control=True,post_change_day='2026-11-15',context_days=['2026-11-13','2026-11-14','2026-11-15'],source='china_agent:advertising_source:2026-11-16:v2',metrics=p,preliminary=True,allocation_proposal_not_proven_sku_loss=True,low_ad_sample=p.get('orders',0)<10,requires_new_confirmation=True)
  a=dict(id=str(CID)+':'+str(nm),kind='ad_exclude_sku',campaign_id=CID,nm_id=nm,article=articles[nm],placement='search',old_minor=27,cost_control_evidence=evidence)
  r=dict(nm=nm,article=articles[nm],period=p,decision='Исключить из этой РК: сократить расход под целевую ДРР5%.',reason='Предложение концентрации состава, не доказательство убыточности товара. Первый полный день после перезапуска —15.11; малые выборки сохранены.',action=a,economics=e)
  c['focus'].append(r);section['rows'].append(dict(article=r['article'],campaign_id=CID,nm_id=nm,decision=r['decision'],action=a,period=p,economics=e,ready=True))
 c['attention']=[r for r in c['focus']if r.get('action')]
 additions=out['recommendation_directions']['add'];additions['rows']=[r for r in additions['rows']if r.get('campaign_id')!=CID]
 for section in out['recommendation_directions'].values():section.update(count=len(section['rows']),ready_count=sum(r.get('ready')is True for r in section['rows']))
 out['owner_umbrella_target5']=dict(campaign_id=CID,target_drr_pct=5,keep=sorted(KEEP),propose_exclude=sorted(exclude),bid_minor=27,remove_new_additions=True,retrospective_kept_spend_cny=20.52,retrospective_kept_amount_cny=429,retrospective_kept_orders=5,retrospective_drr_pct=20.52/429*100,retrospective_not_forecast=True,low_sample=True,zont01_exclusion_may_reduce_order_volume=True,wb_writes=0)
 return out

def preflight(io,bundle):
 import owner_risk16_restore as publish
 from china_advertising_v2 import http
 c=next(c for c in bundle['campaigns']if c['id']==CID);expected={r['nm']for r in c['current_articles']}
 live=http(io,'/api/advert/v2/adverts?ids=41325637')['adverts'];assert len(live)==1 and live[0]['id']==CID and live[0]['status']==9
 assert {n['nm_id']for n in live[0]['nm_settings']}==expected
 assert all(n['bids_kopecks']['search']==27 and n['subject']['id']==61 for n in live[0]['nm_settings'])
 quote=http(io,'/api/advert/v1/bids/min','POST',dict(advert_id=CID,nm_ids=[1556488181],payment_type='cpc',placement_types=['search']))
 assert [b['value']for r in quote['bids']for b in r['bids']if r['nm_id']==1556488181 and b['type']=='search'and b['currency']=='CNY']==[27]
 publish.EXPECTED_ADDED={str(CID)+':'+str(nm)for nm in expected-KEEP}
 publish.EXPECTED_REMOVED={r['action']['id']for r in c['focus']if(r.get('action')or{}).get('kind')=='ad_add_sku'}
 return dict(live=live,minimum_quote=quote,observed_at=datetime.now(timezone.utc).isoformat(),wb_writes=0)

def main():
 import owner_risk16_restore as publish
 publish.ROOT='china_agent:owner_two_campaign_cost_review:2026-11-16:v4'
 publish.SLOT='cost-review-two16-target5';publish.OWNER_REQUEST='стабильно высокий дрр при нашем плановом 5% — нужны действия'
 publish.restore=target5;publish.PREFLIGHT=preflight;publish.ALLOW_UMBRELLA_READS=True
 publish.main()
if __name__=='__main__':main()
