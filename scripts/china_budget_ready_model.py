"""Campaign-level preliminary funding evidence. Never equate a reserve with approval or profit."""
import math
from datetime import date,datetime,timedelta,timezone
from zoneinfo import ZoneInfo
def finite(v):return type(v)in(int,float)and math.isfinite(v)
def instant(v):return datetime.fromisoformat(v.replace('Z','+00:00').replace(' UTC','+00:00'))
def assess_campaign(state,raw,economics,own,changes,days,observed,funding_reference_days=None):
 result=dict(status='unknown',observed_at=observed,preliminary=True,unknown_costs=True,source='whole_campaign_attribution_with_own_buyout_model',ready=False)
 if state.get('status')not in(9,11) or not raw:return dict(result,reason='Нет полного результата РК.')
 end=date.fromisoformat(days[-1]);members={n['nm_id']for n in state['nm_settings']}
 dates=[instant(x['at']).astimezone(ZoneInfo('Europe/Moscow')).date()for x in changes if x.get('cid')==state['id']and x['kind']in['bid','added','excluded','returned','relaunch']or x.get('nm')in members and x['kind']=='price']
 if state.get('timestamps',{}).get('started'):dates.append(instant(state['timestamps']['started']).astimezone(ZoneInfo('Europe/Moscow')).date())
 first=max(dates,default=end-timedelta(days=7))+timedelta(days=1)
 wanted=[d for d in days if date.fromisoformat(d)>=first]
 if not wanted:
  # Waiting for an outcome day must not starve an already approved active test.
  # Funding uses completed historical traffic/current economics, not a causal post-change verdict.
  launched=instant(state['timestamps']['started']).astimezone(ZoneInfo('Europe/Moscow')).date()if state.get('timestamps',{}).get('started')else None
  reference=[d for d in days if not launched or date.fromisoformat(d)>launched]
  if len(reference)!=3:
   available={d['date'][:10]for d in raw.get('days',[])}
   chosen=[d for d in(funding_reference_days or[])if d in days and d in available]
   if not chosen:
    chosen=[d for d in days if d in available]
   if not chosen or funding_reference_days and chosen!=funding_reference_days:return dict(result,status='unknown',evaluation_status='waiting',reason='Нет завершённого исторического расхода для расчёта продолжения теста.')
   reference=chosen
   result.update(owner_manual_launch_day_continuation=True,reference_window='completed_calendar_day_partial_launch_traffic',not_three_full_test_days=True)
  wanted=reference
  result.update(funding_basis='continuation_historical_traffic_current_economics',evaluation_status='waiting',first_full_post_change_day=first.isoformat(),post_change_result_available=False)

 daily={d['date'][:10]:d for d in raw['days']}
 if not all(d in daily for d in wanted):return dict(result,reason='Не хватает полного дня статистики РК.')
 totals={k:sum(daily[d][f]for d in wanted)for k,f in [('spend','sum'),('orders','orders'),('amount','sum_price'),('clicks','clicks')]}
 bynm={}
 for d in wanted:
  for app in daily[d].get('apps',[]):
   for row in app.get('nms',[]):
    nm=row['nmId'];bynm[nm]=bynm.get(nm,0)+row.get('orders',0)
 if sum(bynm.values())!=totals['orders']:return dict(result,reason='Сумма атрибуций SKU не совпадает с итогом РК.')
 models=economics.get('rows',{});own={int(r['nm_id']):r for r in own.get('rows',[])}
 covered=0;contribution=0;stressed=0;small=[];unknown=[]
 associated={nm:n for nm,n in bynm.items()if nm not in members and n>0}
 max_log=max((e.get('logistics_cny',0)+e.get('handling_rub',0)/e['fx_rub_per_cny'] for e in models.values()if finite(e.get('logistics_cny'))and finite(e.get('fx_rub_per_cny'))and e['fx_rub_per_cny']>0),default=0)
 # Associated purchases are not proved incremental benefit. Charge their downside,
 # retain their attribution counts, and never let a missing foreign SKU hide a no-fund result.
 associated_reserve=0;associated_unknown=[]
 direct_orders=sum(n for nm,n in bynm.items()if nm in members)
 for nm,orders in bynm.items():
  if orders<=0 or nm not in members:continue
  e=models.get(str(nm),{});o=own.get(nm,{})
  buyout_ok=(e.get('sample_size',0)>0 and not e.get('buyout_fallback'))or(e.get('sample_size',0)==0 and e.get('buyout_fallback')and (bool(e.get('planned_buyout_source'))or e.get('buyout')==.5))
  valid=buyout_ok and all(finite(e.get(k))for k in ['expected_margin_before_ads_cny','buyout','own_cogs_rub','seller_price_cny','fx_rub_per_cny','logistics_cny','commission_pct'])
  if not valid:unknown.append(nm);continue
  try:
   if any(not 0<=(instant(observed)-instant(e[k])).total_seconds()<=24*3600 for k in['observed_at','price_observed_at','stock_observed_at','published_stock_observed_at']):raise ValueError('Stale')
  except (KeyError,ValueError,TypeError):unknown.append(nm);continue
  fx=e['fx_rub_per_cny'];delivery=max(e['logistics_cny'],(o.get('average_delivery_cost')or 0)/fx);handling=e.get('handling_rub',10)/fx
  reverse=(o.get('backwardlogisticsum')or 0)/e['sample_size']/fx if e['sample_size'] else 0
  margin=e['expected_margin_before_ads_cny']-(delivery-e['logistics_cny'])-reverse
  stress=margin-.2*e['buyout']*(e['seller_price_cny']*(1-(e['commission_pct']+e.get('tax_pct',5))/100)-e['own_cogs_rub']/fx)
  covered+=orders;contribution+=orders*margin;stressed+=orders*stress;max_log=max(max_log,delivery+handling)
  if e['sample_size']<10 or e.get('commission_policy_fallback'):small.append(nm)
 coverage=covered/direct_orders if direct_orders else 0
 # Preserve known downside; only unmodeled associated orders need the explicit
 # two-logistics stress reserve already used by the recovery review.
 for nm,n in associated.items():
  e=models.get(str(nm),{})
  try:
   fresh=0<=(instant(observed)-instant(e['observed_at'])).total_seconds()<=24*3600
  except (KeyError,ValueError,TypeError):fresh=False
  if fresh and finite(e.get('expected_margin_before_ads_cny')):associated_reserve+=max(0,-e['expected_margin_before_ads_cny'])*n
  else:associated_unknown.append(nm);associated_reserve+=2*max_log*n
 result.update(direct_attributed_orders=direct_orders,associated_attributed_orders=sum(associated.values()),associated_orders_by_nm={str(nm):n for nm,n in associated.items()},associated_downside_reserve_cny=associated_reserve,associated_orders_not_incremental_profit=True)
 result.update(attributed_orders_by_nm={str(nm):n for nm,n in bynm.items()if nm in members and n>0},period_from=wanted[0],period_to=wanted[-1],days=wanted,metrics=totals,covered_attributed_orders=covered,attributed_orders=totals['orders'],coverage=coverage,modeled_contribution_cny=contribution,modeled_after_ads_cny=contribution-totals['spend']-associated_reserve,stress_after_ads_cny=stressed-totals['spend']-(direct_orders-covered)*2*max_log-associated_reserve,unknown_nm_ids=unknown,small_sample_nm_ids=small,own_cohort_after_change_verified=False)
 if direct_orders==0 and totals['spend']>0:return dict(result,status='review',reason='Не пополнять и не возобновлять: в завершённом окне нет прямых заказов текущего состава; сопутствующие атрибуции не доказывают окупаемость. Это не окончательный финансовый результат.')
 # Own history is a provisional buyout prior, never a closed post-change financial cohort.
 if coverage>=.999999 and covered>0 and contribution<=totals['spend']:return dict(result,status='review',reason='Предварительная модель РК не поддерживает дополнительный расход; малая выборка не скрывает финансовый риск.')
 if coverage<.9:return dict(result,reason='Собственная модель покрывает недостаточно прямых рекламных атрибуций.')
 if result['modeled_after_ads_cny']<=0:return dict(result,status='review',reason='Не пополнять и не возобновлять: предварительная модель с расходами и резервом сопутствующих атрибуций не поддерживает продолжение; это не доказанный убыток.')
 if associated_unknown and max_log<=0:return dict(result,reason='Не подтверждён резерв расходов сопутствующих атрибуций.')
 if result.get('evaluation_status')=='waiting':
  if result['stress_after_ads_cny']<=0:return dict(result,status='review',reason='Нет положительной стресс-модели для ограниченного продолжения теста.')
  return dict(result,status='positive',ready=True,reason='Ограниченное продолжение согласованного теста: исторический расход завершённых дней и текущая предварительная экономика. Полного дня после изменения ещё нет; прибыль и причинный эффект не доказаны.')
 return dict(result,status='positive',ready=True,reason='Предварительная собственная модель РК положительна. Малая выборка, пересечения атрибуций и неизвестные расходы сохраняются; только ограниченное пополнение после команды.')
