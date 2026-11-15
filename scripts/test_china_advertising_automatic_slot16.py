"""The production daily entry point, offline cache/Telegram; no live transport."""
import base64,copy,importlib.util,io,os,socket,sys,types,unittest
from datetime import datetime
from contextlib import redirect_stdout
from unittest.mock import patch
from zoneinfo import ZoneInfo
from pathlib import Path
from test_china_advertising_v2 import Fake
from test_china_advertising_first_full_day_pipeline import fixture,metrics,Policy
from china_advertising_v2 import build,recommend,history
from china_advertising_economic_review import apply
from china_advertising_directions import attach
from china_morning_rules_review import review

class AutomaticSlot(unittest.TestCase):
 def ready(self):
  b,s,cp,ds,event,m=fixture()
  s.update(ids=[1],period_from='2026-11-09',period_to='2026-11-15',observed_at='2026-11-16T04:00:00Z',config=dict(minTopUp=10000))
  cp['timestamps']=dict(created='2026-10-01T00:00:00+03:00')
  s['catalogue']['rows'][0]['price']=100
  event['at']='2026-11-14T12:00:00+03:00'
  s['batches']['a']['budgets']=dict(adverts=[dict(advertId=1,total=500,currency='CNY')])
  for d in s['batches']['a']['stats'][0]['days']:
   day=d['date'][:10];d['date']=str(__import__('datetime').date.fromisoformat(day)+__import__('datetime').timedelta(days=1))
   d.update(d['apps'][0]['nms'][0])
  return review(Policy(),attach(apply(build(s,m),s,m),s),s)

 def entry(self,cache):
  # Replace construction only. The real entry point, renderer, plans, delivery and binder run.
  with patch.dict(sys.modules,{'china_advertising_state':types.SimpleNamespace(AdvertisingIO=lambda:cache)}):
   spec=importlib.util.spec_from_file_location('offline_scheduled_daily',Path(__file__).with_name('china_advertising_daily.py'))
   daily=importlib.util.module_from_spec(spec);spec.loader.exec_module(daily)
  return daily

 def test_prepare_0700_send_0730_backup_no_duplicates(self):
  cache=Fake();daily=self.entry(cache);bundle=self.ready();sent=[]
  class Clock(datetime):
   at=datetime(2026,11,16,7,0,tzinfo=ZoneInfo('Europe/Moscow'))
   @classmethod
   def now(cls,tz=None):return cls.at
  def sender(f):
   sent.append(f)
   return dict(chat=dict(id=-1004342917488),message_id=9000+len(sent))
  env=dict(GITHUB_REPOSITORY='Ekaterina11098/veschi-bot-runner',GITHUB_REF='refs/heads/main',CHINA_AD_PREPARE_ONLY='true',CHINA_AD_FROZEN_ONLY='false')
  with patch.dict(os.environ,env),patch.object(daily,'datetime',Clock),patch.object(daily,'telegram_sender',return_value=sender),patch('china_advertising_v2.prepare',return_value=bundle)as prepare,patch.object(socket.socket,'connect',side_effect=AssertionError('Network forbidden')),redirect_stdout(io.StringIO()):
   daily.run();self.assertEqual(sent,[])
   artifact=cache.get('china_agent:advertising_artifacts:2026-11-16:v2')
   self.assertEqual(artifact['bundle']['day'],'2026-11-16')
   self.assertEqual(artifact['bundle']['days'],['2026-11-13','2026-11-14','2026-11-15'])
   self.assertEqual({f['family']for f in artifact['files']},{'drr','budgets'})
   os.environ.update(CHINA_AD_PREPARE_ONLY='false',CHINA_AD_FROZEN_ONLY='true');Clock.at=Clock.at.replace(minute=30)
   daily.run();self.assertEqual(len(sent),2);self.assertEqual(prepare.call_count,1)
   receipt=cache.get('china_agent:advertising_delivery:2026-11-16:v1')
   self.assertEqual(receipt['status'],'delivered')
   self.assertTrue(all(p['status']=='sent'and p['message_id']for p in receipt['parts']))
   action_page=next(f for f in sent if f['family']=='drr')
   plan=cache.get('china_agent:loss_plan:v1:'+action_page['plan_id'])
   self.assertEqual(plan['items'][0]['target_minor'],28)
   Clock.at=Clock.at.replace(minute=45);daily.run();self.assertEqual(len(sent),2)
   self.assertEqual(prepare.call_count,1)

 def test_missing_preparation_cannot_send_or_collect_in_delivery_stage(self):
  cache=Fake();daily=self.entry(cache)
  class Clock(datetime):
   @classmethod
   def now(cls,tz=None):return datetime(2026,11,16,7,30,tzinfo=ZoneInfo('Europe/Moscow'))
  with patch.dict(os.environ,dict(GITHUB_REPOSITORY='Ekaterina11098/veschi-bot-runner',GITHUB_REF='refs/heads/main',CHINA_AD_PREPARE_ONLY='false',CHINA_AD_FROZEN_ONLY='true')),patch.object(daily,'datetime',Clock),patch('china_advertising_v2.prepare')as prepare,patch.object(daily,'telegram_sender')as sender:
   with self.assertRaisesRegex(ValueError,'preparation missing'):daily.run()
   prepare.assert_not_called();sender.assert_not_called()

if __name__=='__main__':unittest.main()
