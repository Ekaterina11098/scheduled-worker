"""Deterministic review of every catalogue row; proposals only, no provider calls."""
import collections,datetime,json

def minimum_bid_exclusions(a,e,day):
 """Proposals only: sustained failure at the minimum, after the latest known change.

 Never infer a placement from blended traffic. An exclusion covers the whole SKU.
 Require seven complete returned campaign days, 90 clicks/300 KGS and three
 recent spending days without direct orders. This is not an automatic WB stop.
 """
 end=datetime.date.fromisoformat(day)-datetime.timedelta(days=1)
 start=end-datetime.timedelta(days=6);last3={str(end-datetime.timedelta(days=i))for i in range(3)}
 stats=e['sources']['advertising14']['data'];result=[];checks=[]
 for r in a['rows']:
  for m in r['members']:
   if m['status']!=9:continue
   cfg=a['configurations'][str(m['cid'])]
   placements=[p for p,on in m['placements'].items()if on]
   if not placements or any(m['bids'].get(p)!=(270 if m['cid']==39605579 and p=='recommendations'else 325)for p in placements):continue
   dates=[v[:10]for v in cfg.get('timestamps',{}).values()if isinstance(v,str)and v[:10]<='2099-12-31']
   dates += [v['at'][:10]for v in a.get('verified_bid_changes',[])if v['cid']==m['cid']and v['nm']==r['nm']]
   if not dates or max(dates)>=str(start):continue # Change day is mixed; seven FULL days required.
   campaign=next((c for c in stats if c['advertId']==m['cid']),{})
   observed={d['date'][:10]for d in campaign.get('days',[])}
   required={str(start+datetime.timedelta(days=i))for i in range(7)}
   if not required<=observed:continue
   totals=collections.Counter();recent={d:collections.Counter()for d in last3}
   for c in stats:
    for d in c.get('days',[]):
     dt=d['date'][:10]
     if dt not in required:continue
     for app in d.get('apps',[]):
      for n in app.get('nms',[]):
       if n['nmId']!=r['nm']:continue
       values={k:n.get(k,0)for k in ('sum','sum_price','orders','clicks')}
       totals.update(values)
       if dt in recent:recent[dt].update(values)
   drr=totals['sum']/totals['sum_price']*100 if totals['sum_price']>0 else None
   sustained=all(v['sum']>0 and v['orders']==0 for v in recent.values())
   ready=totals['sum']>=300 and totals['clicks']>=90 and sustained and(drr is None or drr>5)
   checks.append({'cid':m['cid'],'nm':r['nm'],'period':[str(start),str(end)],'all_campaign_totals':dict(totals),'drr':drr,'propose_exclusion':ready})
   if ready:result.append({'kind':'exclude_sku','cid':m['cid'],'nm':r['nm'],'article':r['article']})
 return result,checks

