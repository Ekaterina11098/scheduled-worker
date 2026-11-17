"""Owner-requested pre-staged10:30 delivery using the ordinary report identity and bindings."""
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
import time
def main():
 from china_price_state_transport import install
 install()
 from china_agent.morning_pair import PairWorker
 class TimedPair(PairWorker):
  def prepare(self,preview=False):
   from china_price_current_check import check
   saved=self.get('china_agent:morning_pair:2026-11-17:candidates:verify')or{}
   assert self.day.isoformat()=='2026-11-17'and saved.get('status')=='preview_verified'
   self.price_control_review=self.get('china_agent:daily_expected_candidates:2026-11-17:verify')
   assert self.price_control_review['status']=='complete_disclosed_forecast_model'
   answer=check(self,saved['preview'])
   assert answer==saved['preview'],'Current availability or price changed since owner review'
   self.audit['owner_preview_match']=True
   return answer,[dict(name='china_price_daily_report',report_date=str(self.day),period_from='2026-11-13',period_to='2026-11-16',source_snapshot_id=saved['source_snapshot_id'],status='complete_orders',ready_rises=1,execution_authorized=False)]
  def guard(self,session,method,url,*a,**kw):
   u=urlparse(url)
   if u.hostname=='api.telegram.org'and u.path.rsplit('/',1)[-1].startswith(('send','edit')):
    target=datetime(2026,11,17,10,30,tzinfo=ZoneInfo('Europe/Moscow'))
    assert self.day.isoformat()=='2026-11-17'
    if not getattr(self,'timing_saved',False):
     self.save('china_agent:owner_price1030:2026-11-17:v1',dict(status='prepared_waiting_time',job_id=self.job['id'],target_at=target.isoformat(),prepared_at=datetime.now(timezone.utc).isoformat(),owner_preview_match=self.audit.get('owner_preview_match'),wb_writes=0,model_calls=0))
     self.timing_saved=True
    while datetime.now(timezone.utc)<target:
     time.sleep(min(1,max(.01,(target-datetime.now(timezone.utc)).total_seconds())))
    self.audit['delivery_attempt_at']=datetime.now(timezone.utc).isoformat()
   return super().guard(session,method,url,*a,**kw)
 w=TimedPair('candidates');w.manual=True
 try:
  w.run()
  w.save('china_agent:owner_price1030:2026-11-17:v1',dict(w.audit,target_at='2026-11-17T10:30:00+03:00',model_calls=0))
  assert w.audit['status']in('delivered','already_delivered')
 finally:
  import requests
  requests.sessions.Session.request=w.original_http
if __name__=='__main__':main()
