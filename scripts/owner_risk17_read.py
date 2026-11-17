"""Bounded owner-requested missing evidence only. No marketplace mutations/TG/model."""
import os,json,time
from datetime import datetime,timezone
from urllib.parse import urlparse
import requests
from china_cloud_cost_control import Cache,WB,validate_identity
from china_moysklad_read import read_stock
ROOT='china_agent:owner_risk_review:2026-11-17:v1'
def now():return datetime.now(timezone.utc).isoformat()
def main():
 c=Cache();scope=c.get(ROOT+':scope')or{}
 assert scope.get('owner_id')==5122667182 and scope.get('wb_writes')==0 and scope.get('status')=='authorized_read_only'
 if not c.create(ROOT+':read_claim',dict(status='collecting',at=now())):raise ValueError('Read already claimed; inspect checkpoints, no blind replay')
 v=dict(status='collecting',observed_at=now(),errors={},wb_writes=0,telegram_calls=0,model_calls=0,grants_action_permission=False)
 def save():c.put(ROOT+':fresh',json.loads(json.dumps(v)))
 def stage(k,fn):
  try:v[k]=fn()
  except Exception as e:v['errors'][k]=type(e).__name__+': '+str(e)[:220]
  save()
 original=requests.sessions.Session.request
 def guard(session,method,url,*a,**kw):
  u=urlparse(url);p=u.path;m=method.upper();body=kw.get('json')or{}
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=p.startswith('/rest/v1/')and m in('GET','POST','PATCH')
  elif u.hostname=='advert-api.wildberries.ru':ok=(m=='GET'and p in('/api/advert/v2/adverts','/adv/v1/budget'))or(m=='POST'and p=='/api/advert/v1/bids/min')
  elif u.hostname=='api.moysklad.ru':ok=m=='GET'and p.startswith('/api/remap/1.2/')
  elif u.hostname=='content-api.wildberries.ru':ok=m=='POST'and p=='/content/v2/get/cards/list'
  elif u.hostname=='marketplace-api.wildberries.ru':ok=m=='POST'and p in('/api/v3/stocks/2308581','/api/v3/stocks/2126188')and set(body)=={'chrtIds'}
  else:ok=False
  assert ok,'Read scope rejected '+m+' '+(u.hostname or'')+p
  return original(session,method,url,*a,**kw)
 wb=WB();validate_identity(c,wb);requests.sessions.Session.request=guard
 def req(host,path,method='GET',body=None,params=None):
  time.sleep(.8);r=requests.request(method,'https://'+host+path,headers={'Authorization':os.environ['WB_TOKEN_3']},json=body,params=params,timeout=(10,50));r.raise_for_status();return r.json()
 try:
  stage('campaigns',lambda:dict(observed_at=now(),adverts=req('advert-api.wildberries.ru','/api/advert/v2/adverts',params={'ids':','.join(map(str,scope['campaign_ids']))})['adverts']))
  if len(v.get('campaigns',{}).get('adverts',[]))!=4:raise ValueError('Exact four campaign readback missing')
  def budgets():return dict(observed_at=now(),rows={str(cid):req('advert-api.wildberries.ru','/adv/v1/budget',params={'id':cid})for cid in scope['campaign_ids']})
  stage('budgets',budgets)
  def minima():
   out={}
   for cp in v['campaigns']['adverts']:
    ids=[n['nm_id']for n in cp['nm_settings']];place='search'if cp['settings']['placements'].get('search')else'recommendation'
    out[str(cp['id'])]=req('advert-api.wildberries.ru','/api/advert/v1/bids/min','POST',dict(advert_id=cp['id'],nm_ids=ids,payment_type='cpc',placement_types=[place]))
   return dict(observed_at=now(),rows=out)
  stage('minimums',minima)
  stage('stock_guangzhou',lambda:read_stock(scope['gua_articles'],warehouse_role='guangzhou'))
  def cards():
   out=[]
   for nm in scope['gua_nm_ids']:
    body=dict(settings=dict(cursor=dict(limit=100),filter=dict(textSearch=str(nm),withPhoto=-1)))
    data=req('content-api.wildberries.ru','/content/v2/get/cards/list','POST',body)
    rows=[r for r in data.get('cards',[])if r.get('nmID')==nm]
    if len(rows)!=1:raise ValueError('Exact card missing '+str(nm))
    r=rows[0];out.append({k:r.get(k)for k in('nmID','vendorCode','subjectID','dimensions','sizes')})
   return dict(observed_at=now(),rows=out)
  stage('gua_cards',cards)
  def published():
   cards=v.get('gua_cards',{}).get('rows',[]);ids=[int(s['chrtID'])for r in cards for s in r['sizes']]
   assert cards and ids
   return dict(observed_at=now(),warehouse_id=2308581,size_to_nm={str(s['chrtID']):r['nmID']for r in cards for s in r['sizes']},raw=req('marketplace-api.wildberries.ru','/api/v3/stocks/2308581','POST',dict(chrtIds=ids)))
  stage('published_guangzhou',published)
  v.update(status='complete'if not v['errors']else'partial',completed_at=now());save()
  print(json.dumps(dict(status=v['status'],errors=v['errors'],stages=list(v),wb_writes=0,telegram_calls=0,model_calls=0)))
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()

