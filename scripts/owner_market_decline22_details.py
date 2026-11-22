"""Owner-requested MPStats competitor reads. No WB, Telegram or model calls."""
import os,json
from datetime import datetime,timezone,timedelta
from analytics.mpstats_probe import discover,unpack_tool,sanitize,ProbeError
from analytics.collect import database
ROOT='china_agent:market_decline:2026-11-22:v2'
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
  read('kotland-info','wb_sku',dict(sku=2247132899,report='info'))
  read('kotland-sales','wb_sku',dict(sku=2247132899,report='sales',d1='2026-11-01',d2='2026-11-21'))
  cabinets=checks.get('lk_wb_cabinets',[])
  selected=[r['id']for r in cabinets if r.get('selected')]
  assert len(selected)<=1
  assert any(r.get('id')==10026946 and r.get('name')=='VESCHI Гонконг' and r.get('valid')is True for r in cabinets)
  try:
   read('select-china','lk_wb_cabinets',dict(action='select',id=10026946))
   scope=read('china-scope','lk_wb_cabinets',dict(action='list'))
   assert [r['id']for r in scope if r.get('selected')]==[10026946]
   read('own-funnel','lk_wb_dashboard_sales_funnel',dict(date_from='2026-11-08',date_to='2026-11-21',period_type='30days'))
   read('own-table','lk_wb_dashboard_table',dict(date_from='2026-11-08',date_to='2026-11-21',period_type='30days'))
  finally:
   read('restore-scope','lk_wb_cabinets',dict(action='select',id=selected[0])if selected else dict(action='reset'))
  return dict(status='complete')
 r=discover(os.environ['MPSTATS_API_TOKEN'],read_checks=True,extra_reader=extra)
 save('discovery',dict(status=r.get('status'),executed_data_tools=r.get('executed_data_tools'),detail=r.get('detail')))
 print(json.dumps(dict(status=r.get('status'),calls=r.get('executed_data_tools'))))
if __name__=='__main__':main()
