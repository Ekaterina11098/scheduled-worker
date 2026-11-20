"""One fresh FBS reread, fixed historical window; no ad/price/TG/model calls."""
import requests,json
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from china_advertising_state import AdvertisingIO
from china_hourly_sales_read import read_orders,select_rows,aggregate
ROOT='china_agent:sales_drop20:v2:fresh'
def main():
 io=AdvertisingIO();out=dict(status='collecting',wb_writes=0,telegram_calls=0,model_calls=0,orders={})
 assert io.create(ROOT,out),'Already collected: inspect existing result'
 def save():io.put(ROOT,out)
 def get(path,params=None):
  assert path in('/api/v3/orders','/api/v3/orders/new')
  r=requests.get('https://marketplace-api.wildberries.ru'+path,headers={'Authorization':io.token},params=params,timeout=45);r.raise_for_status();return r.json()
 try:
  cut=datetime.now(ZoneInfo('Europe/Moscow')).replace(microsecond=0);out['cut_msk']=cut.isoformat()
  new=get('/api/v3/orders/new')['orders']
  for off in(0,1,7):
   end=cut-timedelta(days=off);start=end.replace(hour=0,minute=0,second=0);raw=read_orders(get,start,end)
   for r in new:raw[r['id']]=r
   rows=select_rows(raw.values(),start,end)
   out['orders'][str(off)]=dict(rows=rows,totals=aggregate(rows),end_msk=end.isoformat());save()
  out.update(status='complete',observed_at=datetime.now(timezone.utc).isoformat());save()
 except Exception as ex:out.update(status='blocked',error=str(ex)[:200]);save();raise
 print(json.dumps(dict(status=out['status'],wb_writes=0)))
if __name__=='__main__':main()
