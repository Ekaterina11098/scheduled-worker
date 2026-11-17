"""Resolve owner-named NEW WB Guangzhou warehouse; reads only."""
import os,json,time
from datetime import datetime,timezone
from urllib.parse import urlparse
import requests
from china_cloud_cost_control import Cache,WB,validate_identity
ROOT='china_agent:owner_risk_review:2026-11-17:v1'
def stamp():return datetime.now(timezone.utc).isoformat()
def main():
 c=Cache();scope=c.get(ROOT+':scope');assert scope['owner_id']==5122667182 and scope['wb_writes']==0
 assert c.create(ROOT+':new_warehouse_claim',dict(at=stamp(),status='reading')),'Already claimed; inspect exact result'
 f=c.get(ROOT+':fresh');cards=f['gua_cards']['rows'];mapping={str(s['chrtID']):r['nmID']for r in cards for s in r['sizes']}
 original=requests.sessions.Session.request
 def guard(session,method,url,*a,**kw):
  u=urlparse(url);m=method.upper()
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=u.path.startswith('/rest/v1/')and m in('GET','POST','PATCH')
  elif u.hostname=='marketplace-api.wildberries.ru':ok=m=='GET'and u.path=='/api/v3/warehouses'or m=='POST'and u.path.startswith('/api/v3/stocks/')and set(kw.get('json',{}))=={'chrtIds'}
  else:ok=False
  assert ok,'Not a scoped warehouse read'
  return original(session,method,url,*a,**kw)
 validate_identity(c,WB());requests.sessions.Session.request=guard
 out=dict(status='reading',wb_writes=0,telegram_calls=0,model_calls=0,owner_named_warehouse='Гуанджоу новый',observed_at=stamp(),grants_action_permission=False)
 try:
  def req(path,method='GET',body=None):
   r=requests.request(method,'https://marketplace-api.wildberries.ru'+path,headers={'Authorization':os.environ['WB_TOKEN_3']},json=body,timeout=(10,50));r.raise_for_status();return r.json()
  wh=req('/api/v3/warehouses');assert isinstance(wh,list)and len(wh)<=15
  out['warehouses']=wh
  matches=[w for w in wh if str(w.get('name','')).casefold().strip()=='гуанджоу новый']
  assert len(matches)==1,'Owner-named warehouse ambiguous; preserve inventory and inspect list'
  w=matches[0];assert type(w['id'])is int and not w.get('isDeleting',False)
  out['selected']=w
  raw=req('/api/v3/stocks/'+str(w['id']),'POST',dict(chrtIds=[int(k)for k in mapping]))
  out['published']=dict(warehouse_id=w['id'],warehouse_name=w['name'],observed_at=stamp(),size_to_nm=mapping,raw=raw)
  assert len(raw.get('stocks',[]))==len(mapping),'Incomplete new warehouse size coverage'
  out.update(status='complete',completed_at=stamp())
 finally:
  c.put(ROOT+':new_warehouse',json.loads(json.dumps(out)))
  requests.sessions.Session.request=original
 print(json.dumps(dict(status=out['status'],warehouse_id=out.get('selected',{}).get('id'),stocks=len(out.get('published',{}).get('raw',{}).get('stocks',[])),wb_writes=0)))
if __name__=='__main__':main()

