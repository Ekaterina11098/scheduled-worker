import os,json,time,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
import stock_supervision as s
import stock_schedule_watchdog as w
class SupervisionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.env=patch.dict(os.environ,{'SUPABASE_SECRET_KEY':'offline-test-key','STOCK_SUPERVISION_CACHE_DIR':self.tmp.name,'TELEGRAM_ALLOWED_CHAT_ID':'-1001','STOCK_REPORT_DESTINATION_VERIFIED':'true'})
  self.env.start();self.addCleanup(self.env.stop)
  s.save_cache({'destination':{'chat_id':'-1001','verified':True,'verified_at':time.time()}})
 def test_cache_is_encrypted_and_authenticated(self):
  raw=s.cache_path().read_text();self.assertNotIn('-1001',raw)
  self.assertEqual(s.load_cache()['destination']['chat_id'],'-1001')
  value=json.loads(raw);value['ciphertext']=value['ciphertext'][:-5]+'AAAAA';s.cache_path().write_text(json.dumps(value))
  with self.assertRaises(Exception):s.load_cache()
 def test_confirmed_notice_is_not_sent_twice(self):
  calls=[]
  def send(chat,text):calls.append((chat,text));return {'ok':True,'result':{'message_id':123}}
  self.assertEqual(s.notify('slot','startup','error',send)['state'],'confirmed')
  s.notify('slot','startup','error',send);self.assertEqual(len(calls),1)
 def test_unknown_send_result_never_blindly_retries(self):
  calls=[]
  def fail(*args):calls.append(1);raise OSError('unknown')
  with self.assertRaises(OSError):s.notify('slot','startup','error',fail)
  self.assertEqual(s.notify('slot','startup','error',fail)['state'],'uncertain');self.assertEqual(calls,[1])
 def test_wrong_destination_is_blocked_before_send(self):
  os.environ['TELEGRAM_ALLOWED_CHAT_ID']='12345'
  with self.assertRaises(RuntimeError):s.notify('slot','bad','error',lambda *a:self.fail('no send'))
 def test_explicit_disabled_live_destination_never_uses_cache(self):
  import psycopg
  class DB:
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def execute(self,*a):return self
   def fetchone(self):return ({'enabled':False,'destination_verified':True,'chat_id':'-1001'},)
  with patch.object(psycopg,'connect',return_value=DB()):
   with self.assertRaises(RuntimeError):s.resolve_destination()
 def test_verified_cache_allows_alert_during_database_outage(self):
  import psycopg
  with patch.object(psycopg,'connect',side_effect=psycopg.OperationalError('offline')):self.assertEqual(s.resolve_destination(),'-1001')
 def test_expired_cache_is_not_used(self):
  import psycopg
  s.save_cache({'destination':{'chat_id':'-1001','verified':True,'verified_at':time.time()-8*86400}})
  with patch.object(psycopg,'connect',side_effect=psycopg.OperationalError('offline')):
   with self.assertRaises(RuntimeError):s.resolve_destination()
 def test_watchdog_receipt_is_scope_bound_and_never_opens_database(self):
  import psycopg
  s.remember('technical:stock-daily:2026-11-28:0700',dict(status='complete',execution_complete=True,delivery_done=True))
  with patch.object(psycopg,'connect',side_effect=AssertionError('monitor must not consume writer connection')):
   self.assertTrue(w.read_status('technical:stock-daily:2026-11-28:0700')['delivery_done'])
   self.assertIsNone(w.read_status('technical:stock-daily:2026-11-27'))
class WatchdogTests(unittest.TestCase):
 def due(self):return s.latest_due(datetime(2026,11,28,2,20,tzinfo=timezone.utc))
 def test_missing_morning_selects_current_scope_and_dispatches(self):
  d=self.due();self.assertEqual(d['scope'],'technical:stock-daily:2026-11-28:0700');self.assertEqual(d['slot'],'0700')
  self.assertEqual(w.evaluate(d,None,[],d['opened_at']+1200)['reason'],'missing_start')
 def test_evening_and_overnight_keep_same_evening_scope(self):
  for value in ('2026-11-28T17:20:00+00:00','2026-11-29T00:20:00+00:00'):
   self.assertEqual(s.latest_due(datetime.fromisoformat(value))['scope'],'technical:stock-daily:2026-11-28')
 def test_grace_does_not_prematurely_alert(self):
  d=self.due();self.assertEqual(w.evaluate(d,None,[],d['opened_at']+100)['action'],'wait')
 def test_complete_with_confirmed_delivery_has_no_dispatch(self):
  d=self.due();st=dict(scope=d['scope'],execution_complete=True,delivery_done=True)
  self.assertEqual(w.evaluate(d,st,[],d['opened_at']+1200)['action'],'healthy')
 def test_github_success_without_business_completion_is_not_success(self):
  d=self.due();r=[dict(created_at='2026-11-28T02:00:00Z',status='completed',conclusion='success')]
  self.assertEqual(w.evaluate(d,None,r,d['opened_at']+1200)['action'],'dispatch')
 def test_active_worker_is_not_duplicated(self):
  d=self.due();r=[dict(created_at='2026-11-28T02:00:00Z',status='in_progress')]
  self.assertEqual(w.evaluate(d,None,r,d['opened_at']+1200)['action'],'running')
 def test_provider_retry_after_is_preserved(self):
  d=self.due();st=dict(scope=d['scope'],retry_not_before=d['opened_at']+3600)
  self.assertEqual(w.evaluate(d,st,[],d['opened_at']+1200)['reason'],'provider_cooldown')
 def test_recent_attempt_is_not_repeated_immediately(self):
  d=self.due();r=[dict(created_at='2026-11-28T02:18:00Z',status='completed')]
  self.assertEqual(w.evaluate(d,None,r,d['opened_at']+1200)['reason'],'bounded_retry_interval')
class EntryTests(unittest.TestCase):
 def test_prejournal_exception_triggers_startup_notice(self):
  import stock_supervised_entry as e
  def failed():raise TimeoutError('startup')
  with patch.object(e,'resolve_destination'),patch.object(e,'remember'),patch.object(e,'notify',return_value={'state':'confirmed'}) as send,patch.object(e.runpy,'run_path',return_value={'main':failed}):
   with self.assertRaises(TimeoutError):e.main('/tmp/stock_job.py')
   self.assertIn('startup:TimeoutError',send.call_args.args)
 def test_completed_stock_waiting_for_manual_notice_is_not_reported_failed_stock(self):
  import stock_supervised_entry as e
  with patch.object(e,'resolve_destination'),patch.object(e,'remember'),patch.object(e,'notify',return_value={'state':'confirmed'}) as send,patch.object(e.runpy,'run_path',return_value={'main':lambda:dict(status='waiting',execution_complete=True)}):
   e.main('/tmp/stock_job.py')
   self.assertIn('обновлены',send.call_args.args[2]);self.assertNotIn('не завершено',send.call_args.args[2])
if __name__=='__main__':unittest.main()
