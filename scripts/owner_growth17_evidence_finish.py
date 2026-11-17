"""Finish only missing MPStats evidence; reuse every completed WB/MSK stage."""
import os,json
from datetime import datetime,timezone
from china_cloud_cost_control import Cache,stamp
ROOT='china_agent:owner_growth_audit:2026-11-17:v1'
def main():
 c=Cache();assert c.create(ROOT+':missing_evidence_claim',dict(at=stamp(),wb_writes=0)),'No blind duplicate'
 fresh=c.get(ROOT+':fresh');assert fresh.get('pool_reconciliation')and fresh.get('economics')
 from analytics.mpstats_probe import discover
 from analytics.mpstats_gaps import execute_reads
 obs=[];audit=[]
 tasks=[dict(cabinet='token_3',tool='lk_wb_products',key='audit17-week-ready',priority=90,arguments=dict(date_from='2026-11-07',date_to='2026-11-09',start_row=0,end_row=1000))]
 for nm,pid in [(1473243913,149503444),(1473243915,149503446),(1473243442,149503391),(1535337769,149503563)]:
  tasks.append(dict(cabinet='token_3',tool='lk_wb_card_table',key='audit17-card:'+str(nm),priority=80,arguments=dict(type='products',value=pid,period_type='30days',self_redemption=False)))
 def persist(cabinet,row):obs.append(dict(cabinet=cabinet,observation=row))
 def extra(call,checks,known):return execute_reads(call,checks,known,tasks,{},persist,max_requests=5)
 try:result=discover(os.environ['MPSTATS_API_TOKEN'],read_checks=True,extra_reader=extra)
 except Exception as e:result=dict(error=type(e).__name__+': '+str(e)[:300])
 c.put(ROOT+':missing_evidence_raw',json.loads(json.dumps(dict(result=result,observations=obs,at=stamp(),wb_writes=0,telegram_calls=0,model_calls=0))))
 for item in obs:
  o=item['observation'];audit.append({k:o.get(k)for k in('key','tool','status','scope_verified','error','error_type')})
  if item['cabinet']!='token_3'or o.get('scope_verified')is not True or o.get('status')!='received':continue
  if o.get('tool')=='lk_wb_products'or 'week' in str(o.get('key','')):
   body=o.get('data',{}).get('data',{});rows=body.get('data')
   if isinstance(rows,list)and body.get('need_update')==0 and body.get('total')==len(rows):
    fields=('nm_id','sa_name','orders_count','orders_sum','open_card_count','add_to_cart_count','funnel_orders_count','price_after_discount','price_after_spp','price_spp','fbs_stock','days_in_stock')
    fresh['week_funnel']=dict(observed_at=stamp(),period_from='2026-11-07',period_to='2026-11-09',rows=[{k:r.get(k)for k in fields}for r in rows],source='MPStats all-source RUB');fresh['errors'].pop('week_funnel',None)
 fresh.update(status='complete'if not fresh['errors']else'partial',completed_at=stamp(),missing_evidence_audit=audit)
 c.put(ROOT+':fresh',json.loads(json.dumps(fresh)))
 print(json.dumps(dict(status=fresh['status'],errors=fresh['errors'],observations=audit,wb_writes=0,telegram_calls=0,model_calls=0)))
if __name__=='__main__':main()
