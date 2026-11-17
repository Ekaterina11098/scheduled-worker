"""Pre-stage the normal daily price task; release through its existing transport."""
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import time
MSK=ZoneInfo('Europe/Moscow')
def release_time(day,mode='morning'):
 return datetime.combine(day,datetime.min.time(),MSK).replace(hour=10 if mode=='morning'else 15,minute=30 if mode=='morning'else 0)
def wait_for_release(worker):
 target=getattr(worker,'scheduled_release_at',None)
 if target is None:return
 if datetime.now(MSK).date()!=worker.day:raise RuntimeError('Scheduled report day changed')
 if datetime.now(timezone.utc)<target:
  rows=worker.patch(dict(lease_until=(target+timedelta(minutes=15)).isoformat()))
  if len(rows)!=1:raise RuntimeError('Scheduled delivery lost task lease')
  worker.audit['prepared_before_release_at']=datetime.now(timezone.utc).isoformat()
  worker.save('china_agent:scheduled_price_release:'+str(worker.day)+':'+worker.mode,dict(status='prepared_waiting_time',job_id=worker.job['id'],target_at=target.isoformat(),prepared_at=worker.audit['prepared_before_release_at'],wb_writes=0,model_calls=0))
 while (seconds:=(target-datetime.now(timezone.utc)).total_seconds())>0:time.sleep(min(seconds,1))
 hold=worker.get('china_agent:price_publication_hold:'+str(worker.day)+':v1')or{}
 if hold.get('status')=='held_by_owner'and hold.get('owner_id')==5122667182:raise RuntimeError('Owner holds this dated price publication')
 worker.audit['release_attempt_at']=datetime.now(timezone.utc).isoformat()
def main():
 from china_price_state_transport import install
 install()
 from china_agent.morning_pair import PairWorker
 worker=PairWorker('candidates');worker.manual=True;worker.scheduled_release_at=release_time(worker.day)
 try:
  worker.run()
  worker.save('china_agent:morning_pair:'+str(worker.day)+':candidates',worker.audit)
  if worker.audit.get('status')not in('delivered','already_delivered'):raise RuntimeError('Scheduled price delivery incomplete')
 finally:
  import requests
  requests.sessions.Session.request=worker.original_http
if __name__=='__main__':main()