def evaluate_funding(cid,cfg,campaign,balance,rows,missing_days):
 """Evaluate active AND paused campaigns; return proposals, never resume permissions."""
 members=[r for r in rows if any(m['cid']==int(cid)for m in r['members'])]
 stocked=[r for r in members if isinstance(r.get('free_msk'),(int,float))and r['free_msk']>0 and(r.get('stock_wb')or{}).get('wb',0)>0]
 positive=[r for r in stocked if(r.get('model_lower_before_ads_rub')or 0)>0]
 last=campaign.get('day',{});three=campaign.get('three',{})
 drr=lambda x:x.get('sum',0)/x['sum_price']*100 if x.get('sum_price',0)>0 else None
 result={'cid':int(cid),'campaign_status':cfg.get('status'),'balance_kgs':balance,'decision':'not_needed','amount_kgs':None,'day_drr':drr(last),'three_drr':drr(three),'stocked_skus':len(stocked),'positive_scenario_skus':len(positive),'resume_authorized':False}
 def stop(reason):result['decision']=reason;return result
 if int(cid)in(41517533,39605582):return stop('owner_hold')
 if cfg.get('status')not in(9,11):return stop('ineligible_campaign_status')
 if missing_days:return stop('incomplete_recent_days')
 if not isinstance(balance,(int,float)):return stop('unknown_budget')
 if not positive:return stop('economics_or_stock_unconfirmed')
 # Paused campaigns need actual recent traffic, not late attribution alone.
 if cfg['status']==11:
  if three.get('clicks',0)<30 or three.get('sum',0)<100:return stop('paused_recent_delivery_insufficient')
  if len(positive)!=len(stocked):return stop('paused_composition_economics_review_required')
 if drr(last)is None or drr(three)is None:return stop('drr_undefined')
 if max(drr(last),drr(three))>5:return stop('drr_above_target')
 if last.get('sum',0)<=balance:return stop('budget_sufficient')
 gap=last['sum']-balance
 result.update(decision='propose_topup',amount_kgs=1200 if gap<=1200 else int((gap+99)//100*100))
 return result

def review(a,e,day):
 yesterday=(datetime.date.fromisoformat(day)-datetime.timedelta(days=1)).isoformat()
 period=[(datetime.date.fromisoformat(day)-datetime.timedelta(days=i)).isoformat()for i in (3,2,1)]
 dates={str(c['advertId']):{d['date'][:10]for d in c['days']}for c in e['sources']['advertising14']['data']}
 missing={cid:[d for d in period if d>=cfg.get('timestamps',{}).get('created','')[:10] and d not in dates.get(cid,set())]for cid,cfg in a['configurations'].items()};missing={k:v for k,v in missing.items()if v}
 actions=[];checks=[];funding=[];funding_checks=[]
 for r in a['rows']:
  own=(r['funnel14']or{}).get('statistic',{}).get('selected',{})
  p=collections.Counter()
  for m in r['members']:p.update((m['ads']or{}).get('three',{}))
  knownstock=isinstance(r['free_msk'],(int,float)) and r['free_msk']>0 and (r['stock_wb']or{}).get('wb',0)>0
  checks.append({'nm':r['nm'],'article':r['article'],'all_members_three':dict(p),'own_orders':own.get('orderCount'),'buyouts':own.get('buyoutCount'),'cancels':own.get('cancelCount'),'stock_wb':r['stock_wb'],'stock_msk':r['free_msk'],'mature_cohort':r['cohort'],'scenario_lower_before_ads_rub':r['model_lower_before_ads_rub'],'overlapping_campaigns':[m['cid']for m in r['members']],'growth_review':'Sparse direct attribution or mixed placement cannot establish a ready raise/add; stock and mature before-ad scenario checked, no profit assertion.'})
  for m in r['members']:
   if m['status']!=9 or m['cid']in(41517533,39605582)or not knownstock:continue
   # Only a single serving placement gives an unambiguous bid target.
   placements=[k for k,v in m['placements'].items()if v]
   if len(placements)!=1:continue
   placement=placements[0];bid=m['bids'].get(placement);minimum=270 if m['cid']==39605579 and placement=='recommendations'else 325
   v=(m['ads']or{}).get('three',{});last=(m['ads']or{}).get('day',{})
   if type(bid)is int and bid>minimum and v.get('clicks',0)>=30 and v.get('sum',0)>=100 and v.get('orders',0)==0 and last.get('orders',0)==0 and last.get('sum',0)>0:
    actions.append({'kind':'reduce_bid','cid':m['cid'],'nm':r['nm'],'article':r['article'],'placement':placement,'from_minor':bid,'to_minor':minimum})
 exclusions,minimum_checks=minimum_bid_exclusions(a,e,day)
 actions.extend(exclusions)
 for cid,cfg in a['configurations'].items():
  check=evaluate_funding(cid,cfg,a['campaigns'].get(cid,{}),a['budgets'].get(cid),a['rows'],missing.get(cid,[]))
  funding_checks.append(check)
  if check['decision']=='propose_topup':funding.append({'cid':int(cid),'amount_kgs':check['amount_kgs']})
 assert len(checks)==len(a['rows'])
 # Keep rationale outside PNG; an empty reduction list is not a minimum-bid review.
 for check in minimum_checks:
  next(r for r in checks if r['nm']==check['nm']).setdefault('minimum_bid_review',[]).append(check)
 return {'status':'reviewed_proposals_only','actions':actions,'funding':funding,'budgets':a['budgets'],'internal_analysis':{'catalogue':351,'sku_checks':checks,'funding_checks':funding_checks,'missing_required_day':missing,'sources_at':a['sources_at'],'historical_coverage':e.get('advertising_coverage'),'rules':'No zero fill. DRR native campaign first; no averages. No automatic pause/exclusion from no orders. Bid reductions only unambiguous serving placement above cached minimum. No raise/add without robust placement evidence. Active and paused campaigns both evaluated with recorded reasons; paused proposals require recent delivery and composition economics review, never authorize resume. Funding only actual one-day cash shortfall with native day/3d DRR<=5 and positive dated RUB-before-ad stock scenario; minimum1200 not authorization. No actual profit or FX conversion claimed. Recent minimum-bid changes never reissued.','economics':'RUB scenario before advertising only, mature cohort date explicit, no confirmed KGS/RUB FX or actual profit claim. Associated orders not proof of direct SKU efficacy.','wb_writes':0,'model_calls':0}}
