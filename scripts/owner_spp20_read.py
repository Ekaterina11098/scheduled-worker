"""Single MPStats buyer-price observation; no marketplace or Telegram mutations."""
import os,json
from datetime import datetime,timezone
from analytics.mpstats_probe import discover
from analytics.mpstats_gaps import execute_reads
from china_cloud_cost_control import Cache
ROOT='china_agent:spp_review20:v1'
def main():
 c=Cache();scope=c.get('china_agent:sales_drop20:v1:request');ids=set(scope['nm_ids'])
 out=dict(status='collecting',wb_writes=0,telegram_calls=0,model_calls=0,started_at=datetime.now(timezone.utc).isoformat())
 assert c.create(ROOT,out)
 observations=[]
 tasks=[dict(cabinet='token_3',tool='lk_wb_products',key='owner-spp20-current',priority=80,arguments=dict(date_from='2026-11-20',date_to='2026-11-20',start_row=0,end_row=1000))]
 def persist(cabinet,obs):
  if cabinet=='token_3'and obs.get('scope_verified')is True and obs.get('status')=='received':observations.append(obs)
 def extra(call,checks,known):return execute_reads(call,checks,known,tasks,{},persist,max_requests=1)
 try:
  discover(os.environ['MPSTATS_API_TOKEN'],read_checks=True,extra_reader=extra)
  assert len(observations)==1,'No complete scoped MPStats response'
  body=observations[0]['data']['data'];rows=body['data'];assert body.get('total')==len(rows),'Incomplete page'
  keys=['nm_id','sa_name','price','price_before_discount','price_after_discount','price_spp','price_after_spp','price_final','price_discount','last_update','updated_at']
  out.update(status='complete'if body.get('need_update')==0 else'pending_source_refresh',need_update=body.get('need_update'),source_total=len(rows),rows=[{k:r[k]for k in keys if k in r}for r in rows if int(r['nm_id'])in ids],observed_at=datetime.now(timezone.utc).isoformat(),period=['2026-11-20','2026-11-20'])
 except Exception as e:out.update(status='blocked',error=str(e)[:300])
 c.put(ROOT,out);print(json.dumps(dict(status=out['status'],rows=len(out.get('rows',[])))))
if __name__=='__main__':main()
