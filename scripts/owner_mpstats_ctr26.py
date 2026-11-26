"""One-off owner-authorized read of MPStats after Jam activation; no marketplace writes."""
import os,json,time
from datetime import datetime,timezone,timedelta
from analytics.mpstats_probe import discover,unpack_tool,sanitize,complete_products,ProbeError
from analytics.collect import database
ROOT='china_agent:mpstats_ctr_recheck:2026-11-26:v1'
DAY='2026-11-25'
def save(k,p):
 ts=datetime.now(timezone.utc)
 database('POST','telegram_api_cache',body=dict(cache_key=ROOT+':'+k,payload=p,updated_at=ts.isoformat(),expires_at=(ts+timedelta(days=365)).isoformat()),params={'on_conflict':'cache_key'})
def main():
 old=database('GET','telegram_api_cache',params={'cache_key':'eq.'+ROOT+':result','select':'cache_key'})
 if old:print('Already recorded; no replay');return
 save('started',dict(run_id=os.environ.get('GITHUB_RUN_ID'),observed_at=datetime.now(timezone.utc).isoformat(),period_from=DAY,period_to=DAY,wb_writes=0,browser_used=False,model_calls=0))
 scope=database('GET','telegram_api_cache',params={'cache_key':'eq.china_agent:owner_deadstock:2026-11-23:v1:scope','select':'payload'})[0]['payload']
 assert len(scope['items'])==24 and scope['extra_article']=='018-JuneBag-black'
 save('scope',dict(items=scope['items']+[dict(article=scope['extra_article'],nm_id=None,identity_status='resolve_exact_in_fresh_mpstats_catalog')],requested_count=25))
 def extra(call,checks,known):
  def tool(n,a):
   time.sleep(1)
   return sanitize(unpack_tool(call('tools/call',dict(name=n,arguments=a))))
  initial=[r['id'] for r in checks['lk_wb_cabinets'] if r.get('selected')]
  assert len(initial)<=1
  assert any(r.get('id')==10026946 and r.get('name')=='VESCHI Гонконг' and r.get('valid')is True for r in checks['lk_wb_cabinets'])
  changed=initial!=[10026946]
  try:
   if changed:tool('lk_wb_cabinets',dict(action='select',id=10026946))
   assert [r['id']for r in tool('lk_wb_cabinets',dict(action='list'))if r.get('selected')]==[10026946]
   for name in ['lk_wb_products','lk_wb_dashboard_sales_funnel','lk_wb_pulse_products']:
    if name not in known:
     save(name,dict(status='absent_from_fresh_catalog'));continue
    args=dict(date_from=DAY,date_to=DAY)
    if name in ['lk_wb_products','lk_wb_pulse_products']:args.update(start_row=0,end_row=1000)
    if name=='lk_wb_pulse_products':args['refresh']=False
    try:
     data=tool(name,args)
     if name=='lk_wb_products':data=complete_products(tool,args,data)
     save(name,dict(status='received',arguments=args,data=data,checked_at=datetime.now(timezone.utc).isoformat()))
    except ProbeError as e:
     save(name,dict(status=e.status,detail=e.detail,retry_after=e.retry_after))
     if e.retry_after:raise
  finally:
   if changed:tool('lk_wb_cabinets',dict(action='select',id=initial[0])if initial else dict(action='reset'))
   restored=[r['id']for r in tool('lk_wb_cabinets',dict(action='list'))if r.get('selected')]
   save('restoration',dict(initial=initial,restored=restored,verified=initial==restored))
   assert initial==restored
  return dict(status='complete')
 result=discover(os.environ['MPSTATS_API_TOKEN'],read_checks=True,extra_reader=extra)
 token=os.environ['MPSTATS_API_TOKEN'].strip()
 result=json.loads(json.dumps(result,ensure_ascii=False).replace(token,'[REDACTED]'))
 save('result',result)
 print('Read-only MPStats check:',result.get('status'),flush=True)
if __name__=='__main__':main()
