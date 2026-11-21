import json
from china_advertising_state import AdvertisingIO
from china_advertising_v2 import build
from china_advertising_cards import enhance
from china_advertising_economic_review import apply
io=AdvertisingIO();s=io.get('china_agent:advertising_source:2026-11-21:v2')
m={}
for cid,q in s['full_growth_inputs'].get('minimums',{}).items():
 for row in q['bids']:
  vals=[b['value']for b in row['bids']if b.get('currency')=='CNY']
  if len(vals)==1:m[cid+':'+str(row['nm_id'])]=vals[0]
r=apply(enhance(build(s,m),s),s,m)
d={'status':'diagnosed','blockers':r['economic_review_blockers'],'rows':[{'cid':c['id'],'nm':x['nm'],'article':x['article'],'economics':x.get('economics'),'blocker':x.get('data_blocker')}for c in r['campaigns']for x in c.get('focus',[])if x.get('data_blocker')]}
k='china_agent:morning21:diagnostic:v1'
if not io.get(k):io.create(k,d)
else:io.put(k,d)
print(json.dumps(d,ensure_ascii=False))
