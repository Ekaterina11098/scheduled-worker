"""One-off saved-data verification of the IP rules backend. No collector or sender."""
import json,os,copy
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import ip_report_freeze as freeze
from ip_report_analysis import ROOT_RULES
original=freeze.store
day=str(datetime.now(timezone.utc).astimezone(ZoneInfo('Europe/Moscow')).date())
class SavedOnly:
 def __init__(self):self.memory={}
 def cache_get(self,key):
  if key in self.memory:return copy.deepcopy(self.memory[key])
  if key=='advertising:ip:morning_recovery:'+day+':v1':
   return original.cache_get('advertising:ip:scheduled_source:v1:'+day+':'+os.environ['IP_REPORT_SLOT'])
  return original.cache_get(key)
 def cache_set(self,key,value,**kwargs):
  if key.startswith('advertising:ip:daily-review-audit:v1:'):
   self.memory[key]=copy.deepcopy(value);return
  if not(key.startswith(ROOT_RULES)or(key.startswith('advertising:ip:report-analysis:v1:')and key.endswith(':preview'))):
   raise AssertionError('Unexpected verification write')
  return original.cache_set(key,value,**kwargs)
 def registration(self):return original.registration()
 def db(self,method,*args,**kwargs):
  if method!='GET':raise AssertionError('Verification reads sources only')
  return original.db(method,*args,**kwargs)
freeze.store=SavedOnly()
os.environ['IP_REPORT_VERIFY_ONLY']='true'
assert not os.environ.get('OPENAI_API_KEY')
for slot in('morning','midday'):
 os.environ['IP_REPORT_SLOT']=slot
 try:result=freeze.main()
 except Exception as exc:
  import traceback
  original.cache_set(ROOT_RULES+'verification-error',dict(slot=slot,error_type=type(exc).__name__,trace=traceback.format_exc()),ttl_days=7)
  raise RuntimeError('Private saved-data verification error')from None
 assert result['status']=='verified_saved_only'
 assert all(result[k]==0 for k in('model_calls','charged_micro_usd','source_calls','wb_writes','telegram_calls'))
 saved=original.cache_get('advertising:ip:report-analysis:v1:'+result['period']+':preview')
 review=saved['contract']['rules_analysis']
 assert review['backend']=='rules_no_model'and review['model']is None
 assert original.cache_get(ROOT_RULES+result['period'])['analysis']==review
 assert saved['images']and all(i.get('sha256')for i in saved['images'])
 print(json.dumps(dict(slot=slot,status=result['status'],backend=review['backend'],period=result['period'],
  images=len(result['images']),actions=len(result['actions']),model_calls=0,charged_micro_usd=0,
  source_calls=0,wb_writes=0,telegram_calls=0,private_readback=True)))
