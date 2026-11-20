
"""Private owner review: read current evidence, never send Telegram or write WB."""
import os,json,copy,base64,hashlib
from datetime import datetime,timezone
from urllib.parse import urlparse
import requests
from china_advertising_state import AdvertisingIO
from china_advertising_v2 import http,prepare,save
from china_advertising_v2_png import render
from china_report_cash_refresh import refresh
from china_moysklad_read import read_stock
from china_morning_readiness import current_prices,published_stock
DAY='2026-11-20'
KEY='china_agent:advertising_artifacts:'+DAY+':owner-review-v1'
io=AdvertisingIO()
assert not io.get(KEY),'Existing preview preserved'
original=requests.sessions.Session.request
def guard(session,method,url,*args,**kw):
 u=urlparse(url);m=method.upper()
 if u.hostname=='api.telegram.org' or 'openai'in(u.hostname or''):raise ValueError('No Telegram or model in owner preview')
 if (u.hostname or'').endswith('wildberries.ru'):
  allowed=(m=='GET'and u.path in('/adv/v1/promotion/count','/api/advert/v2/adverts','/api/advert/v1/config','/adv/v3/fullstats','/api/v2/list/goods/filter'))or(m=='POST'and u.path in('/api/advert/v2/budget','/api/advert/v1/bids/min','/api/v3/stocks/2126188'))
  assert allowed,'WB mutation forbidden in preview'
 if (u.hostname or'').endswith('moysklad.ru'):assert m=='GET','No stock mutations'
 return original(session,method,url,*args,**kw)
requests.sessions.Session.request=guard
s=io.get('china_agent:advertising_source:'+DAY+':v2')
assert s['status']=='complete'and s['day_quality']['usable']
s=refresh(io,s,http)
states={c['id']:c for b in s['batches'].values()for c in b['campaigns']['adverts']}
wanted=sorted({n['nm_id']for cid in(41967612,41296359)for n in states[cid]['nm_settings']})
data=io.get('china_agent:advertising_full_growth:'+DAY+':v1:inputs')
scope=data.get('owner_exact_scope_refresh')or{}
assert scope.get('campaign_ids')==[41967612,41296359]
assert (datetime.now(timezone.utc)-datetime.fromisoformat(scope['observed_at'])).total_seconds()<3600
assert {r['nm_id']for r in scope['prices']['rows']}==set(wanted),'Composition changed since exact-scope check'
# A scoped refresh does not refresh the unqueried remainder of the catalogue.
original=io.get('china_agent:advertising_artifacts:'+DAY+':v2')
prior={str(m['nm']):m['economics']for c in original['bundle']['campaigns']for m in c.get('budget_members',[])if m.get('economics')}
reference=next(e for nm,e in prior.items()if int(nm)not in wanted and e.get('price_observed_at'))
for name,field in [('prices','price_observed_at'),('stock','stock_observed_at'),('published_stock','published_stock_observed_at')]:
 data[name]['observed_at']=reference[field]
for nm,e in data['economics']['rows'].items():
 if int(nm)in wanted:continue
 old=prior.get(nm,reference)
 for field in ('price_observed_at','stock_observed_at','published_stock_observed_at'):
  if field in old:e[field]=old[field]
io.put('china_agent:advertising_full_growth:'+DAY+':v1:inputs',data)
s['economics']=data['economics']
save(io,'china_agent:advertising_source:'+DAY+':v2',s)
bundle=prepare(io,DAY)
files=render(bundle)
value=dict(day=DAY,status='owner_review_only_not_sent',bundle=bundle,files=[{k:v for k,v in f.items()if k!='bytes'}|dict(b64=base64.b64encode(f['bytes']).decode(),png_sha256=hashlib.sha256(f['bytes']).hexdigest())for f in files],wb_writes=0,telegram_calls=0,model_calls=0,prepared_at=datetime.now(timezone.utc).isoformat())
assert io.create(KEY,value)
summary=dict(status=value['status'],source_key=KEY,campaigns=[dict(campaign_id=c['id'],balance=c.get('balance'),reserve=c.get('budget_reference_need'),gap=c.get('budget_cash_gap'),amount=(c.get('budget_action')or{}).get('amount_cny'),note=c.get('budget_short_note'),economy=(c.get('campaign_budget_economics')or{}).get('status'))for c in bundle['campaigns']if c['status']in(9,11)],wb_writes=0,telegram_calls=0,model_calls=0)
assert io.create('china_agent:owner_report20_review:v1:summary',summary)
print(json.dumps(dict(status=value['status'],files=len(files),wb_writes=0,telegram_calls=0,model_calls=0)))
