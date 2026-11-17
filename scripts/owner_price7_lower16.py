"""Exact seven Codex-owner prices, existing durable engine; zero Telegram/model traffic."""
import os,json,time,hashlib
from datetime import datetime,timezone
from decimal import Decimal
from urllib.parse import urlparse,quote
import requests
from china_price_apply import IO,process,plan,PREFIX,POLICY,CHAT,BOT,day,now,sha
ROOT='china_agent:owner_price7_lower:2026-11-16:v1'
EXPECTED={'1473243819':('517-NoelBag-white','208',50),'1473243891':('0-NoelBag-green','175',50),'1473243900':('596-NoelBag-zgrey','218.5',50),'1473243912':('60-NoelBag-black','218',50),'1473245492':('141-PamelaBag-brown','355.5',50),'1535337771':('3-FurPanama-coffee','114',40),'1535337773':('5-FurPanama-beige','111',50)}
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
class OwnerIO(IO):
 def __init__(self):
  self.url=os.environ['SUPABASE_URL'].rstrip('/');secret=os.environ['SUPABASE_SECRET_KEY'];self.headers={'apikey':secret,'Content-Type':'application/json'}
  if not secret.startswith('sb_secret_'):self.headers['Authorization']='Bearer '+secret
  self.token=os.environ['WB_TOKEN_3'];self.before={};self.post_count=0
  self.command=super().get(ROOT+':approval');p=self.command
  assert p['status']=='authorized' and p['execution_authorized']is True and p['actor_user_id']==5122667182 and p['source_channel']=='codex' and p['telegram_delivery']is False
  assert day()==p['day']=='2026-11-16' and now()<datetime.fromisoformat(p['expires_at'].replace('Z','+00:00'))
  assert len(p['selections'])==7 and {s['nm_id'] for s in p['selections']}==set(EXPECTED)
  for s in p['selections']:
   art,target,discount=EXPECTED[s['nm_id']]
   assert s['article']==art and Decimal(s['target_cny'])==Decimal(target) and s['seller_discount']==discount and s['club_discount']==0
   assert s['action']=='\u0421\u043d\u0438\u0436\u0435\u043d\u0438\u0435' and Decimal(s['current_cny'])*Decimal('.95')<=Decimal(target)<Decimal(s['current_cny'])
  self.approval_key=PREFIX+str(CHAT)+':0:5122667182:'+digest(p['selections'])
  self.execution_key='china_agent:price_execution:v1:'+self.approval_key[len(PREFIX):]
  self.approval=dict(schema_version=2,execution_authorized=True,execution_policy=POLICY,approval_policy='all_current_human_group_members',decision='approved_recommendation',chat_id=CHAT,bot_id=BOT,report_job_id=0,report_date=p['day'],actor_user_id=5122667182,created_at=p['created_at'],selections=p['selections'],basis='explicit_codex_owner_exact_prices',owner_command_key=ROOT+':approval',telegram_delivery=False)
 def get(self,key):return self.approval if key==getattr(self,'approval_key',None)else super().get(key)
 def validate(self,a):
  p=super().get(ROOT+':approval');assert digest(p)==digest(self.command) and a==self.approval
  assert os.environ['GITHUB_REPOSITORY']=='Ekaterina11098/scheduled-worker' and os.environ['GITHUB_REF']=='refs/heads/main'
 def tg(self,*args,**kwargs):raise RuntimeError('Owner forbids Telegram calls')
 def prices(self,ids):
  prices=super().prices(ids)
  if not self.before:self.before=prices;self.save(ROOT+':before',dict(observed_at=now().isoformat(),rows=prices,wb_writes=0))
  return prices
 def save(self,key,value):
  if super().get(key)is None:
   if not self.create(key,value):raise RuntimeError('Concurrent state create')
  else:self.put(key,value)
 def put(self,key,value):
  if key==getattr(self,'execution_key',None):
   value.update(source_channel='codex',owner_command_key=ROOT+':approval',telegram_delivery=False)
   for item in value.get('items',[]):
    nm=item['selection']['nm_id']
    if nm in self.before:item.setdefault('before',self.before[nm])
    if item.get('status')=='applied':item.setdefault('verified_at',now().isoformat())
  super().put(key,value)
 def wb(self,path,method='GET',body=None):
  if method=='POST':
   assert path=='/api/v2/upload/task' and self.post_count==0 and set(body)=={'data'}
   assert 1<=len(body['data'])<=7 and len({r['nmID']for r in body['data']})==len(body['data'])
   state=super().get(self.execution_key);assert state['status']=='submitting' and state['request']==body
   for row in body['data']:
    nm=str(row['nmID']);assert nm in EXPECTED
    art,target,discount=EXPECTED[nm];assert row['discount']==discount and Decimal(row['price'])*(100-discount)/100==Decimal(target)
   self.post_count+=1
  return super().wb(path,method,body)
def main():
 io=OwnerIO();e=process(io,io.approval_key,polls=18)
 if e['status']=='done':
  # Independent final WB read, including items already at target; never another write.
  live=io.prices(list(EXPECTED));checks=[]
  for nm,(art,target,discount)in EXPECTED.items():
   p=live[nm];assert p['vendorCode']==art and p['currencyIsoCode4217']=='CNY' and p['discount']==discount and p['clubDiscount']==0
   assert p['sizes'] and all(Decimal(str(s['discountedPrice']))==Decimal(target)for s in p['sizes'])
   checks.append(dict(nm_id=nm,article=art,target_cny=target,discount=discount,status='verified',readback=p))
  io.save(ROOT+':verified',dict(status='verified',execution_key=io.execution_key,completed_at=now().isoformat(),items=checks,telegram_calls=0,model_calls=0))
 io.save(ROOT+':result',dict(status=e['status'],execution_key=io.execution_key,upload_id=e.get('upload_id'),items=[dict(nm_id=x['selection']['nm_id'],status=x['status'],reason=x.get('reason'))for x in e.get('items',[])],post_count=io.post_count,telegram_calls=0,model_calls=0,observed_at=now().isoformat()))
 print(json.dumps(dict(status=e['status'],upload_id=e.get('upload_id'),items=len(e.get('items',[])),post_count=io.post_count,telegram_calls=0)))
if __name__=='__main__':
 original=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);method=method.upper()
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=u.path.startswith('/rest/v1/')and method in('GET','POST','PATCH')
  elif u.hostname=='discounts-prices-api.wildberries.ru':ok=(method=='GET'and u.path in('/ping','/api/v2/list/goods/filter','/api/v2/history/tasks','/api/v2/history/goods/task'))or(method=='POST'and u.path=='/api/v2/upload/task')
  else:ok=False
  assert ok,'Network request outside exact-price owner scope'
  return original(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 try:main()
 finally:requests.sessions.Session.request=original

