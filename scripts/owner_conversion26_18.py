import requests,json
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_cloud_cost_control import Cache,WB,validate_identity
from china_wb_evidence import FUNNEL,normalize_funnel
KEY='china_agent:owner_conversion26_18:v1:result'
def main():
 io=AdvertisingIO();validate_identity(Cache(),WB());assert not io.get(KEY);out=dict(status='reading',observed_at=datetime.now(timezone.utc).isoformat(),wb_writes=0,telegram_calls=0);assert io.create(KEY,out)
 body=dict(selectedPeriod=dict(start='2026-11-26',end='2026-11-26'),pastPeriod=dict(start='2026-11-25',end='2026-11-25'),nmIds=[],brandNames=[],subjectIds=[],tagIds=[],skipDeletedNm=False,orderBy=dict(field='openCard',mode='desc'),limit=1000,offset=0)
 try:
  r=requests.post(FUNNEL,headers={'Authorization':io.token},json=body,timeout=90,allow_redirects=False);r.raise_for_status();data=r.json()['data'];assert data['currency']=='CNY' and len(data['products'])<1000
  out.update(status='complete',request=body,raw=data,rows=normalize_funnel(data['products'],body['selectedPeriod'],body['pastPeriod'],KEY),completed_at=datetime.now(timezone.utc).isoformat());io.put(KEY,out);print(json.dumps(dict(status='complete',rows=len(out['rows']))))
 except Exception as e:out.update(status='blocked',reason=type(e).__name__+': '+str(e)[:200]);io.put(KEY,out);raise
if __name__=='__main__':main()


