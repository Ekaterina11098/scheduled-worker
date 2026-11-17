import json,time,requests,os
from china_cloud_cost_control import Cache,WB,validate_identity,stamp
from china_package_readback import validate
R='china_agent:owner_016_exclude631_keep:2026-11-17:v1'
c=Cache();w=WB();validate_identity(c,w);e=c.get(R+':execution')
assert e['status']=='uncertain'
def read(cid):return w.campaigns([cid])[str(cid)]
i=dict(id=e['items'][0]['id'],kind='ad_exclude_sku',campaign_id=41270309,nm_id=1604165742)
r=validate([i],e['items'],read);c.put(R+':reconciliation',dict(r,checked_at=stamp(),wb_writes=0,telegram_calls=0))
if r['status']=='verified':
 after=r['rounds'][-1]['campaigns']['41270309']
 assert any(n['nm_id']==1473246045 and n['bids_kopecks']['recommendations']==28 for n in after['nm_settings'])
 e.update(status='verified',after=after,package_readback=r,verified_at=stamp(),keep631_preserved=True,read_only_reconciled=True)
 e['items'][0].update(status='verified',after=after,verified_at=e['verified_at'])
 c.put(R+':execution',e);reg=c.get('china_agent:verified_campaign_state:v1')or{};reg['41270309']=R+':execution';c.put('china_agent:verified_campaign_state:v1',reg)
 c.put('china_agent:ad_rule_execution:owner016-exclude631-keep17:v1',dict(status='done',canonical_source_execution_key=R+':execution',alias_of_verified_batch=True,wb_writes=0,items=[dict(i,status='verified',before=e['before'],after=after,verified_at=e['verified_at'],source_execution_key=R+':execution')]))
 e['reporting_registered']=True;c.put(R+':execution',e)
print(json.dumps(dict(status=r['status'],reads=len(r['rounds']),targets=[[n for n in x.get('campaigns',{}).get('41270309',{}).get('nm_settings',[]) if n['nm_id'] in(1473246045,1604165742)]for x in r['rounds']])))
