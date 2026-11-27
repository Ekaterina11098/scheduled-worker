import base64,copy,datetime,json,os,sys,time,types,unittest
from pathlib import Path
from unittest.mock import patch
from ooo_wb_config_cache import remember
P=Path(__file__).parent;T=json.loads((P/'ooo_report_templates.json').read_text(encoding='utf-8'))
class Flow(unittest.TestCase):
 def test_warm_then_fresh_stats_uses_no_configuration_request_or_delivery(self):
  rows={};calls=[];stamp=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
  change=(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(minutes=2)).isoformat()
  class DB:
   def get(self,k):return copy.deepcopy(rows.get(k))
   def once(self,k,v):
    if k in rows:raise AssertionError('Duplicate claim')
    rows[k]=copy.deepcopy(v)
   def update(self,k,v):rows[k]=copy.deepcopy(v)
   def api(self,*args):return [{'payload':{'sid':'fixture'}}]
  cfg={'id':1,'currency':'KGS','status':9,'settings':{'name':'fixture'},'timestamps':{'updated':change},'nm_settings':[]}
  remember(DB(),[cfg]);root='ooo_agent:midday:2026-11-11:1500';rows[root+':request']={'read_only':True,'cabinet':'token_1','day':'2026-11-11','campaign_ids':[1]}
  def get(url,**kw):
   calls.append(url)
   if url.endswith('/count'):data={'adverts':[{'status':9,'type':9,'advert_list':[{'advertId':1,'changeTime':change}]}]}
   elif url.endswith('/fullstats'):data=[{'advertId':1,'currency':'KGS','days':[]}]
   else:raise AssertionError('Unnecessary config read or unapproved endpoint')
   return types.SimpleNamespace(status_code=200,headers={},json=lambda:data)
  claims={'sid':'fixture','t':False,'s':0,'exp':time.time()+3600};token='header.'+base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('=')+'.signature'
  mods={'china_codex_cloud':types.SimpleNamespace(DB=DB,stamp=stamp),'requests':types.SimpleNamespace(get=get)}
  ns={'__name__':'offline'}
  with patch.dict(sys.modules,mods),patch.dict(os.environ,{'WB_TOKEN_1':token,'GITHUB_RUN_ID':'offline','OOO_REPORT_CONFIG_WARM_ONLY':'1'}):
   exec(T['midreader'],ns);ns['run']()
  self.assertEqual(rows[root+':read']['status'],'configurations_ready');self.assertEqual(len(calls),1)
  with patch.dict(sys.modules,mods),patch.dict(os.environ,{'WB_TOKEN_1':token,'GITHUB_RUN_ID':'offline','OOO_REPORT_CONFIG_WARM_ONLY':'0'}):ns['run']()
  self.assertEqual(rows[root+':read']['status'],'complete');self.assertEqual(sum(u.endswith('/fullstats')for u in calls),1)
  self.assertEqual(sum(u.endswith('/adverts')for u in calls),0)
if __name__=='__main__':unittest.main()