def attach(bundle,source,changes):
 import copy
 out=copy.deepcopy(bundle);states={c['id']:c for b in source['batches'].values()for c in b['campaigns']['adverts']};stats={c['advertId']:c for b in source['batches'].values()for c in b['stats']}
 data=source.get('full_growth_inputs')or{};own=data.get('own')or{}
 for c in out['campaigns']:
  if c['id']in states:
   from china_advertising_decision_contract import effective_launch_at
   model_state=copy.deepcopy(states[c['id']]);model_state.setdefault('timestamps',{})['started']=effective_launch_at(source,states[c['id']])
   c['campaign_budget_economics']=assess_campaign(model_state,stats.get(c['id']),source.get('economics',{}),own,changes,out['budget_days'],out.get('budget_observed_at',source['observed_at']),funding_reference_days=(source.get('owner_launch_day_funding_refs')or{}).get(str(c['id'])))
   e=c['campaign_budget_economics'];e['expected_bids']={str(n['nm_id']):n['bids_kopecks']for n in states[c['id']]['nm_settings']}
   models=source.get('economics',{}).get('rows',{});labels={int(r['nmID']):r['vendorCode']for r in source['catalogue']['rows']}
   price_rows={int(r['nm_id']):r for r in data.get('prices',{}).get('rows',[])};stock_rows={r['article'].casefold():r for r in data.get('stock',{}).get('rows',[])}
   e['member_inputs']={}
   for nm in map(int,e['expected_bids']):
    model=models.get(str(nm),{});pr=price_rows.get(nm,{});article=pr.get('article')or labels.get(nm);st=stock_rows.get((article or'').casefold(),{})
    free=st.get('stock',0)-st.get('reserve',0)if st.get('stock')is not None and st.get('reserve')is not None else model.get('stock_free')
    pub=(data.get('published_stock',{}).get('amounts')or{}).get(str(nm),model.get('published_stock'))
    e['member_inputs'][str(nm)]=dict(article=article,price=pr.get('seller_price',model.get('seller_price_cny')),cost=st['price']/100 if finite(st.get('price'))and st['price']>0 else model.get('own_cogs_rub'),buyout=model.get('buyout')if not model.get('buyout_fallback')else None,fx=model.get('fx_rub_per_cny',(data.get('fx')or{}).get('rub_per_cny')),stock_free=free,published_stock=pub)
   incomplete=[nm for nm,r in e['member_inputs'].items()if not finite(r['price'])or r['published_stock']is None or r['stock_free']is None or not finite(r['cost'])and not(r['stock_free']<=0 and r['published_stock']==0)]
   if incomplete:e.update(status='unknown',ready=False,reason='Не подтверждены текущие цена, себестоимость или остаток состава РК.',incomplete_member_inputs=incomplete)
 return out

