"""Cached shared-contract review only. No marketplace/TG/model requests."""
import copy,json,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_advertising_decision_contract import finalize
io=AdvertisingIO();root='china_agent:owner_winners63_27:v1'
orig=requests.sessions.Session.request
def guard(s,m,u,*a,**k):
 p=urlparse(u);assert p.hostname==urlparse(io.url).hostname and p.path.startswith('/rest/v1/'),'Cache only'
 return orig(s,m,u,*a,**k)
requests.sessions.Session.request=guard
try:
 fresh=io.get(root+':result');stock=io.get(root+':stock')['stock'];scope=io.get(root+':scope')['items'];wanted={x['nm']for x in scope};labels={x['nm']:x['article']for x in scope}
 source=copy.deepcopy(io.get(root+':contract_input'));inp=io.get('china_agent:advertising_full_growth:2026-11-26:v1:inputs:midday')
 existing={r['advertId']:copy.deepcopy(r)for b in source['batches'].values()for r in b.get('stats',[])}
 for r in []:
  cp=existing.setdefault(r['advertId'],dict(advertId=r['advertId'],days=[]));cp['days']=[d for d in cp['days']if d['date'][:10]!='2026-11-26']+copy.deepcopy(r['days'])
 source['batches']={'scope':dict(campaigns=dict(adverts=fresh['campaigns']['data']),stats=list(existing.values()))};source['config']=fresh['config']['data'];source['period_to']='2026-11-26';source['target_drr_pct']=8
 source['full_growth_inputs']=dict(prices=fresh['prices']['data'],published_stock=fresh['published']['data']);source['catalogue']=dict(rows=[dict(nmID=x['nm'],vendorCode=x['article'])for x in scope])
 econ=copy.deepcopy(inp['economics']);econ['rows']={k:v for k,v in econ['rows'].items()if int(k)in wanted};pr={x['nm_id']:x for x in fresh['prices']['data']['rows']};st={x['article'].casefold():x for x in stock['rows']}
 for k,m in econ['rows'].items():
  nm=int(k);s=st[labels[nm].casefold()];free=s['stock']-s['reserve'];price=pr[nm]['seller_price'];cost=s['price']/100
  m.update(stock_free=free,stock_observed_at=stock['observed_at'],price_observed_at=fresh['prices']['observed_at'],seller_price_cny=price,published_stock=fresh['published']['data']['amounts'].get(k),published_stock_observed_at=fresh['published']['observed_at'])
  if free>0 and m.get('buyout')is not None:m.update(own_cogs_rub=cost*m['fx_rub_per_cny'],expected_margin_before_ads_cny=m['buyout']*(price*(1-(m['commission_pct']+m['tax_pct']+m['payment_reserve_pct'])/100)-cost)-m['logistics_cny']-m['handling_rub']/m['fx_rub_per_cny'],cost_source_currency='CNY')
 source['economics']=econ
 for key in('china_agent:owner_decline179_price26:v1:execution','china_agent:owner_missed58_price26:v1:execution','china_agent:owner_checkout47_price27:v2:execution'):
  e=io.get(key);pass # Exact price timestamps below; do not load unrelated execution snapshots into review
  source.setdefault('experience',[]).append(dict(status='verified',started_at=e['verified_at'],action=dict(kind='price_change',nm_ids=[int(n)for n in e['after']if int(n)in wanted])))
 minima={}
 for key,v in fresh.items():
  if key.startswith('min_'):
   cid=int(key.split('_')[1])
   for r in v['data']['bids']:
    vals=[b['value']for b in r['bids']if b['currency']=='CNY']
    if len(vals)==1:minima[str(cid)+':'+str(r['nm_id'])]=vals[0]
 candidates={str(x['cid'])+':'+str(x['nm']):x for x in io.get(root+':proposed_tests')['rows']}
 cps=[]
 for c in fresh['campaigns']['data']:
  focus=[]
  for n in c['nm_settings']:
   nm=n['nm_id']
   if nm not in wanted:continue
   row=dict(nm=nm,article=labels[nm],period=dict(spend=0,orders=0,amount=0,clicks=0,views=0),daily=[],action=None,decision='Поддерживать текущий охват; проверить усиление.',reason='')
   test=candidates.get(str(c['id'])+':'+str(nm))
   if test:
    zone='search'if c['settings']['placements']['search']else'recommendations'
    row.update(action=dict(kind='ad_set_bid',direction='raise',campaign_id=c['id'],nm_id=nm,old_minor=round(test['old']*100),target_minor=round(test['bid']*100),placement=zone),decision='Предварительный тест повышения.')
   focus.append(row)
  if focus:cps.append(dict(id=c['id'],status=c['status'],payment='cpc',name=c['settings']['name'],focus=focus,period=dict(spend=0,amount=0,orders=0),attention=[]))
 out=finalize(None,dict(day='2026-11-27',days=['2026-11-23','2026-11-24','2026-11-25','2026-11-26'],campaigns=cps,target_drr_pct=8),source,minima)
 out['campaigns']=[dict(c,focus=[r for r in c['focus']if r['nm']in wanted])for c in out['campaigns']]
 out.update(scope_nm_ids=sorted(wanted),wb_writes=0,telegram_calls=0,executed=False,warning='26Nov hourly advertising is23:07partial snapshot; not full26day. No completed post26price day exists. Candidate bids remain proposals, not ready actions.',observed_at=datetime.now(timezone.utc).isoformat())
 assert io.create(root+':contract_review',out)
 print('Saved shared-contract preview')
except Exception as ex:
 key=root+':contract_error';value=dict(error=type(ex).__name__+': '+str(ex),observed_at=datetime.now(timezone.utc).isoformat())
 io.put(key,value)if io.get(key)else io.create(key,value)
 raise
finally:requests.sessions.Session.request=orig
