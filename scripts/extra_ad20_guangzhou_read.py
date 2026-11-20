"""Complete second-warehouse coverage for owner-requested assortment review; read only."""
import json,copy,time,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_advertising_v2 import http
from china_moysklad_read import read_stock
from china_campaign_routes import guangzhou_models
ROOT='china_agent:extra_advertising:2026-11-20:v1'
KEY=ROOT+':guangzhou'
def main():
 io=AdvertisingIO();v=io.get(ROOT);assert v and v.get('prices')
 p=io.get(KEY)or dict(status='collecting',wb_writes=0,telegram_calls=0,model_calls=0)
 route=copy.deepcopy((io.get('china_agent:campaign_economics_routes:v1')['campaigns']['41779660']))
 original=requests.sessions.Session.request
 def guard(session,method,url,*a,**kw):
  u=urlparse(url);m=method.upper();host=u.hostname or''
  if host=='api.telegram.org'or'openai'in host:raise ValueError('No Telegram/model')
  if host.endswith('wildberries.ru'):assert (m=='POST'and u.path in('/content/v2/get/cards/list','/api/v3/stocks/'+str(route['published_warehouse_id']),'/api/advert/v1/bids/min')),'No WB changes'
  if host.endswith('moysklad.ru'):assert m=='GET','No stock changes'
  return original(session,method,url,*a,**kw)
 requests.sessions.Session.request=guard
 def save():
  p['updated_at']=datetime.now(timezone.utc).isoformat()
  io.put(KEY,copy.deepcopy(p))if io.get(KEY)else io.create(KEY,p)
 if 'stock'not in p:p['stock']=read_stock([r['article']for r in v['prices']['rows']],warehouse_role='guangzhou');save()
 if 'published'not in p:
  mapping={str(sz):r['nm_id']for r in v['prices']['rows']for sz in r['size_ids']}
  r=requests.post('https://marketplace-api.wildberries.ru/api/v3/stocks/'+str(route['published_warehouse_id']),headers={'Authorization':io.token},json=dict(chrtIds=list(map(int,mapping))),timeout=50);r.raise_for_status()
  p['published']=dict(warehouse_id=route['published_warehouse_id'],size_to_nm=mapping,raw=r.json(),observed_at=datetime.now(timezone.utc).isoformat());save()
 if 'cards'not in p:
  rows=[];cursor={'limit':100};wanted={r['nm_id']for r in v['prices']['rows']};seen=set()
  for _ in range(20):
   rr=requests.post('https://content-api.wildberries.ru/content/v2/get/cards/list',headers={'Authorization':io.token},json={'settings':{'cursor':cursor,'filter':{'withPhoto':-1}}},timeout=50);rr.raise_for_status();data=rr.json()
   cards=data['cards'];rows.extend({k:c.get(k)for k in('nmID','vendorCode','dimensions','sizes','subjectID')}for c in cards if c['nmID']in wanted)
   seen.update(c['nmID']for c in cards)
   if data['cursor']['total']<100:break
   cursor={**data['cursor'],'limit':100};cursor.pop('total',None);time.sleep(.7)
  else:raise ValueError('Card pagination incomplete')
  assert len({r['nmID']for r in rows})==len(rows)
  p['cards']=dict(rows=rows,observed_at=datetime.now(timezone.utc).isoformat());save()
 if 'economics'not in p:
  stock={r['article']:r for r in p['stock']['rows']};cards={r['nmID']:r for r in p['cards']['rows']}
  amounts={str(n):0 for n in p['published']['size_to_nm'].values()};seen=set()
  for s in p['published']['raw']['stocks']:
   nm=p['published']['size_to_nm'][str(s.get('chrtId',s.get('chrtID')))];amounts[str(nm)]+=s['amount'];seen.add(nm)
  ids={r['nm_id']for r in v['prices']['rows']if r['nm_id']in cards and r['nm_id']in seen and stock.get(r['article'],{}).get('stock',0)-stock.get(r['article'],{}).get('reserve',0)>0 and amounts[str(r['nm_id'])]>0}
  old=io.get('china_agent:advertising_full_growth:2026-11-20:v1:inputs');route['nm_ids']=sorted(ids)
  ev=dict(stock=p['stock'],cards=p['cards'],published=p['published'])
  # Only exact IDs with stock and published availability enter the unit model.
  ev['published']=copy.deepcopy(p['published']);ev['published']['raw']['stocks']=[s for s in ev['published']['raw']['stocks']if p['published']['size_to_nm'][str(s.get('chrtId',s.get('chrtID')))]in ids]
  inputs=dict(old,prices=v['prices']);p['economics']=guangzhou_models(inputs,route,ev,io.get('china_agent:new_ad_economics_policy:v1'));p['eligible_nm_ids']=sorted(ids);p['route']=route;save()
 if 'extra_category_quotes'not in p:
  old=io.get('china_agent:advertising_full_growth:2026-11-20:v1:inputs');quotes={}
  for cp in old['campaigns']:
   for n in cp.get('nm_settings',[]):
    subject=n['subject']['id'];zone='search'
    if subject!=280 or str(subject)+':search'in quotes:continue
    # Category identity is read from the actual campaign; no invented minimum.
    q=http(io,'/api/advert/v1/bids/min','POST',dict(advert_id=cp['id'],nm_ids=[n['nm_id']],payment_type='cpc',placement_types=['search']))
    quotes[str(subject)+':search']=dict(subject_id=subject,campaign_id=cp['id'],nm_id=n['nm_id'],response=q,observed_at=datetime.now(timezone.utc).isoformat())
  p['extra_category_quotes']=quotes;save()
 p['status']='complete';save();print(json.dumps(dict(status='complete',stock_rows=len(p['stock']['rows']),available_models=len(p['economics']['rows']),wb_writes=0,telegram_calls=0,model_calls=0)))
if __name__=='__main__':main()

