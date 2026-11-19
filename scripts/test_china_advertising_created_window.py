"""Regression: a campaign created today cannot break yesterday's completed report."""
import ast,copy,types,sys,unittest
from pathlib import Path
from datetime import date,datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from unittest.mock import patch

class CreatedWindowTests(unittest.TestCase):
 def run_case(self,created):
  tree=ast.parse(Path(__file__).with_name('china_advertising_v2.py').read_text(encoding='utf-8'))
  nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in('collect','event_time','save')]
  state={'status':'complete','period_from':'2026-11-12','period_to':'2026-11-18','batches':{'0':{'stats':[],'campaigns':{'adverts':[dict(id=123,status=9,timestamps={}if created is None else dict(created=created))]}}}}
  key='china_agent:advertising_source:2026-11-19:v2';data={key:state,'format':{'status':'approved','version':'v'}};calls=[]
  class IO:
   def get(self,k):return copy.deepcopy(data.get(k))
   def put(self,k,v):data[k]=copy.deepcopy(v)
   def create(self,k,v):data[k]=copy.deepcopy(v);return True
  def http(io,path):calls.append(path);return []
  readiness=types.ModuleType('china_morning_readiness');readiness.ensure=lambda *a:None
  ns=dict(copy=copy,time=types.SimpleNamespace(sleep=lambda n:None),date=date,datetime=datetime,timedelta=timedelta,timezone=timezone,MSK=ZoneInfo('Europe/Moscow'),FORMAT='format',VERSION='v',http=http,stamp=lambda:'fixture',collect_alternative_zero_statistics=lambda *a:{})
  exec(compile(ast.Module(body=nodes,type_ignores=[]),'production-collect','exec'),ns)
  with patch.dict(sys.modules,{'china_morning_readiness':readiness}):result=ns['collect'](IO(),'2026-11-19')
  return result,calls
 def test_new_campaign_is_retained_without_invalid_request_or_fake_zero(self):
  result,calls=self.run_case('2026-11-19T00:09:54+03:00')
  self.assertEqual(calls,[]);self.assertEqual(result['batches']['0']['stats'],[])
  self.assertEqual(result['batches']['0']['campaigns']['adverts'][0]['id'],123)
  self.assertEqual(result['campaign_statistics_scope']['123']['status'],'not_in_period')
 def test_utc_creation_is_evaluated_in_moscow(self):
  result,calls=self.run_case('2026-11-18T22:09:54Z')
  self.assertEqual(calls,[]);self.assertEqual(result['campaign_statistics_scope']['123']['created_day_msk'],'2026-11-19')
 def test_old_missing_campaign_still_requires_collection(self):
  result,calls=self.run_case('2026-11-17T15:00:00+03:00')
  self.assertEqual(len(calls),1);self.assertIn('beginDate=2026-11-17&endDate=2026-11-18',calls[0]);self.assertNotIn('campaign_statistics_scope',result)
 def test_unknown_creation_is_not_skipped(self):
  result,calls=self.run_case(None)
  self.assertEqual(len(calls),1);self.assertIn('beginDate=2026-11-12&endDate=2026-11-18',calls[0])
if __name__=='__main__':unittest.main()

