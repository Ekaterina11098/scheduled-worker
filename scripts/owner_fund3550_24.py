import os,json,time,copy,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner_fund3550_24:2026-11-24:v1'
PLAN={40945478:100,41270309:1250,41332083:450,42088552:1750}
STANDARD=['china_agent:daily_ad_execution:v2:daily-2026-11-24-budgets-1-buttons-1ba8cc8cb9fd8d5866239eea-5122667182','china_agent:daily_ad_execution:v2:daily-2026-11-24-drr-0-buttons-a45a5e28d2f801981c104bbd-5122667182']
def stamp():return datetime.now(timezone.utc).isoformat()
def norm(c):
 d={k:copy.deepcopy(c[k])for k in('id','status','currency','settings','bid_type','nm_settings')};d['nm_settings']=sorted(d['nm_settings'],key=lambda n:n['nm_id']);return d
def main():
 io=AdvertisingIO();a=io.get(ROOT+':approval')
 assert a['status']=='approved'and {x['cid']:x['amount_cny']for x in a['items']}==PLAN and a['amount_cny']==3550
 assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
 existing=io.get(ROOT+':execution')
 if existing:print(json.dumps({'status':existing['status'],'note':'Journal exists; never replay'}));return
 e=dict(status='preflight',started_at=stamp(),items=[],wb_writes=0,telegram_calls=0,model_calls=0)
 assert io.create(ROOT+':execution',e),'Concurrent execution'
 def save():io.put(ROOT+':execution',e)
 orig=requests.sessions.Session.request;allowed=None
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();path=u.path+('?' +u.query if u.query else '')
  dbhost=urlparse(os.environ['SUPABASE_URL']).hostname
  ok=(u.hostname==dbhost and m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/'))or(u.hostname=='advert-api.wildberries.ru'and((m=='GET'and u.path in('/api/advert/v2/adverts','/adv/v1/balance','/api/advert/v1/config'))or(m=='POST'and u.path=='/api/advert/v2/budget'and set((kw.get('json')or{}).get('advertIds',[]))<=set(PLAN))or allowed==(m,path,kw.get('json'))))
  assert ok,'Outside cash-only scope';return orig(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def req(path,method='GET',body=None):
  time.sleep(1.5);r=requests.request(method,'https://advert-api.wildberries.ru'+path,json=body,headers={'Authorization':io.token,'Cache-Control':'no-cache,no-store'},timeout=(10,55));r.raise_for_status();return r.json()if r.content else{}
 def campaigns(ids):return {c['id']:c for c in req('/api/advert/v2/adverts?ids='+','.join(map(str,ids))+'&owner_cash='+str(time.time_ns()))['adverts']}
 def budget(cid):
  rows=req('/api/advert/v2/budget','POST',{'advertIds':[cid]})['adverts'];assert len(rows)==1 and rows[0]['advertId']==cid and rows[0]['currency']=='CNY';return rows[0]['total']
 def standard_done():assert all((io.get(k)or{}).get('status')=='done'for k in STANDARD),'Standard package active; stop'
 try:
  standard_done();before=campaigns(PLAN);assert set(before)==set(PLAN)
  cfg=req('/api/advert/v1/config');assert cfg['currency']=='CNY'and cfg['minTopUp']<=10000
  cash=req('/adv/v1/balance');assert cash['currency']=='CNY'
  typ=0 if cash.get('balance',0)>=3550 else 1 if cash.get('net',0)>=3550 else None;assert typ is not None,'Insufficient account balance'
  for item in a['items']:
   cid=item['cid'];c=before[cid];assert c['status']==9 and c['currency']=='CNY'
   bal=budget(cid);assert bal<=item['review_balance']+1,'New funding since proposal; do not duplicate'
   e['items'].append(dict(id='fund:'+str(cid),cid=cid,status='preflight',amount_cny=PLAN[cid],before=c,before_budget=bal,steps={}))
  save()
  for x in e['items']:
   cid=x['cid'];standard_done();c=campaigns([cid])[cid];assert norm(c)==norm(x['before']),'Campaign changed; stop'
   bal=budget(cid);assert bal<=x['before_budget']+1,'Concurrent funding detected'
   path='/adv/v1/budget/deposit?id='+str(cid);body={'sum':PLAN[cid],'type':typ}
   op=dict(status='submitting',submitted_at=stamp(),method='POST',path=path,body=body)
   x['status']='submitting';x['steps']['deposit']=op;save();allowed=('POST',path,body)
   try:op['response']=req(path,'POST',body)
   finally:allowed=None
   e['wb_writes']+=1;op['status']='accepted';save()
   after_balance=budget(cid);after=campaigns([cid])[cid]
   assert after_balance>=bal+PLAN[cid]-max(2,PLAN[cid]*.005),'Deposit uncertain; never replay'
   assert norm(after)==norm(x['before']),'Whole campaign changed; no further funding'
   op.update(status='verified',verified_at=stamp(),before_budget=bal,after_budget=after_balance)
   x.update(status='verified',after=after,after_budget=after_balance,verified_at=stamp());save()
   assert io.create(ROOT+':funding:'+str(cid),x)
  e.update(status='verified',completed_at=stamp(),verified_at=stamp(),total_cny=sum(x['amount_cny']for x in e['items']));save()
 except Exception as ex:
  e.update(status='uncertain'if any(x.get('status')=='submitting'for x in e['items'])else'partial'if e['wb_writes']else'blocked',error=type(ex).__name__+': '+str(ex)[:300]);save();raise
 print(json.dumps({'status':e['status'],'total_cny':e['total_cny'],'wb_writes':e['wb_writes'],'items':[dict(cid=x['cid'],amount=x['amount_cny'],balance=x['after_budget'],status=x['status'])for x in e['items']]}))
if __name__=='__main__':main()
