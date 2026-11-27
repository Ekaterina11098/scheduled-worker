import ast,copy,json,hashlib,datetime,pathlib,unittest
P=pathlib.Path(__file__).parent
tree=ast.parse((P/'ip_scheduled_source.py').read_text(encoding='utf8'))
ns={'json':json,'hashlib':hashlib,'datetime':datetime.datetime,'timedelta':datetime.timedelta,'timezone':datetime.timezone,'REPORT_DAY':'2026-11-27','DAY':'2026-11-27','SLOT':'midday','NOW':datetime.datetime(2026,11,27,13,5,tzinfo=datetime.timezone.utc),'RUN_ID':'test','memo':{},'memo_ids':{},'state':{'reused':[]},'period':lambda a:(a.get('d1'),a.get('d2')),'decode_rows':lambda r:r}
for n in tree.body:
 if isinstance(n,ast.FunctionDef)and n.name in('digest','reuse_cutoff','snapshot','existing'):exec(compile(ast.Module(body=[n],type_ignores=[]),'source','exec'),ns)
class Tests(unittest.TestCase):
 def test_exact_insert_id_not_unindexed_run_filter(self):
  calls=[];p={'value':1}
  def db(method,table,params=None,body=None):
   calls.append((method,params))
   if method=='POST':return [{'id':12345}]
   self.assertEqual(params,{'id':'eq.12345','select':'id,payload','limit':1});return [{'id':12345,'payload':[p]}]
  ns['database']=db;self.assertEqual(ns['snapshot']('mpstats_test',p,'2026-11-27','2026-11-27'),12345);self.assertEqual(calls[0][1],{'select':'id'})
 def test_retry_hour_does_not_recollect_saved_midday(self):
  ns['memo'].clear();ns['memo_ids'].clear();ns['state']['reused']=[];args={'d1':'2026-11-27','d2':'2026-11-27','campaign_id':123,'report':'products'};obs={'tool':'wbbidder_campaign_stats','arguments':args,'status':'received'};calls=[]
  def db(method,table,params=None):
   calls.append(params)
   if params.get('select')=='id':self.assertEqual(params['collected_at'],'gte.2026-11-27T11:30:00+00:00');return [{'id':23028}]
   return [{'id':23028,'payload':[copy.deepcopy(obs)]}]
  ns['database']=db;self.assertEqual(ns['existing']('wbbidder_campaign_stats',args),obs);self.assertEqual(ns['state']['reused'],[23028]);self.assertEqual(ns['existing']('wbbidder_campaign_stats',args),obs);self.assertEqual(len(calls),2)
if __name__=='__main__':unittest.main()
