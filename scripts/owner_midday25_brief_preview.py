"""Re-render the verified saved preview in the owner-approved brief format."""
import copy,json,base64,hashlib,requests
from urllib.parse import urlparse
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner_midday_brief:2026-11-25:v1'
def main():
 io=AdvertisingIO()
 if io.get(ROOT):print('Verified brief preview exists, no repeat');return
 original=requests.sessions.Session.request
 def guard(s,method,url,*a,**kw):
  u=urlparse(url);assert u.hostname==urlparse(io.url).hostname and u.path.startswith('/rest/v1/')and method.upper()in('GET','POST','PATCH'),'Saved-only format correction';return original(s,method,url,*a,**kw)
 requests.sessions.Session.request=guard
 try:
  saved=io.get('china_agent:owner_midday_fix:2026-11-25:v2:preview');assert saved['status']=='verified';bundle=copy.deepcopy(saved['bundle'])
  from china_advertising_midday import render_midday,recommendations
  from china_archived_report_window import midday_view
  for c in midday_view(bundle)['campaigns']:
   if not c.get('attention'):assert recommendations(c)==(['Ничего не менять.']if c.get('owner_unchanged')else['Без изменений.'])
  files=render_midday(bundle);assert sum(len(f['actions'])for f in files)==len(saved['actions'])
  out=dict(status='verified',created_at=datetime.now(timezone.utc).isoformat(),source_key='china_agent:owner_midday_fix:2026-11-25:v2:preview',bundle=bundle,actions=saved['actions'],files=[dict(bytes_base64=base64.b64encode(f['bytes']).decode(),sha256=hashlib.sha256(f['bytes']).hexdigest(),page=f['page'])for f in files],wb_reads=0,wb_writes=0,telegram_calls=0,model_calls=0,format='concrete_SKU_actions_or_no_changes')
  assert io.create(ROOT,out);print(json.dumps(dict(status='verified',pages=len(files),actions=len(saved['actions']),wb_reads=0,wb_writes=0,telegram_calls=0)))
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()
