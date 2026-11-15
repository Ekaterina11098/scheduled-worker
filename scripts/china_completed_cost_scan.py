"""Find completed-day cost risks across every current SKU, not only the initial shortlist."""
import copy
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
def expand(bundle,source,minima):
 if not bundle.get('day')or not bundle.get('days'):return copy.deepcopy(bundle)
 from china_advertising_v2 import history
 out=copy.deepcopy(bundle);changes=history(source.get('executions',[]));MSK=ZoneInfo('Europe/Moscow')
 for cid,q in (source.get('full_growth_inputs',{}).get('minimums')or{}).items():
  for r in q.get('bids',[]):
   values=[v['value']for v in r['bids']if v.get('currency')=='CNY']
   if len(values)==1:minima.setdefault(str(cid)+':'+str(r['nm_id']),values[0])
 labels={int(r['nmID']):r['vendorCode']for r in source.get('catalogue',{}).get('rows',[])}
 states={c['id']:c for b in source['batches'].values()for c in b['campaigns']['adverts']}
 stats={c['advertId']:c for b in source['batches'].values()for c in b['stats']}
 models=source.get('economics',{}).get('rows',{})
 def dateof(x):return datetime.fromisoformat(x.replace('Z','+00:00')).astimezone(MSK).date().isoformat()
 for c in out['campaigns']:
  state=states.get(c['id']);raw=stats.get(c['id'])
  if not state or not raw or state['status']!=9 or state['settings']['payment_type']!='cpc':continue
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


