"""Addressed owner-requested manishki read-only review. No WB writes or Telegram."""
import sys,json,time,hashlib,datetime,requests
sys.path.insert(0,'scripts')
from owner_ad_tests23 import State,ReadWB,stamp
ROOT='ip_agent:manishki_review:2026-11-27:v1';HOST='advert-api.wildberries.ru'
IDS=[493953814,493953815,493953816,493953817,997991776,997991777,997991778];MAN=[997991776,997991777,997991778]
db=State();wb=ReadWB(db,'token_2');state=dict(status='reading',started_at=stamp(),wb_writes=0,telegram_sends=0,source_calls=0);deadline=time.time()+7200
def save():db.put(ROOT,state)
def call(label,host,path,method='GET',params=None,body=None):
 allowed={('GET',HOST,'/adv/v1/promotion/count'),('GET',HOST,'/api/advert/v3/adverts'),('POST',HOST,'/api/advert/v1/bids/min'),('POST','seller-analytics-api.wildberries.ru','/api/analytics/v3/sales-funnel/products'),('POST','discounts-prices-api.wildberries.ru','/api/v2/list/goods/filter')}
 if (method,host,path)not in allowed:raise PermissionError('Readonly endpoint boundary')
 key='wb-pause:'+hashlib.sha256((wb.token+host+path).encode()).hexdigest()
 for attempt in range(3):
  until=float((db.get(key)or{}).get('until',0))
  if until>deadline:raise RuntimeError('Cooldown exceeds bounded review')
  while until>time.time():
   state.update(status='waiting_provider',wait_endpoint=path,resume_after=datetime.datetime.fromtimestamp(until,datetime.timezone.utc).isoformat());save();time.sleep(min(25,max(.1,until-time.time())))
  state['source_calls']+=1;save()
  r=requests.request(method,'https://'+host+path,headers={'Authorization':wb.token},params=params,json=body,timeout=(10,70),allow_redirects=False)
  try:data=r.json()if r.content else{}
  except ValueError:data={'unparseable':True}
  raw=r.headers.get('X-Ratelimit-Retry')or r.headers.get('Retry-After')or r.headers.get('X-Ratelimit-Reset')
  try:delay=float(raw or 0)
  except ValueError:delay=0
  if delay>time.time()-86400:delay=max(0,delay-time.time())
  if r.status_code==429 or r.headers.get('X-Ratelimit-Remaining')=='0':db.put(key,dict(until=time.time()+max(3,delay)+5,basis='provider_header'))
  if r.status_code==429:state.setdefault('definite429',[]).append(dict(path=path,retry_after=delay,at=stamp()));save();continue
  state[label]=dict(http=r.status_code,data=data,observed_at=stamp());save()
  if not r.ok or isinstance(data,dict)and data.get('unparseable'):raise RuntimeError('WB HTTP'+str(r.status_code)+' '+path)
  return data
 raise RuntimeError('Bounded429retries exhausted')
if db.get(ROOT):raise SystemExit('Existing review retained; no replay')
if not db.put(ROOT,state,once=True):raise SystemExit('Review already claimed')
try:
 wb.identity()
 stock=call('stock','seller-analytics-api.wildberries.ru','/api/analytics/v3/sales-funnel/products','POST',body={'selectedPeriod':{'start':'2026-11-27','end':'2026-11-27'},'pastPeriod':{'start':'2026-11-26','end':'2026-11-26'},'nmIds':IDS,'skipDeletedNm':False,'limit':1000,'offset':0})
 if {r['product']['nmId']for r in stock['data']['products']}!=set(IDS):raise ValueError('Product coverage')
 prices=call('prices','discounts-prices-api.wildberries.ru','/api/v2/list/goods/filter','POST',body={'nmList':MAN})
 if {r['nmID']for r in prices['data']['listGoods']}!=set(MAN):raise ValueError('Price coverage')
 inv=call('catalog',HOST,'/adv/v1/promotion/count');active=sorted({r['advertId']for g in inv.get('adverts',[])if g['status']==9 for r in g.get('advert_list',[])})
 ids=sorted(set(active)|{40192945})
 if len(ids)>20:raise ValueError('Active scope bounds')
 cfg=call('configs',HOST,'/api/advert/v3/adverts',params={'advertIds':','.join(map(str,ids))})
 if {c['advertId']for c in cfg['adverts']}!=set(ids)or cfg.get('next'):raise ValueError('Configuration coverage')
 target=next(c for c in cfg['adverts']if c['advertId']==40192945);placements=target['settings']['placements'];subject=next(n['subject']['id']for n in target['nms']if n['nmId']==997991776)
 if subject!=756 or target['settings']['paymentType']!='cpc' or placements not in (['search'],['recommendations']):raise ValueError('Current category/payment/placement ambiguous')
 place='recommendation'if placements==['recommendations']else'search'
 call('minimum',HOST,'/api/advert/v1/bids/min','POST',body={'advert_id':40192945,'nm_ids':[997991776],'payment_type':'cpc','placement_types':[place]})
 state.update(status='complete',active_ids=active,observed_placement=placements,finished_at=stamp());save()
except Exception as e:state.update(status='attention',error=str(e)if isinstance(e,(PermissionError,RuntimeError,ValueError))else type(e).__name__,finished_at=stamp());save()
print(json.dumps({k:state.get(k)for k in('status','source_calls','error','wb_writes')}))
if state['status']!='complete':raise SystemExit(1)
