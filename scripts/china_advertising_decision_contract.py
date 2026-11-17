"""One deterministic existing-SKU decision contract for all report surfaces."""
import copy,hashlib,json
from datetime import datetime
from zoneinfo import ZoneInfo
REVISION='completed-postchange-economics-v1'
MSK=ZoneInfo('Europe/Moscow')
KINDS={'price','bid','added','returned','relaunch'}
def changed_day(source,state,nm):
 from china_advertising_v2 import history
 events=list(history(source.get('executions',[])))+list(source.get('verified_composition_changes',[]))
 for rec in source.get('experience',[]):
  event=rec.get('payload',rec);action=event.get('action',{});at=event.get('started_at')
  if action.get('kind')=='price_change'and at:
   events.extend(dict(nm=n,kind='price',at=at)for n in action.get('nm_ids',[]))
 ats=[x['at']for x in events if x.get('nm')==nm and x.get('kind')in KINDS]
 if state.get('timestamps',{}).get('started'):ats.append(state['timestamps']['started'])
 days=[]
 for at in ats:
  dt=datetime.fromisoformat(at.replace('Z','+00:00'))
  if dt.tzinfo is None:raise ValueError('Verified change timestamp requires timezone')
  days.append(dt.astimezone(MSK).date().isoformat())
 return max(days,default='1970-01-01')
def normalize(bundle,source):
 """Use only full supplied days strictly after the last verified SKU change."""
 from china_advertising_v2 import daily_metrics,sums
 out=copy.deepcopy(bundle)
 if not out.get('day'):return out # Legacy context-free unit fixtures; final publication requires a dated bundle.
 day=out['day'];allowed=set(out.get('days',[]))
 raw={r['advertId']:r for b in source['batches'].values()for r in b.get('stats',[])}
 states={c['id']:c for b in source['batches'].values()for c in b['campaigns'].get('adverts',[])}
 for cp in out['campaigns']:
  state=states[cp['id']];members={n['nm_id']for n in state['nm_settings']}
  for row in cp.get('focus',[]):
   nm=row['nm']
   if nm not in members:continue
   epoch=changed_day(source,state,nm)
   ds=[d for d in raw.get(cp['id'],{}).get('days',[])if epoch<d['date'][:10]<day and d['date'][:10]in allowed]
   names=sorted({d['date'][:10]for d in ds})
   metrics=sums(daily_metrics(n)for d in ds for a in d.get('apps',[])for n in a.get('nms',[])if n['nmId']==nm)
   row['decision_window']=dict(revision=REVISION,changed_day=epoch,days=names,metrics=metrics,launch_change_day_excluded=True)
   comparison=dict(row.get('comparison')or{});comparison.update(after=metrics,to_days=names);row['comparison']=comparison
   row['pending_first_day']=not bool(names)
   if not names:row['action']=None
 return out
def finalize(io,bundle,source,minima):
 """Shared entry point for morning, midday and a cached analyst preview; no API calls."""
 from china_advertising_economic_review import apply
 from china_advertising_directions import attach
 if not bundle.get('day')or not bundle.get('days'):raise ValueError('Unified decision requires completed dated source')
 additions={(c['id'],r['nm']):copy.deepcopy(r)for c in bundle['campaigns']for r in c.get('focus',[])if (r.get('action')or{}).get('kind')=='ad_add_sku'}
 out=apply(bundle,source,minima)
 for cp in out['campaigns']:
  cp['focus']=[additions.get((cp['id'],r['nm']),r)for r in cp.get('focus',[])]
  cp['attention']=[r for r in cp['focus']if r.get('action')]
 out=attach(out,source)
 rows=[];ledger_key='china_agent:advertising_decisions:v1:'+REVISION+':'+out['day']
 prior=(io.get(ledger_key)or{})if io is not None else {};ledger=copy.deepcopy(prior)
 for cp in out['campaigns']:
  for r in cp.get('focus',[]):
   window=r.get('decision_window')
   if not window:continue
   # Timestamp refresh alone must not create a new economic decision identity.
   e=r.get('economics',{})
   facts=dict(cid=cp['id'],nm=r['nm'],window=window,cumulative=r.get('completed_exposure_guard'),status=cp.get('status'),blocker=r.get('data_blocker'),pending=r.get('pending_first_day'),current_bid=r.get('current_bid_minor'),minimum=r.get('minimum_bid_minor'),economics={k:e.get(k)for k in ('seller_price_cny','stock_free','published_stock','own_cogs_rub','buyout','sample_size','logistics_cny','commission_pct','expected_margin_before_ads_cny')})
   hh=hashlib.sha256(json.dumps(facts,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
   row=dict(campaign_id=cp['id'],nm_id=r['nm'],article=r['article'],facts_sha256=hh,decision=r.get('decision'),action=r.get('action'),decision_window=window,reason=r.get('reason'))
   key=str(cp['id'])+':'+str(r['nm'])
   if io is not None:
    old=ledger.get(key)
    if old and old.get('facts_sha256')==hh and (old.get('action')!=row['action']or old.get('decision')!=row['decision']):raise ValueError('Same verified facts produced conflicting recommendation')
    ledger[key]=row
   rows.append(row)
 if io is not None and ledger!=prior:
  if prior:io.put(ledger_key,ledger)
  else:io.create(ledger_key,ledger)
 out['decision_contract']=dict(revision=REVISION,rows=rows,deterministic=True,model_calls=0,wb_writes=0)
 return out

