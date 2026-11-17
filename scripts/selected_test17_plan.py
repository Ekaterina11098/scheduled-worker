"""Build an exact proposal from saved completed-day evidence; no execution."""
import copy
from datetime import datetime,timezone
from china_selected_campaign_test import CONTRACT,PREPARATION
from china_loss_control import digest
KEEP={2128836688,2129199357,2129309884,2129309885}

def correction(bundle,source,models,fresh):
 result=copy.deepcopy(bundle)
 for section in result['recommendation_directions'].values():
  section['rows']=[r for r in section['rows']if r.get('campaign_id')!=41779660]
  section.update(count=len(section['rows']),ready_count=sum(r.get('ready')is True for r in section['rows']))
 c=next(c for c in result['campaigns']if c['id']==41779660)
 before=next(c for c in fresh['campaigns']['adverts']if c['id']==41779660)
 actual={str(n['nm_id']):n['bids_kopecks']for n in before['nm_settings']}
 assert c['status']==before['status']==11 and c['balance']==fresh['budgets']['rows']['41779660']['total']==0
 assert KEEP<set(map(int,actual))
 raw=next(s for b in source['batches'].values()for s in b['stats']if s['advertId']==41779660)
 traffic={str(n):dict(clicks=0,orders=0)for n in KEEP}
 for day in raw['days']:
  if day['date'][:10]!='2026-11-16':continue
  for app in day['apps']:
   for n in app['nms']:
    if n['nmId']in KEEP:
     row=traffic[str(n['nmId'])];row['clicks']+=n['clicks'];row['orders']+=n['orders']
 cost=sum(t['clicks']*.28 for t in traffic.values());net=0;stress=0;members={}
 for n,t in traffic.items():
  m=models['rows'][n];assert m['published_stock']>0 and m['stock_free']>0
  assert m['buyout']==.4 and m['sample_size']==0 and m['expected_margin_before_ads_cny']>0
  net+=m['expected_margin_before_ads_cny']*t['orders']-t['clicks']*.28
  stress+=((m['expected_margin_before_ads_cny']+m['logistics_cny'])*.32/.4-m['logistics_cny'])*t['orders']-t['clicks']*.28
  members[n]=dict(price=m['seller_price_cny'],cost=m['own_cogs_rub'],buyout=m['buyout'],logistics_cny=m['logistics_cny'])
 assert abs(cost-54.04)<.001 and abs(net-37.93318)<.001 and abs(stress+25.4415)<.001
 action=dict(id='selected-test:41779660:20261117-v1',kind='recover_campaign',campaign_id=41779660,status_before=11,
  selected_test=True,nm_ids=sorted(KEEP),remove_nm_ids=[],placement='recommendations',target_minor=28,
  amount_cny=200,balance_before=0,article='Тест 027/68/160/161; выкуп 40%: +37,93 CNY, при 32%: −25,44 CNY; малая выборка',
  review_scope_text='Состав и ставки из рекламного PNG уже проверены. Пополнить200 и возобновить027,68,160,161по0,28. Риск: плановый выкуп40%, при32% расчет отрицательный.',
  recovery_evidence=dict(preliminary=True,period_from='2026-11-16',period_to='2026-11-16',observed_at=fresh['published_guangzhou']['observed_at'],expected_bids={str(n):dict(actual[str(n)],recommendations=28)for n in KEEP},
   modeled_after_ads_cny=net,stress_after_ads_cny=stress,risk_disclosed_before_confirmation=True,member_inputs=members,traffic=traffic,
   inputs_key='china_agent:advertising_full_growth:2026-11-17:v1:inputs',spend_cny=round(cost*3,2),
   reserve_basis='Scenario: one completed day selected clicks at lower bid times three; not three measured days or forecast',
   attribution_not_incremental=True,unknown_shared_costs=True))
 action['selected_test_contract']=CONTRACT+'41779660:'+action['id']
 ref=PREPARATION+'41779660:20261117-v1'
 prep=[];labels={n['nm']:n['article']for n in c['current_articles']}
 for nm in sorted(set(map(int,actual))-KEEP):
  prep.append(dict(id='prepare-test:41779660:'+str(nm),kind='ad_exclude_sku',campaign_id=41779660,nm_id=nm,article=labels[nm],placement='recommendations',old_minor=actual[str(nm)]['recommendations'],status_before=11,paused_exclusion_only=True,preparation_ref=ref,owner_selected=True))
 nm=2129309885
 prep.append(dict(id='prepare-test:41779660:'+str(nm),kind='ad_set_bid',campaign_id=41779660,nm_id=nm,article=labels[nm],placement='recommendations',old_minor=50,target_minor=28,status_before=11,paused_reduction_only=True,preparation_ref=ref))
 action['requires_preparation_key']=ref
 c.update(focus=[],attention=[dict(article=x['article'],action=x)for x in prep],budget_action=None,financial_action=action,financial_recommendation='Тест: оставить 027, 68, 160, 161 по 0,28 CNY; остальные 14 убрать. 161: 0,50 → 0,28. Пополнение 200 CNY и запуск — отдельно в бюджетном PNG. Предварительная экономика +37,93; стресс −25,44 CNY.',budget_review_required=True)
 result['selected_test_preparation']=dict(key=ref,status='ready_for_human_confirmation',grants_action_permission=False,campaign_id=41779660,keep_nm_ids=sorted(KEEP),expected_bids=actual,placement='recommendations',target_minor=28,action_hashes={a['id']:digest([a])for a in prep})
 c.pop('owner_statistics_note',None)
 for z in result['campaigns']:
  if z['id']==41325637:
   z['owner_statistics_note']='79 и 92 оставить по 0,27. 102: 15–16.11 без заказов, 5,94 CNY; не повышать. 26 и 121: тест по 0,27, оценка 18.11. Без пополнения.'
  if z['id']==41332083:
   z['owner_statistics_note']='Бюджет 0; вероятная остановка из-за денег. ДРР вчера 4,45%. Предварительная экономика 3 дней: +141,25 CNY; стресс −28,05. Это риск модели, не запрет владельца на запуск.'
 result['owner_selected_test_proposal']=dict(campaign_id=41779660,action_id=action['id'],no_execution_before_human_confirmation=True,wb_writes=0,model_calls=0)
 return result,action

