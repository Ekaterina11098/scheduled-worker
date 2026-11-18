"""Two-candidate read-only stock/economics refresh after verified cabinet thresholds."""
import requests,os,json
from urllib.parse import urlparse
from china_cloud_cost_control import Cache,WB,validate_identity,stamp
from china_moysklad_read import Reader
ROOT='china_agent:owner_blackfriday_gap:2026-11-18:v1'
ITEMS=[dict(nm_id=1473243818,article='529-NoelBag-lpink',current=210,target=207),dict(nm_id=1473243453,article='548-GloriaBag-brown',current=425,target=424)]
def main():
 c=Cache();assert c.create(ROOT+':claim:transport-fix1',dict(status='collecting',at=stamp()))
 orig=requests.sessions.Session.request
 def guard(s,method,url,*a,**k):
  u=urlparse(url);m=method.upper()
  ok=(u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname and u.path.startswith('/rest/v1/') and m in ('GET','POST','PATCH'))or(u.hostname=='api.moysklad.ru'and m=='GET'and u.path.startswith('/api/remap/1.2/'))
  assert ok,'Only private-cache and exact MSK read allowed'
  return orig(s,m,url,*a,**k)
 requests.sessions.Session.request=guard
 try:
  stock=Reader().stock([i['article']for i in ITEMS],'msk');assert stock['coverage_complete']
  source=c.get('china_agent:advertising_source:2026-11-18:v2');models=source['economics']['rows'];rows={r['article']:r for r in stock['rows']}
  out=dict(status='complete',observed_at=stamp(),stock=stock,rows=[],wb_writes=0,telegram_calls=0,model_calls=0,grants_action_permission=False)
  for i in ITEMS:
   e=models[str(i['nm_id'])];st=rows[i['article']];cost=st['price']/100;free=st['stock']-st['reserve'];q=e['buyout'];fx=e['fx_rub_per_cny'];coeff=1-(e['commission_pct']+e['tax_pct']+e['payment_reserve_pct'])/100
   margin=q*(i['target']*coeff-cost/fx)-e['logistics_cny']-e['handling_rub']/fx
   out['rows'].append(dict(i,stock_free=free,cogs_rub=cost,buyout=q,sample_size=e['sample_size'],sample_reliable=e['sample_reliable'],buyout_source_observed_at=e['observed_at'],margin_before_ads_cny=margin,margin_at_5pct_ads=margin-i['target']*.05,break_even_drr_pct=100*margin/i['target'],economics_source=e,preliminary=True,unknown_reverse_and_shared_costs=True))
  assert c.create(ROOT+':read',out)
  print(json.dumps(dict(status='complete',rows=len(out['rows']),wb_writes=0,telegram_calls=0)))
 finally:requests.sessions.Session.request=orig
if __name__=='__main__':main()
