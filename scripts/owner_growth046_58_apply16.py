"""Exact two bids and two deposits, owner confirmed. No other WB mutation."""
import os,json,copy,time
from datetime import datetime,timezone,timedelta
import requests
from china_cloud_cost_control import Cache,stamp
from china_new_ads import Transport
ROOT='china_agent:owner_growth046_58_apply:2026-11-16:v1:'
SPEC=[dict(campaign_id=40933588,nm_id=1473243896,placement='recommendations',old_minor=30,target_minor=32,amount_cny=350),dict(campaign_id=41298169,nm_id=1473243910,placement='search',old_minor=28,target_minor=30,amount_cny=100)]
def projected(c):
 return {k:copy.deepcopy(c[k])for k in ['id','status','currency','bid_type','settings','nm_settings']}
def expected(before,item):
 c=projected(before)
 n=next(n for n in c['nm_settings']if n['nm_id']==item['nm_id'])
 n['bids_kopecks'][item['placement']]=item['target_minor']
 return c
def main():
 db=Cache();a=db.get(ROOT+'approval')
 assert a['status']=='approved'and a['owner_id']==5122667182 and a['scope']==SPEC
 def live():assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'].replace('Z','+00:00'))
 live()
 e=dict(status='running',approval_key=ROOT+'approval',items=[],created_at=stamp(),wb_writes=0)
 if not db.create(ROOT+'execution',e):raise RuntimeError('Existing execution: inspect, never repeat')
 token=os.environ['WB_TOKEN_3'];t=Transport(type('IO',(),dict(token=token))())
 def save():db.put(ROOT+'execution',e)
 def write(st,name,path,method,body=None):
  assert name not in st['steps'],'Duplicate mutation forbidden';live()
  st['steps'][name]=dict(status='submitting',path=path,method=method,body=body,at=stamp());save()
  try:r=t.request(path,method,body)
  except Exception:
   st['steps'][name]['status']='uncertain';e['status']='uncertain';save();raise
  st['steps'][name].update(status='accepted',response=r,accepted_at=stamp());e['wb_writes']+=1;save();return r
 def wait(fn):
  for i in range(10):
   try:return fn()
   except (AssertionError,RuntimeError,ValueError):
    if i==9:raise
    time.sleep(7)
 def verified(st,name,readback):
  st['steps'][name].update(status='verified',readback=readback,verified_at=stamp());save()
 try:
  ref=db.get('china_agent:owner_growth046_58_643:2026-11-16:v1:read');assert ref['prices']and ref['published_stock']and ref['msk_stock_cogs']['coverage_complete']
  assert datetime.now(timezone.utc)-datetime.fromisoformat(ref['completed_at'])<timedelta(hours=1)
  for x in SPEC:
   assert ref['published_stock']['amounts'][str(x['nm_id'])]>0
   pr=next(p for p in ref['prices']['rows']if p['nm_id']==x['nm_id'])
   stock=next(s for s in ref['msk_stock_cogs']['rows']if s['article']==pr['article'])
   assert stock['stock']-stock['reserve']>0 and stock['price']>0
  cfg=t.config();assert cfg['currency']=='CNY'and cfg['minTopUp']<=10000
  assert all(x['target_minor']%cfg['cpcStep']==0 and x['target_minor']<=cfg['cpcMaxBid']for x in SPEC)
  r=requests.get('https://advert-api.wildberries.ru/adv/v1/balance',headers={'Authorization':token},timeout=45)
  assert r.ok;account=r.json();assert account['currency']=='CNY'and account['net']>=450
  e['account_before']=account;e['config']=cfg;save()
  # Preflight both before the first write.
  for x in SPEC:
   c=t.campaign(x['campaign_id']);assert c['status']==9 and c['currency']=='CNY'and c['bid_type']=='manual'
   n=next(n for n in c['nm_settings']if n['nm_id']==x['nm_id']);old=n['bids_kopecks'][x['placement']]
   assert old in (x['old_minor'],x['target_minor'])
   assert c['settings']['placements'][x['placement']]is True
   typ='recommendation'if x['placement']=='recommendations'else'search'
   q=t.request('/api/advert/v1/bids/min','POST',dict(advert_id=x['campaign_id'],nm_ids=[x['nm_id']],payment_type='cpc',placement_types=[typ]))
   bids=[b['value']for row in q['bids']if row['nm_id']==x['nm_id']for b in row['bids']if b['type']==typ and b['currency']=='CNY']
   assert len(bids)==1 and bids[0]<=x['target_minor']
   st=dict(id=str(x['campaign_id']),campaign_id=x['campaign_id'],status='preflight',before=c,minimum=q,steps={},spec=x);e['items'].append(st);save()
  for st in e['items']:
   x=st['spec'];cid=x['campaign_id'];before=st['before'];target=expected(before,x)
   current=t.campaign(cid);assert projected(current)==projected(before),'Composition changed during preflight'
   old=next(n for n in before['nm_settings']if n['nm_id']==x['nm_id'])['bids_kopecks'][x['placement']]
   if old!=x['target_minor']:
    write(st,'bid','/api/advert/v1/bids','PATCH',dict(bids=[dict(advert_id=cid,nm_bids=[dict(nm_id=x['nm_id'],bid_kopecks=x['target_minor'],placement=x['placement'])])]))
    def bidread():
     c=t.campaign(cid);assert projected(c)==target;return c
    st['after_bid']=wait(bidread);verified(st,'bid',st['after_bid'])
   else:st['steps']['bid']=dict(status='verified',already_done=True,readback=current,verified_at=stamp());save()
   b=t.budget(cid);st['before_budget']=b;save()
   write(st,'funding','/adv/v1/budget/deposit?id='+str(cid),'POST',dict(sum=x['amount_cny'],type=1))
   def funded():
    b2=t.budget(cid);assert b+x['amount_cny']-2<=b2<=b+x['amount_cny'];return b2
   st['after_budget']=wait(funded);verified(st,'funding',st['after_budget'])
   after=t.campaign(cid);assert projected(after)==target
   st.update(status='verified',after=after,verified_at=stamp());save()
   child=ROOT+'campaign:'+str(cid);assert db.create(child,copy.deepcopy(st))
   reg=db.get('china_agent:verified_campaign_state:v1')or{};reg[str(cid)]=child;db.put('china_agent:verified_campaign_state:v1',reg)
  # Final independent state check after all four actions.
  for st in e['items']:
   c=t.campaign(st['campaign_id']);assert projected(c)==projected(st['after'])
   st['final_readback']=c;st['final_balance']=t.budget(st['campaign_id'])
  e.update(status='verified',verified_at=stamp(),funded_cny=450);save()
 except Exception as ex:
  pending=any(z.get('status')in('submitting','accepted','uncertain')for st in e['items']for z in st['steps'].values())
  e.update(status='uncertain'if pending else'partial'if any(st['status']=='verified'for st in e['items'])else'blocked',reason=str(ex)[:250]or type(ex).__name__);save();raise
 print(json.dumps(dict(status=e['status'],wb_writes=e['wb_writes'],funded_cny=e['funded_cny'])))
if __name__=='__main__':main()
