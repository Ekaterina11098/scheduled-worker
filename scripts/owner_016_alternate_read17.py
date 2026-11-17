import json,time
from china_cloud_cost_control import Cache,WB,validate_identity,stamp
c=Cache();w=WB();validate_identity(c,w);out=[]
for query in ('&statuses=9&order=id&direction=desc','&statuses=9&order=id&direction=asc'):
 x=w.req('/api/advert/v2/adverts?ids=41270309'+query)['adverts'];assert len(x)==1 and x[0]['id']==41270309
 out.append(x[0]);time.sleep(3)
c.put('china_agent:owner_016_exclude631_keep:2026-11-17:v1:alternate_read',dict(status='complete',observed_at=stamp(),reads=out,wb_writes=0,telegram_calls=0))
print(json.dumps([dict(updated=x['timestamps']['updated'],targets=[n for n in x['nm_settings']if n['nm_id']in(1473246045,1604165742,1473245517)])for x in out]))
