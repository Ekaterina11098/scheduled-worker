"""Read-only MPStats historical prices for 51 missing prebulk China baselines."""
import os,json,time,requests
from datetime import datetime,timezone,timedelta
from urllib.parse import urlparse
from analytics.mpstats_probe import decode_response,unpack_tool,ProbeError,sanitize
URL=os.environ['SUPABASE_URL'].rstrip('/')
KEY=os.environ['SUPABASE_SECRET_KEY']
TOKEN=os.environ['MPSTATS_API_TOKEN'].strip()
ROOT='china_agent:owner_missing51_mpprices27:v1'
def now():return datetime.now(timezone.utc).isoformat()
def db(method,params=None,body=None):
 r=requests.request(method,URL+'/rest/v1/telegram_api_cache',params=params,json=body,headers={'apikey':KEY,'Authorization':'Bearer '+KEY,'Prefer':'resolution=merge-duplicates'},timeout=45);r.raise_for_status();return r.json()if r.content else[]
def get(key):
 v=db('GET',{'cache_key':'eq.'+key,'select':'payload','limit':1});return v[0]['payload']if v else None
def put(key,payload):
 db('POST',{'on_conflict':'cache_key'},{'cache_key':key,'payload':payload,'updated_at':now(),'expires_at':(datetime.now(timezone.utc)+timedelta(days=3650)).isoformat()})
src=get('china_agent:sheet_dashboard:v1:data')
ev=db('GET',{'cache_key':'like.china_agent:experience:v1:owner-price-rules24-*','select':'payload','limit':1000})
known={n for e in ev for n in e['payload']['action']['nm_ids']}
scope=[x for x in src['catalogue']if x['nm']not in known]
assert len(scope)==51
state=get(ROOT+':result')or dict(status='discovering',created_at=now(),scope=scope,rows={},wb_writes=0,telegram_calls=0)
headers={'Accept':'application/json, text/event-stream','Content-Type':'application/json'}
session=requests.Session();counter=0
def rpc(method,params):
 global counter
 assert method in ('initialize','tools/list','tools/call')
 if method=='tools/call':
  assert params['name']in ('repricer_tokens','mine_products_history')
  if params['name']=='mine_products_history':
   a=params['arguments'];assert a['nmid']in {x['nm']for x in scope}and a['d1']=='2026-11-20'and a['d2']=='2026-11-24'and a['marketplace']=='wildberries'
 counter+=1
 r=session.post('https://mcp.mpstats.io/mcp',params={'token':TOKEN},headers=headers,json={'jsonrpc':'2.0','id':counter,'method':method,'params':params},timeout=(10,65),allow_redirects=False)
 value=decode_response(r,counter)
 if r.headers.get('Mcp-Session-Id'):headers['Mcp-Session-Id']=r.headers['Mcp-Session-Id']
 return value
try:
 init=rpc('initialize',{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'veschi-owner-readonly-price-history','version':'1'}})
 headers['MCP-Protocol-Version']=init['protocolVersion']
 r=session.post('https://mcp.mpstats.io/mcp',params={'token':TOKEN},headers=headers,json={'jsonrpc':'2.0','method':'notifications/initialized'},timeout=(10,60),allow_redirects=False);assert r.status_code in(200,202,204)
 def tool(name,args):return unpack_tool(rpc('tools/call',{'name':name,'arguments':args}))
 tokens=tool('repricer_tokens',{})
 # Store account connection identifiers/names only, never authentication tokens.
 state['tokens']=sanitize(tokens);state['status']='tokens_received';put(ROOT+':result',state)
 rows=tokens.get('data',[])if isinstance(tokens,dict)else tokens
 if isinstance(rows,dict):rows=rows.get('tokens',rows.get('data',[]))
 assert isinstance(rows,list),'Unexpected token listing schema'
 selected=[x for x in rows if isinstance(x,dict)and 'Гонконг'in str(x.get('name',''))]
 if len(selected)!=1:
  state['status']='identity_needs_review';put(ROOT+':result',state);raise SystemExit('Saved connection discovery; exact China identity needs review')
 tid=selected[0]['id'];state['connection_id']=tid;state['status']='collecting';put(ROOT+':result',state)
 for x in scope:
  if str(x['nm'])in state['rows']:continue
  try:
   value=tool('mine_products_history',{'user_token_id':tid,'nmid':x['nm'],'marketplace':'wildberries','d1':'2026-11-20','d2':'2026-11-24'})
   state['rows'][str(x['nm'])]=dict(article=x['article'],status='received',observed_at=now(),data=sanitize(value))
  except ProbeError as e:
   state['rows'][str(x['nm'])]=dict(article=x['article'],status=e.status,detail=e.detail,observed_at=now())
   put(ROOT+':result',state)
   if e.status in('access_denied','rate_limited','tool_access_error'):raise
  put(ROOT+':result',state);time.sleep(1)
 state['status']='complete';state['completed_at']=now();put(ROOT+':result',state)
except SystemExit:raise
except Exception as e:
 state['status']='partial';state['error']=type(e).__name__+':'+(e.status if isinstance(e,ProbeError)else str(e)[:250])
 put(ROOT+':result',state);raise SystemExit('Read checkpoint saved: '+state['error'])
print('Saved readonly MPStats price history '+str(len(state['rows']))+'/51')
