"""Read-only final combined audit of all17 confirmed actions and41332083cash."""
import json,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_advertising_v2 import http,save
ROOT='china_agent:owner_final_audit330:2026-11-15:v1'
def main():
 io=AdvertisingIO()
 if io.get(ROOT):return
 old=requests.sessions.Session.request
 def guard(session,method,url,**kw):
  u=urlparse(url);m=method.upper()
  if u.hostname=='advert-api.wildberries.ru':assert(m=='GET'and u.path=='/api/advert/v2/adverts')or(m=='POST'and u.path=='/api/advert/v2/budget')
  elif not url.startswith(io.url+'/rest/v1/'):raise ValueError('No mutations, models or Telegram')
  return old(session,method,url,**kw)
 requests.sessions.Session.request=guard
 key='china_agent:loss_plan:v1:daily-2026-11-15-cost-complete15-drr-0-buttons-e38293cf83ea7ed31890fba3-307200273'
 p=io.get(key);assert len(p['items'])==17
 ids=sorted({r['campaign_id']for r in p['items']})
 cs=http(io,'/api/advert/v2/adverts?ids='+','.join(map(str,ids)))['adverts'];by={c['id']:c for c in cs};assert set(by)==set(ids)
 budget=http(io,'/api/advert/v2/budget','POST',dict(advertIds=[41332083]))
 rows=[]
 for r in p['items']:
  cp=by[r['campaign_id']];n=next((n for n in cp['nm_settings']if n['nm_id']==r['nm_id']),None)
  okay=n is None if r['kind']=='ad_exclude_sku'else n is not None and n['bids_kopecks'][r['placement']]==r['target_minor']
  rows.append(dict(id=r['id'],kind=r['kind'],matches=okay,actual=n,expected=r.get('target_minor')))
 v=dict(status='complete',observed_at=datetime.now(timezone.utc).isoformat(),campaigns=by,budgets=budget,items=rows,wb_writes=0,telegram_calls=0,model_calls=0,grants_action_permission=False)
 save(io,ROOT,v);print(json.dumps(dict(matches=sum(r['matches']for r in rows),mismatches=[r['id']for r in rows if not r['matches']],budgets=budget)))
if __name__=='__main__':main()
