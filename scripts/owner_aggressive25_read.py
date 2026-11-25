"""One bounded saved read for a second-stage advertising proposal. No mutations."""
import json,time,requests
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_cloud_cost_control import Cache,WB,validate_identity
from china_hourly_sales_read import read_orders,select_rows,aggregate,comparison
ROOT='china_agent:owner_aggressive25:v1:read'
def main():
 io=AdvertisingIO();old=io.get(ROOT)
 if old:print('Read checkpoint already exists; inspect, do not repeat');return
 validate_identity(Cache(),WB());clock=datetime.now(ZoneInfo('Europe/Moscow'));end=clock.replace(minute=0,second=0,microsecond=0)
 out=dict(status='reading',observed_at=datetime.now(timezone.utc).isoformat(),cut_msk=end.isoformat(),orders={},errors={},wb_writes=0,telegram_calls=0,model_calls=0);assert io.create(ROOT,out)
 def save():io.put(ROOT,json.loads(json.dumps(out)))
 original=requests.sessions.Session.request
 def guard(s,method,url,*a,**kw):
  u=urlparse(url);m=method.upper();ok=u.hostname==urlparse(io.url).hostname and u.path.startswith('/rest/v1/')and m in('GET','POST','PATCH')
  if u.hostname=='marketplace-api.wildberries.ru':ok=m=='GET'and u.path in('/api/v3/orders','/api/v3/orders/new')
  if u.hostname=='advert-api.wildberries.ru':ok=m=='GET'and u.path in('/api/advert/v2/adverts','/adv/v3/fullstats')
  assert ok,'Read-only scope';return original(s,method,url,*a,**kw)
 requests.sessions.Session.request=guard
 def req(host,path,params=None):
  time.sleep(1.5);r=requests.get('https://'+host+path,params=params,headers={'Authorization':io.token},timeout=55)
  if not r.ok:raise ValueError('Read HTTP '+str(r.status_code))
  return r.json()
 try:
  slot=io.get('china_agent:hourly_sales_api:v1:snapshot:'+end.strftime('%Y-%m-%dT%H')+':MSK')or{}
  new=None
  for d in(0,1,7):
   try:
    if slot.get('orders',{}).get(str(d),{}).get('status')=='complete':out['orders'][str(d)]=slot['orders'][str(d)];save();continue
    if new is None:new=req('marketplace-api.wildberries.ru','/api/v3/orders/new')['orders']
    cut=end-timedelta(days=d);start=cut.replace(hour=0);raw=read_orders(lambda p,par:req('marketplace-api.wildberries.ru',p,par),start,cut);raw.update({r['id']:r for r in new});rows=select_rows(raw.values(),start,cut);tot=aggregate(rows);assert not tot['unknown_amount_ids']
    out['orders'][str(d)]=dict(status='complete',rows=rows,totals=tot,start_msk=start.isoformat(),end_msk=cut.isoformat(),last_completed_hour=aggregate(select_rows(raw.values(),cut-timedelta(hours=1),cut)),observed_at=datetime.now(timezone.utc).isoformat());save()
   except Exception as e:out['errors']['orders'+str(d)]=str(e)if isinstance(e,ValueError)else type(e).__name__;save()
  if len(out['orders'])==3:out['sales_comparisons']={str(d):comparison(out['orders']['0']['totals'],out['orders'][str(d)]['totals'])for d in(1,7)};save()
  base=io.get('china_agent:hourly_sales_api:v1:snapshot:2026-11-25T12:MSK');ids=sorted(int(cid)for cid,c in base['advertising']['campaigns'].items()if c['status']==9)
  try:
   states=req('advert-api.wildberries.ru','/api/advert/v2/adverts',dict(ids=','.join(map(str,ids))))['adverts'];out['campaigns']=states;save()
   out['stats']=req('advert-api.wildberries.ru','/adv/v3/fullstats',dict(ids=','.join(map(str,ids)),beginDate='2026-11-25',endDate='2026-11-25'));out['ads_observed_at']=datetime.now(timezone.utc).isoformat();out['missing_stats_ids']=sorted(set(ids)-{s['advertId']for s in out['stats']});save()
  except Exception as e:out['errors']['advertising']=str(e)if isinstance(e,ValueError)else type(e).__name__;save()
  out.update(status='complete'if not out['errors']else'partial',completed_at=datetime.now(timezone.utc).isoformat());save();print(json.dumps(dict(status=out['status'],errors=out['errors'],cut=out['cut_msk'],writes=0)))
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()