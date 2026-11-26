"""Complete pagination and distinguish advertised views from all-card impressions."""
import os,json,time
from owner_mpstats_ctr26 import save,ROOT,DAY
from analytics.mpstats_probe import discover,unpack_tool,sanitize,ProbeError
from analytics.collect import database
def get(k):
 r=database('GET','telegram_api_cache',params={'cache_key':'eq.'+ROOT+':'+k,'select':'payload'})
 return r[0]['payload']if len(r)==1 else None
def main():
 if get('followup_result'):print('Already recorded');return
 catalog=get('result')['tools']
 def extra(call,checks,known):
  def tool(n,a):
   time.sleep(1)
   return sanitize(unpack_tool(call('tools/call',dict(name=n,arguments=a))))
  initial=[r['id'] for r in checks['lk_wb_cabinets']if r.get('selected')]
  assert len(initial)<=1
  assert any(r.get('id')==10026946 and r.get('name')=='VESCHI Гонконг' and r.get('valid')is True for r in checks['lk_wb_cabinets'])
  changed=initial!=[10026946]
  try:
   if changed:tool('lk_wb_cabinets',dict(action='select',id=10026946))
   assert [r['id']for r in tool('lk_wb_cabinets',dict(action='list'))if r.get('selected')]==[10026946]
   raw=get('lk_wb_pulse_products')['data']
   total=raw['total'];rows=raw['products']
   assert 0<=len(rows)<=total<=1000 and raw['period']==dict(to=DAY,**{'from':DAY})
   while len(rows)<total:
    args=dict(date_from=DAY,date_to=DAY,start_row=len(rows),end_row=min(len(rows)+100,total),refresh=False)
    page=tool('lk_wb_pulse_products',args)
    assert page['total']==total and page['period']==raw['period'] and page['products']
    save('pulse_page_'+str(len(rows)),dict(arguments=args,data=page))
    rows.extend(page['products'])
   assert len(rows)==total and len({r['sku']for r in rows})==len(rows)
   save('pulse_complete',dict(status='received',period=raw['period'],total=total,products=rows,pagination_complete=True))
   args=dict(date_from=DAY,date_to=DAY,groups=['funnel','advert_stats'],refresh=False)
   value=tool('lk_wb_pulse_summary',args)
   save('lk_wb_pulse_summary',dict(status='received',arguments=args,data=value))
  finally:
   if changed:tool('lk_wb_cabinets',dict(action='select',id=initial[0])if initial else dict(action='reset'))
   restored=[r['id']for r in tool('lk_wb_cabinets',dict(action='list'))if r.get('selected')]
   save('followup_restoration',dict(initial=initial,restored=restored,verified=initial==restored))
   assert initial==restored
  return dict(status='complete')
 result=discover(os.environ['MPSTATS_API_TOKEN'],read_checks=True,extra_reader=extra,catalog=catalog)
 save('followup_result',result)
 print('Read-only paginated probe:',result.get('status'))
if __name__=='__main__':main()
