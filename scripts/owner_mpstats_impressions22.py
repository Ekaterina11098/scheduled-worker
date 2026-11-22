"""MPStats API capability test: two own-card reads, no WB/TG/model."""
import os,json
from datetime import datetime,timezone,timedelta
from analytics.mpstats_probe import discover,unpack_tool,sanitize
from analytics.collect import database
ROOT='china_agent:mpstats_impressions_api:2026-11-22:v1'
def save(key,p):
 database('POST','telegram_api_cache',body=dict(cache_key=ROOT+':'+key,payload=p,updated_at=datetime.now(timezone.utc).isoformat(),expires_at=(datetime.now(timezone.utc)+timedelta(days=365)).isoformat()),params={'on_conflict':'cache_key'})
def main():
 def extra(call,checks,known):
  def tool(n,args):return sanitize(unpack_tool(call('tools/call',dict(name=n,arguments=args))))
  initial=[r['id']for r in checks['lk_wb_cabinets']if r.get('selected')];assert len(initial)<=1
  assert any(r.get('id')==10026946 and r.get('name')=='VESCHI Гонконг' and r.get('valid')is True for r in checks['lk_wb_cabinets'])
  try:
   tool('lk_wb_cabinets',dict(action='select',id=10026946))
   assert [r['id']for r in tool('lk_wb_cabinets',dict(action='list'))if r.get('selected')]==[10026946]
   for name in ['lk_wb_card_table','lk_wb_card_widget']:
    args=dict(type='products',value='149503425',period_type='30days',self_redemption=False)
    try:save(name,dict(status='received',tool=name,arguments=args,data=tool(name,args),observed_at=datetime.now(timezone.utc).isoformat()))
    except Exception as e:save(name,dict(status='failed',error=type(e).__name__))
  finally:tool('lk_wb_cabinets',dict(action='select',id=initial[0])if initial else dict(action='reset'))
  return dict(status='complete')
 r=discover(os.environ['MPSTATS_API_TOKEN'],read_checks=True,extra_reader=extra)
 save('result',dict(status=r.get('status'),calls=r.get('executed_data_tools'),detail=r.get('detail')))
 print(r.get('status'))
if __name__=='__main__':main()
