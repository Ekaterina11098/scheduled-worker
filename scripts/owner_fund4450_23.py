import os,json,time,copy,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner_fund4450:2026-11-23:v1'
PLAN=[(42088552,1300,21),(41270309,800,50),(40933588,1100,1871),(41298169,450,446),(41055480,200,102),(41332083,200,146),(41325622,100,85),(41967612,100,103),(41155909,100,151),(42068265,100,75)]
def now():return datetime.now(timezone.utc).isoformat()
def norm(c):
 d={k:copy.deepcopy(c[k])for k in ('id','status','currency','settings','bid_type','nm_settings')};d['nm_settings']=sorted(d['nm_settings'],key=lambda n:n['nm_id']);return d
def main():
 io=AdvertisingIO();a=io.get(ROOT+':approval');assert a and a['status']=='approved' and a['total_cny']==4450 and a['plan']==[list(x)for x in PLAN]
 assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
 e=io.get(ROOT+':execution')
 if e:print(json.dumps({'status':e['status'],'note':'Existing journal; no replay'}));return
 e=dict(status='preflight',started_at=now(),items={},wb_writes=0,telegram_calls=0,model_calls=0,approval_key=ROOT+':approval');assert io.create(ROOT+':execution',e)
 def save():io.put(ROOT+':execution',e)
 original=requests.sessions.Session.request;allowed=None
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();path=u.path+('?' + u.query if u.query else '')
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=m in ('GET','POST','PATCH') and u.path.startswith('/rest/v1/')
  elif u.hostname=='advert-api.wildberries.ru':ok=(m=='GET' and u.path in ('/api/advert/v2/adverts','/adv/v1/balance','/api/advert/v1/config'))or(m=='POST' and u.path=='/api/advert/v2/budget')or allowed==(m,path,kw.get('json'))
  else:ok=False
  assert ok,'Outside cash-only scope';return original(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def req(path,method='GET',body=None):
  time.sleep(1.2);r=requests.request(method,'https://advert-api.wildberries.ru'+path,json=body,headers={'Authorization':io.token,'Cache-Control':'no-cache,no-store'},timeout=(10,55));r.raise_for_status();return r.json()if r.content else{}
 def camp(cid):return req('/api/advert/v2/adverts?ids='+str(cid)+'&owner_read='+str(time.time_ns()))['adverts'][0]
 def budget(cid):
  x=req('/api/advert/v2/budget','POST',{'advertIds':[cid]})['adverts'];assert len(x)==1 and x[0]['advertId']==cid and x[0]['currency']=='CNY';return x[0]['total']
 cfg=req('/api/advert/v1/config');assert cfg['currency']=='CNY' and cfg['minTopUp']<=10000
 cash=req('/adv/v1/balance');assert cash['currency']=='CNY';assert max(cash.get('balance',0),cash.get('net',0))>=4450,'Insufficient single-source cash for package';e['cash_before']=cash;save()
 for cid,amount,proposal_balance in PLAN:
  s={'cid':cid,'amount_cny':amount,'status':'preflight'};e['items'][str(cid)]=s;save()
  try:
   before=camp(cid);assert before['id']==cid and before['status']==9 and before['currency']=='CNY','Target not active';bal=budget(cid);s.update(before=before,before_budget=bal);save()
   assert bal<=proposal_balance+2,'New funding since proposal; do not repeat'
   cash=req('/adv/v1/balance');typ=0 if cash.get('balance',0)>=amount else 1 if cash.get('net',0)>=amount else None;assert typ is not None
   path='/adv/v1/budget/deposit?id='+str(cid);body={'sum':amount,'type':typ};s.update(status='submitting',submitted_at=now(),request=body);save();allowed=('POST',path,body)
   try:s['response']=req(path,'POST',body)
   finally:allowed=None
   e['wb_writes']+=1;s['status']='accepted';save()
   after=camp(cid);afterbal=budget(cid);again=camp(cid);assert norm(before)==norm(after)==norm(again),'Advertising fields changed';assert afterbal>=bal+amount-2,'Balance increase not confirmed'
   s.update(status='verified',after=after,after_budget=afterbal,verified_at=now());save();io.create(ROOT+':funding:'+str(cid),dict(s,id='fund:'+str(cid),steps={'deposit':{'status':'verified','submitted_at':s['submitted_at'],'body':body,'response':s['response']}}))
  except Exception as ex:
   s.update(status='uncertain'if s['status']in ('submitting','accepted')else'blocked',error=type(ex).__name__+': '+str(ex)[:300]);save()
 e['status']='verified'if all(x['status']=='verified'for x in e['items'].values())and len(e['items'])==10 else'partial_attention';e['completed_at']=now();e['verified_total_cny']=sum(x['amount_cny']for x in e['items'].values()if x['status']=='verified');save();print(json.dumps({'status':e['status'],'total':e['verified_total_cny'],'items':[{k:x.get(k)for k in ('cid','status','amount_cny','before_budget','after_budget','error')}for x in e['items'].values()]}))
if __name__=='__main__':main()