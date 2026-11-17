"""Explicit warehouse routes for economic evidence, never changes a selling route."""
import copy,math,json,time
from datetime import datetime,timezone,timedelta
POLICY='china_agent:campaign_economics_routes:v1'
ROOT='china_agent:campaign_route_evidence:'
def stamp():return datetime.now(timezone.utc).isoformat()
def fresh(at,h=24):
 try:return timedelta(0)<=datetime.now(timezone.utc)-datetime.fromisoformat(at.replace('Z','+00:00'))<=timedelta(hours=h)
 except (ValueError,TypeError,AttributeError):return False
def guangzhou_models(v,route,evidence,policy):
 from china_advertising_economic_review import model_rows
 if evidence['stock'].get('warehouse_id')!=route['warehouse_id']or evidence['published'].get('warehouse_id')!=route['published_warehouse_id']:
  raise ValueError('Route warehouse identity mismatch')
 if evidence['stock'].get('coverage_complete')is not True:raise ValueError('Route stock incomplete')
 ids=set(route['nm_ids']);prices=dict(v['prices'],rows=[p for p in v['prices']['rows']if p['nm_id']in ids])
 if {p['nm_id']for p in prices['rows']}!=ids:raise ValueError('Routed prices incomplete')
 cards={c['nmID']:c for c in evidence['cards']['rows']};po=copy.deepcopy(policy)
 po.setdefault('planned_buyout_by_nm',{});po.setdefault('logistics_by_nm',{})
 for nm in ids:
  weight=cards[nm]['dimensions'].get('weightBrutto')
  if type(weight)not in(int,float)or not 0<weight<10:raise ValueError('Exact packaged weight invalid')
  delivery=math.ceil(weight*10-1e-9)/10*route['tariff_cny_per_kg']+route['tariff_fixed_cny']
  po['logistics_by_nm'][str(nm)]=dict(delivery_cny=delivery,route='Guangzhou_FBS',delivery_source=route['source_ref'])
  po['planned_buyout_by_nm'][str(nm)]=dict(probability=route['planned_buyout'],source_ref=route['source_ref'])
 inputs=dict(products=v['own'],prices=prices,stock=evidence['stock'],fx=dict(rub_per_cny=v['fx']['rub_per_cny']))
 out=model_rows(inputs,po,{})
 if out['missing']or set(out['rows'])!={str(nm)for nm in ids}:raise ValueError('Routed economics incomplete')
 pub=evidence['published'];amounts={str(nm):0 for nm in ids};seen=set()
 for row in pub['raw'].get('stocks',[]):
  nm=pub['size_to_nm'].get(str(row.get('chrtId',row.get('chrtID'))))
  if nm is None:raise ValueError('Unexpected published route size')
  seen.add(nm);amounts[str(nm)]+=row['amount']
 # Missing sizes are unknown, not zero. All exact requested nms must be returned.
 if seen!=ids:raise ValueError('Routed published coverage incomplete')
 for nm,e in out['rows'].items():e.update(warehouse_role='guangzhou',warehouse_id=evidence['stock']['warehouse_id'],
  stock_basis='Guangzhou stock minus reserve',published_warehouse_id=pub['warehouse_id'],published_stock=amounts[nm],
  published_stock_observed_at=pub['observed_at'],packaged_weight_kg=cards[int(nm)]['dimensions']['weightBrutto'],
  fx_rub_per_cny=float(v['fx']['rub_per_cny']),fx_date=v['fx'].get('date'),route_policy_ref=route['source_ref'])
 return out
def collect(io,v,source,day):
 policy=io.get(POLICY)or{};states={c['id']:c for b in source.get('batches',{}).values()for c in b['campaigns'].get('adverts',[])}
 for cid,route in policy.get('campaigns',{}).items():
  state=states.get(int(cid))
  if not state or state.get('status')not in(9,11):continue
  ids={n['nm_id']for n in state['nm_settings']}
  if route.get('warehouse_role')!='guangzhou':raise ValueError('Explicit campaign warehouse route changed')
  if ids!=set(route['nm_ids']):
   registry=io.get('china_agent:verified_campaign_state:v1')or{}
   receipt=io.get(registry.get(cid,''))or{};after=receipt.get('after')or{}
   if receipt.get('status')!='verified'or after.get('id')!=state['id']or {n['nm_id']for n in after.get('nm_settings',[])}!=ids:raise ValueError('Campaign route membership has no matching verified receipt')
   route=dict(route,nm_ids=sorted(ids),composition_receipt=registry[cid]);policy['campaigns'][cid]=route;io.put(POLICY,policy)
  key=ROOT+day+':v1:'+cid;evidence=io.get(key)
  if not evidence or not fresh(evidence.get('stock',{}).get('observed_at'))or not fresh(evidence.get('published',{}).get('observed_at')):
   import requests
   from china_moysklad_read import read_stock
   def req(host,path,body):
    time.sleep(.8);r=requests.post('https://'+host+path,json=body,headers={'Authorization':io.token},timeout=(10,50));r.raise_for_status();return r.json()
   prices=[p for p in v['prices']['rows']if p['nm_id']in ids];articles=[p['article']for p in prices]
   if len(articles)!=len(ids):raise ValueError('Route price coverage incomplete')
   stock=read_stock(articles,warehouse_role='guangzhou')
   if stock.get('warehouse_id')!=route['warehouse_id']or not stock.get('coverage_complete'):raise ValueError('Exact GUA warehouse evidence missing')
   cards_key='china_agent:campaign_route_cards:v1:'+cid;cards=io.get(cards_key)
   if not cards or not fresh(cards.get('observed_at'),24*7)or {r['nmID']for r in cards.get('rows',[])}!=ids:
    rows=[]
    for nm in sorted(ids):
     data=req('content-api.wildberries.ru','/content/v2/get/cards/list',dict(settings=dict(cursor=dict(limit=100),filter=dict(textSearch=str(nm),withPhoto=-1))))
     found=[r for r in data.get('cards',[])if r.get('nmID')==nm]
     if len(found)!=1:raise ValueError('Route card missing')
     rows.append({k:found[0].get(k)for k in('nmID','vendorCode','dimensions','sizes')})
    cards=dict(rows=rows,observed_at=stamp());io.put(cards_key,cards)if io.get(cards_key)else io.create(cards_key,cards)
   mapping={str(sz['chrtID']):r['nmID']for r in cards['rows']for sz in r['sizes']}
   published=dict(warehouse_id=route['published_warehouse_id'],observed_at=stamp(),size_to_nm=mapping,
     raw=req('marketplace-api.wildberries.ru','/api/v3/stocks/'+str(route['published_warehouse_id']),dict(chrtIds=[int(k)for k in mapping])))
   evidence=dict(stock=stock,cards=cards,published=published,wb_writes=0,telegram_calls=0)
   io.put(key,evidence)if io.get(key)else io.create(key,evidence)
  models=guangzhou_models(v,route,evidence,io.get('china_agent:new_ad_economics_policy:v1')or{})
  v['economics']['rows'].update(models['rows'])
  for nm in models['rows']:v['economics']['missing'].pop(nm,None)
  v.setdefault('campaign_routes',{})[cid]=dict(warehouse_role='guangzhou',evidence_key=key,source_ref=route['source_ref'])
 return v
