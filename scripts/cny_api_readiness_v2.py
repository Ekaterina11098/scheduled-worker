"""Read-only live readiness audit; no MS mutations or external service changes."""
import datetime,sys
import cny_migration_backup_20261125 as b
m=b.m

def main():
 t=b.ReadOnly();db=m.Cache(t)
 manifest=db.get(b.ROOT+'backup_manifest:v1')
 assert manifest and db.get(b.ROOT+'verified_plan:v1')['status']=='complete'
 currencies=b.fullrows(t,'entity/currency')
 defaults=[x for x in currencies if x.get('default')]
 assert len(defaults)==1
 snapshot={'at':m.now(),'ms_writes':0,'default_currency':{k:defaults[0].get(k) for k in ('id','isoCode','system','default')},'currencies':[{k:x.get(k) for k in ('id','isoCode','system','default')} for x in currencies],'types':[]}
 for item in manifest['counts']+[{'type':'inventory','count':db.get(b.ROOT+'scope_extra:inventory')['count']}]:
  typ=item['type'];expected=item['count']
  current=t.request(m.MS,'entity/'+typ,params={'limit':1})
  row={'type':typ,'baseline_count':expected,'live_count':current['meta']['size']}
  if expected:
   key=('backup_extra:inventory:0' if typ=='inventory' else 'backup:'+typ+':page:0')
   page=db.get(b.ROOT+key)
   cutoff=page.get('read_at') or page.get('at') or manifest['created_at']
   dt=datetime.datetime.fromisoformat(cutoff.replace('Z','+00:00')).astimezone(datetime.timezone(datetime.timedelta(hours=3)))
   moment=dt.strftime('%Y-%m-%d %H:%M:%S')
   changed=t.request(m.MS,'entity/'+typ,params={'limit':1,'filter':'updated>='+moment})
   row.update({'changes_since_first_page':changed['meta']['size'],'cutoff_msk':moment})
  snapshot['types'].append(row)
  b.put(db,'api_readiness:v2',dict(snapshot,status='running'))
 snapshot['status']='complete'
 snapshot['base_currency_gate']='ready_cny' if defaults[0].get('isoCode')=='CNY' else 'requires_accounting_currency_switch'
 snapshot['requires_refresh']=any(x['baseline_count']!=x['live_count'] or x.get('changes_since_first_page',0) for x in snapshot['types'])
 b.put(db,'api_readiness:v2',snapshot)
 print('Read-only API readiness audit completed; results saved privately.')
if __name__=='__main__':
 try:main()
 except Exception as error:
  try:
   db=m.Cache(b.ReadOnly())
   b.put(db,'api_readiness_error:v2',{'status':'failed','error':type(error).__name__,'detail':str(error),'at':m.now(),'ms_writes':0})
  finally:
   print('Read-only audit stopped; inspect private diagnostics.')
  sys.exit(1)
