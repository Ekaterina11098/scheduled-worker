"""Task-local clean GET journal transport; shared transports and MS guards unchanged."""
import gzip,json,os,urllib.request,urllib.error,urllib.parse
import cny_migration_backup_20261125 as b
m=b.m
class JournalTransport(b.ReadOnly):
 def _request_once(self,base,path,method='GET',body=None,params=None,cache_prefer=None):
  expected=os.environ['SUPABASE_URL'].rstrip('/')+'/rest/v1/'
  if base!=expected or method!='GET':
   return super()._request_once(base,path,method,body,params,cache_prefer)
  assert path=='telegram_api_cache' and body is None
  assert params and params.get('cache_key','').startswith('eq.'),'Only explicit private journal keys allowed'
  token=os.environ['SUPABASE_SECRET_KEY']
  headers={'Accept':'application/json','Accept-Encoding':'gzip','Authorization':'Bearer '+token,'apikey':token}
  req=urllib.request.Request(base+path+'?'+urllib.parse.urlencode(params),headers=headers,method='GET')
  try:
   with urllib.request.urlopen(req,timeout=45) as response:
    raw=response.read()
    if response.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
    return json.loads(raw) if raw else None
  except urllib.error.HTTPError as error:raise m.Stop('HTTP_'+str(error.code)+' GET telegram_api_cache') from None
  except (TimeoutError,urllib.error.URLError):raise m.Stop('API transport outcome uncertain') from None
