"""Owner requested both21Nov plans: real read preflight, memory-only simulated mutations."""
import copy,json,time,requests,hashlib
from urllib.parse import urlparse,parse_qs
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
from china_loss_control import PLAN,APPROVAL,digest
ROOT='china_agent:owner_reports21_preflight:v2'
def main():
 real=AdvertisingIO();memory={};campaigns={};budgets={};reads={};attempts=[]
 original=requests.sessions.Session.request;nap=time.sleep
 def response(data):
  r=requests.Response();r.status_code=200;r._content=json.dumps(data).encode();return r
 def request(session,method,url,*args,**kw):
  u=urlparse(url);host=u.hostname or '';path=u.path;method=method.upper();body=kw.get('json')or{}
  if 'telegram'in host or 'openai'in host:raise RuntimeError('Audit forbids external message/model')
  if host.endswith('wildberries.ru'):
   if host=='advert-api.wildberries.ru':
    if path=='/api/advert/v2/adverts':
     ids=[int(x)for x in parse_qs(u.query)['ids'][0].split(',')]
     if all(x in campaigns for x in ids):return response({'adverts':[copy.deepcopy(campaigns[x])for x in ids]})
    elif path=='/api/advert/v2/budget':
     ids=body['advertIds']
     if all(x in budgets for x in ids):return response({'adverts':[dict(advertId=x,total=budgets[x],currency='CNY')for x in ids]})
    elif path=='/adv/v0/auction/nms' and method=='PATCH':
     attempts.append(dict(method=method,path=path))
     for row in body['nms']:
      cp=campaigns[row['advert_id']];remove=set(row['nms']['delete']);cp['nm_settings']=[n for n in cp['nm_settings']if n['nm_id']not in remove]
      subject=copy.deepcopy(cp['nm_settings'][0]['subject'])
      for nm in row['nms']['add']:cp['nm_settings'].append(dict(nm_id=nm,subject=subject,bids_kopecks=dict(search=28 if cp['settings']['placements'].get('search')else 0,recommendations=28 if cp['settings']['placements'].get('recommendations')else 0)))
     return response({})
    elif path=='/api/advert/v1/bids' and method=='PATCH':
     attempts.append(dict(method=method,path=path))
     for row in body['bids']:
      for b in row['nm_bids']:
       next(n for n in campaigns[row['advert_id']]['nm_settings']if n['nm_id']==b['nm_id'])['bids_kopecks'][b['placement']]=b['bid_kopecks']
     return response({})
    elif path=='/adv/v1/budget/deposit'and method=='POST':
     attempts.append(dict(method=method,path=path));cid=int(parse_qs(u.query)['id'][0]);budgets[cid]+=body['sum'];return response({})
    elif path in('/adv/v0/pause','/adv/v0/stop','/adv/v0/start'):
     raise RuntimeError('Unexpected lifecycle action in audited plans')
    allowed=(method=='GET'and path in('/api/advert/v2/adverts','/api/advert/v1/config','/adv/v1/balance'))or(method=='POST'and path in('/api/advert/v2/budget','/api/advert/v1/bids/min'))
   else:allowed=(method=='GET'and path=='/api/v2/list/goods/filter')or(method=='POST'and path.startswith('/api/v3/stocks/'))
   if not allowed:raise RuntimeError('Audit blocked unexpected WB operation '+method+' '+path)
  elif host.endswith('moysklad.ru'):
   if method!='GET':raise RuntimeError('No stock writes')
  else:
   if method!='GET':raise RuntimeError('No persistent writes during simulated execution')
  key=method+url+json.dumps(kw.get('params'))+json.dumps(body,sort_keys=True)
  if key in reads:return response(reads[key])
  r=original(session,method,url,*args,**kw)
  if r.ok:
   data=r.json();reads[key]=data
   if host=='advert-api.wildberries.ru'and path=='/api/advert/v2/adverts':
    for c in data['adverts']:campaigns[c['id']]=copy.deepcopy(c)
   if host=='advert-api.wildberries.ru'and path=='/api/advert/v2/budget':
    for c in data['adverts']:budgets[c['advertId']]=c['total']
  return r
 class IO:
  token=real.token
  wb=real.wb
  daily_report_current_revalidation=True
  def get(self,key):
   if key not in memory:memory[key]=real.get(key)
   return copy.deepcopy(memory[key])
  def put(self,key,p):memory[key]=copy.deepcopy(p)
  def create(self,key,p):
   if self.get(key)is not None:return False
   self.put(key,p);return True
  def validate_owner(self,a):pass
 io=IO()
 import china_report_buttons as buttons,china_execution_notice as notices,china_confirmed_report_recovery as recovery,china_daily_ad_actions as daily
 buttons.execution_claim=lambda *a:None
 notices.deliver_result=lambda *a:None
 recovery.register_campaigns=lambda *a:None
 requests.sessions.Session.request=request;time.sleep=lambda n:None
 results=[]
 try:
  for family,mid in [('drr',1121),('budgets',1122)]:
   binding=io.get('china_agent:daily_ad_message:v2:'+str(mid));parent=io.get(PLAN+binding['plan_id'])
   assert binding['plan_sha256']==parent['plan_sha256']==digest(parent['items'])and mid in parent['report_message_ids']
   token=hashlib.sha256((parent['plan_id']+':'+parent['plan_sha256']+':'+family).encode()).hexdigest()[:24]+'-5122667182'
   pid=parent['plan_id']+'-buttons-'+token;p=copy.deepcopy(parent);p.update(plan_id=pid,parent_plan_id=parent['plan_id'],parent_plan_sha256=parent['plan_sha256'],selected_ids=[x['id']for x in parent['items']])
   job=990000+(family=='budgets');a=dict(sender_id=5122667182,job_id=job,status='approved',plan_id=pid,plan_sha256=p['plan_sha256'],created_at=datetime.now(timezone.utc).isoformat())
   io.put(PLAN+pid,p);io.put(APPROVAL+str(job),a)
   io.put('china_agent:report_buttons:v1:confirmation:'+token,dict(status='confirmed',sender_id=5122667182,plan_sha256=parent['plan_sha256'],selected_ids=p['selected_ids'],job_id=job))
   e=daily.execute(io,a,p)
   results.append(dict(family=family,message_id=mid,plan_sha256=parent['plan_sha256'],items=[{k:s.get(k)for k in('id','status','reason','already_done','funding_reconciliation')}for s in e['items']],package=e.get('package_readback')))
 finally:requests.sessions.Session.request=original;time.sleep=nap
 result=dict(status='complete',observed_at=datetime.now(timezone.utc).isoformat(),results=results,live_before_campaigns=list(campaigns),simulated_mutations=attempts,wb_writes=0,telegram_calls=0,model_calls=0,simulation_only=True)
 real.put(ROOT,result)if real.get(ROOT)else real.create(ROOT,result)
 print(json.dumps(result))
if __name__=='__main__':main()
