"""Owner-requested six-fur read only. No WB mutations, Telegram or model calls."""
import os,json,requests
from china_cloud_cost_control import Cache,stamp
from china_morning_readiness import current_prices,published_stock
from china_moysklad_read import read_stock
IDS=[2216217906,2216257724,2216045897,2215883910,2216111729,2216167898]
KEY='china_agent:owner_fur_search:2026-11-16:v1:read'
class ReadIO:
 def __init__(self):self.token=os.environ['WB_TOKEN_3']
 def wb(self,path):
  r=requests.get('https://discounts-prices-api.wildberries.ru'+path,headers={'Authorization':self.token},timeout=45)
  if not r.ok:raise RuntimeError('Price read HTTP '+str(r.status_code))
  return r.json()['data']
def main():
 c=Cache()
 if not c.create(KEY+':claim',dict(observed_at=stamp(),wb_writes=False)):raise RuntimeError('Already claimed; inspect cache')
 out=dict(status='collecting',observed_at=stamp(),wb_writes=False,telegram_calls=0,model_calls=0,errors={})
 io=ReadIO()
 def read(name,fn):
  try:out[name]=fn()
  except Exception as e:out['errors'][name]=str(e)[:180]
  c.put(KEY,out)
 def ad(path,body=None):
  url='https://advert-api.wildberries.ru'+path
  r=requests.get(url,headers={'Authorization':io.token},timeout=45) if body is None else requests.post(url,headers={'Authorization':io.token},json=body,timeout=45)
  if not r.ok:raise RuntimeError('Advertising read HTTP '+str(r.status_code))
  return r.json()
 read('campaign',lambda:ad('/api/advert/v2/adverts?ids=41756218'))
 read('minimums',lambda:ad('/api/advert/v1/bids/min',dict(advert_id=41756218,nm_ids=IDS,payment_type='cpc',placement_types=['search','recommendation'])))
 read('prices',lambda:current_prices(io,IDS))
 if 'prices' in out:
  read('published_stock',lambda:published_stock(io,out['prices'],IDS))
  read('msk_stock_cogs',lambda:read_stock([x['article'] for x in out['prices']['rows']]))
 out.update(status='complete' if not out['errors'] else 'partial',completed_at=stamp())
 c.put(KEY,out)
 print(json.dumps(dict(status=out['status'],errors=out['errors'],source_key=KEY)))
if __name__=='__main__':main()