def validate_funding(io,item,before):
 """Fresh price, own COGS/availability and exact bid composition before an explicitly approved deposit."""
 if item.get('owner_cash25_contract'):
  from china_owner_cash25_contract import validate as validate_cash25
  return validate_cash25(io,item,before)
 if item.get('owner_report20_contract'):
  from china_owner_report20_contract import validate
  return validate(io,item,before)
 if item.get('manual_budget_continuation'):
  from china_manual_budget_contract import validate_funding as validate_manual
  return validate_manual(io,item,before)
 from china_advertising_v2 import http
 from china_morning_readiness import current_prices,published_stock
 from china_moysklad_read import read_stock
 evidence=item.get('budget_evidence')
 if not evidence:return # Older already-bound legacy plans retain their existing execution checks.
 now=datetime.now(timezone.utc)
 if evidence.get('status')!='positive'or not evidence.get('ready')or (not 0<=(now-instant(evidence['observed_at'])).total_seconds()<=2*3600 and not getattr(io,'daily_report_current_revalidation',False)):raise ValueError('Funding review unavailable or expired')
 if evidence['period_to']>=str(now.astimezone(ZoneInfo('Europe/Moscow')).date()):raise ValueError('Incomplete-day funding evidence')
 actual={str(n['nm_id']):n['bids_kopecks']for n in before['nm_settings']}
 if actual!=evidence['expected_bids']:
  from china_confirmed_funding_context import reconcile
  evidence=reconcile(io,evidence,before)
 prices=current_prices(io,list(map(int,actual)));pub=published_stock(io,prices,list(map(int,actual)))
 stock=read_stock([r['article']for r in prices['rows']]);rows={r['article'].casefold():r for r in stock['rows']}
 if not stock['coverage_complete']or pub['missing_nm_ids']:raise ValueError('Funding stock coverage incomplete')
 delta=0
 for r in prices['rows']:
  nm=str(r['nm_id']);old=evidence['member_inputs'][nm];st=rows[r['article'].casefold()]
  if r['seller_price']!=old['price']:raise ValueError('Funding seller price changed')
  current_free=st['stock']-st['reserve'];current_pub=pub['amounts'][nm]
  # A continuously unavailable member may not contribute hypothetical profit.
  # A known unknown was already excluded from contribution and charged in stress.
  unknown_unmodeled=int(nm)in evidence.get('unknown_nm_ids',[])and evidence.get('coverage',0)>=.9 and evidence.get('stress_after_ads_cny',0)>0
  if (old['stock_free']is not None and old['stock_free']<=0 or old['published_stock']==0)and (evidence['attributed_orders_by_nm'].get(nm,0)==0 or unknown_unmodeled):
   if current_free>0 and current_pub>0:raise ValueError('Previously unavailable product changed; fresh model required')
   continue
  published_required=(io.get('china_agent:analysis_backend:v1')or{}).get('require_published_stock',True)is not False
  if current_free<=0 or (published_required and current_pub<=0) or not st.get('price')or st['price']<=0 or not finite(old['cost']):raise ValueError('Funding current stock/COGS unavailable: '+r['article']+' (nm '+nm+', MSK free '+str(current_free)+', WB '+str(current_pub)+')')
  q=old['buyout'];fx=old['fx']
  if not finite(q)and st['price']/100>old['cost']:raise ValueError('Changed COGS with unknown own buyout; refresh review')
  if finite(q)and finite(fx)and fx>0:delta+=evidence['attributed_orders_by_nm'].get(nm,0)*q*(st['price']/100-old['cost'])/fx
 if evidence['modeled_after_ads_cny']-delta<=0:raise ValueError('Current COGS no longer supports provisional funding model')
