"""Owner-requested MPStats competitor reads. No WB, Telegram or model calls."""
import os,json
from datetime import datetime,timezone,timedelta
from analytics.mpstats_probe import discover,unpack_tool,sanitize,ProbeError
from analytics.collect import database
ROOT='china_agent:market_decline:2026-11-22:v3'
def save(key,p):
 database('POST','telegram_api_cache',body=dict(cache_key=ROOT+':'+key,payload=p,updated_at=datetime.now(timezone.utc).isoformat(),expires_at=(datetime.now(timezone.utc)+timedelta(days=365)).isoformat()),params={'on_conflict':'cache_key'})
def main():
 def extra(call,checks,known):
  def read(key,name,args):
   try:
    value=sanitize(unpack_tool(call('tools/call',dict(name=name,arguments=args))))
    save(key,dict(status='received',tool=name,arguments=args,data=value,observed_at=datetime.now(timezone.utc).isoformat()))
    return value
   except ProbeError as e:
    save(key,dict(status=e.status,detail=e.detail));return None
  read('category-daily','wb_category_stats',dict(path='Аксессуары/Сумки и рюкзаки/Сумки',report='by_date',d1='2026-11-08',d2='2026-11-21',fbs=1))
  for sku in [1338107746,1338107813,848046186,1361318850,1359585148,1363609764,2247132899,697189747]:
   read('sku-'+str(sku),'wb_sku',dict(sku=sku,report='by_period',d1='2026-11-08',d2='2026-11-21'))
  return dict(status='complete')
 r=discover(os.environ['MPSTATS_API_TOKEN'],read_checks=True,extra_reader=extra)
 save('discovery',dict(status=r.get('status'),executed_data_tools=r.get('executed_data_tools'),detail=r.get('detail')))
 print(json.dumps(dict(status=r.get('status'),calls=r.get('executed_data_tools'))))
if __name__=='__main__':main()
