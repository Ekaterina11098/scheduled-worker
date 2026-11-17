"""Find completed-day cost risks across every current SKU, not only the initial shortlist."""
import copy
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo

def preserve_completed_cost(io,source,report_day):
 """Bounded per-SKU counters plus seven revisable days; no extra WB reads."""
 from china_advertising_v2 import history
 events=history(source.get('executions',[]));MSK=ZoneInfo('Europe/Moscow')
 def local(at):return datetime.fromisoformat(at.replace('Z','+00:00')).astimezone(MSK).date().isoformat()
 states={c['id']:c for b in source.get('batches',{}).values()for c in b.get('campaigns',{}).get('adverts',[])}
 key='china_agent:completed_campaign_cost:v2';old=io.get(key)or{};ledger=copy.deepcopy(old)
 for batch in source.get('batches',{}).values():
  for campaign in batch.get('stats',[]):
   cid=campaign['advertId'];state=states.get(cid)
   if not state or state.get('status')not in(9,11):continue
   target=ledger.setdefault(str(cid),{});wanted={str(n['nm_id'])for n in state['nm_settings']}
   for nm in list(target):
    if nm not in wanted:target.pop(nm)
   for nm in wanted:
    changes=[local(x['at'])for x in events if x.get('nm')==int(nm)and(x['kind']=='price'or x.get('cid')==cid and x['kind']in('bid','added','returned','relaunch'))]
    if state.get('timestamps',{}).get('started'):changes.append(local(state['timestamps']['started']))
    epoch=max(changes,default='1970-01-01');entry=target.get(nm)or{}
    if entry.get('epoch')!=epoch:entry=dict(epoch=epoch,days={},older=dict(spend=0,clicks=0,orders=0,day_count=0))
    for d in campaign.get('days',[]):
     day=d['date'][:10]
     if not epoch<day<report_day:continue
     if day<=entry['older'].get('last',''):continue # already folded; never count a wide reread twice
     rows=[n for app in d.get('apps',[])for n in app.get('nms',[])if str(n['nmId'])==nm]
     entry['days'][day]={a:sum(n.get(b,0)for n in rows)for a,b in [('spend','sum'),('clicks','clicks'),('orders','orders')]}
    dates=sorted(entry['days'])
    for day in dates[:-7]:
     r=entry['days'].pop(day)
     for a in('spend','clicks','orders'):entry['older'][a]+=r[a]
     entry['older']['day_count']+=1
     entry['older'].setdefault('first',day);entry['older']['last']=day
    target[nm]=entry
 if ledger!=old:
  io.put(key,ledger)if io.get(key)is not None else io.create(key,ledger)
 return ledger
def expand(bundle,source,minima):
 if not bundle.get('day')or not bundle.get('days'):return copy.deepcopy(bundle)
 from china_advertising_v2 import history
 out=copy.deepcopy(bundle);changes=history(source.get('executions',[]))+list(source.get('verified_composition_changes',[]));MSK=ZoneInfo('Europe/Moscow')
 # Match the initial selection's price-change evidence; a missing baseline must not reuse old traffic.
 for rec in source.get('experience',[]):
  event=rec.get('payload',rec);act=event.get('action',{});at=event.get('started_at')
  if act.get('kind')=='price_change'and at:
   changes.extend(dict(nm=nm,cid=None,kind='price',at=at)for nm in act.get('nm_ids',[]))
 for cid,q in (source.get('full_growth_inputs',{}).get('minimums')or{}).items():
  for r in q.get('bids',[]):
   values=[v['value']for v in r['bids']if v.get('currency')=='CNY']
   if len(values)==1:minima.setdefault(str(cid)+':'+str(r['nm_id']),values[0])
 labels={int(r['nmID']):r['vendorCode']for r in source.get('catalogue',{}).get('rows',[])}
 states={c['id']:c for b in source['batches'].values()for c in b['campaigns']['adverts']}
 stats={c['advertId']:c for b in source['batches'].values()for c in b['stats']}
 # Owner-approved: identical subject/payment/placement shares the verified category minimum.
 for cp in states.values():
  grouped={}
  for n in cp['nm_settings']:
   key=str(cp['id'])+':'+str(n['nm_id']);sid=n.get('subject',{}).get('id')
   if key in minima:grouped.setdefault(sid,set()).add(minima[key])
  for n in cp['nm_settings']:
   values=grouped.get(n.get('subject',{}).get('id'),set())
   if len(values)==1:minima.setdefault(str(cp['id'])+':'+str(n['nm_id']),next(iter(values)))
 models=source.get('economics',{}).get('rows',{})
 def dateof(x):return datetime.fromisoformat(x.replace('Z','+00:00')).astimezone(MSK).date().isoformat()
 for c in out['campaigns']:
  state=states.get(c['id']);raw=stats.get(c['id'])
  if not state or not raw or state['status']not in(9,11) or state['settings']['payment_type']!='cpc':continue
  existing={r['nm']for r in c.get('focus',[])}
  for n in state['nm_settings']:
   nm=n['nm_id']
   if nm in existing or nm in(1473245494,1473245510):continue
   dates=[dateof(x['at'])for x in changes if x.get('nm')==nm and (x['kind']in('bid','price')or x.get('cid')==c['id']and x['kind']in('added','returned','relaunch'))]
   if state.get('timestamps',{}).get('started'):dates.append(dateof(state['timestamps']['started']))
   changed=max(dates,default='1970-01-01')
   days=[d for d in raw.get('days',[])if d['date'][:10]in bundle['days']and d['date'][:10]<bundle['day']and d['date'][:10]>changed]
   rows=[r for d in days for a in d.get('apps',[])for r in a.get('nms',[])if r['nmId']==nm]
   if not rows:continue
   p={k:sum(r.get(f,0)for r in rows)for k,f in [('spend','sum'),('orders','orders'),('amount','sum_price'),('clicks','clicks'),('views','views')]}
   e=models.get(str(nm),{});margin=e.get('expected_margin_before_ads_cny')
   if p['spend']<=0 or not(p['orders']==0 or p['amount']>0 and p['spend']/p['amount']>.05 or isinstance(margin,(int,float))and margin*p['orders']<p['spend']):continue
   c.setdefault('focus',[]).append(dict(nm=nm,article=labels.get(nm,'WB '+str(nm)),period=p,comparison=dict(after=p,to_days=[d['date'][:10]for d in days]),daily=[],period_drr=100*p['spend']/p['amount']if p['amount']else None,decision='Проверить расход по завершённым дням.',reason='',action=None,completed_cost_scan=True))
 return out





