import json,time,requests
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
from owner_blocked542_media23 import ROOT,stable
def main():
 io=AdvertisingIO();e=io.get(ROOT+':execution');assert e and e['wb_writes']==1;item=e['items'][0];before=item['before'];reads=[]
 for i in range(6):
  time.sleep(6);r=requests.post('https://content-api.wildberries.ru/content/v2/get/cards/list',headers={'Authorization':io.token,'Cache-Control':'no-cache,no-store,max-age=0','Pragma':'no-cache'},json={'settings':{'cursor':{'limit':100},'filter':{'textSearch':'1473243239','withPhoto':-1}}},timeout=(10,55));r.raise_for_status();rows=[c for c in r.json()['cards']if c['nmID']==1473243239 and c['vendorCode']=='542-CelineaBag-darkbrown'];assert len(rows)==1;c=rows[0];reads.append(c);item['readonly_reconciliation']=reads;io.put(ROOT+':execution',e)
  if len(reads)>=2 and all(not(x.get('photos')or x.get('video'))and stable(x)==stable(before)for x in reads[-2:]):
   item.update(status='verified',after=c,verified_at=datetime.now(timezone.utc).isoformat());item['operation']['status']='verified';e.update(status='verified',completed_at=item['verified_at']);e.pop('error',None);io.put(ROOT+':execution',e);print('Verified media empty');return
 print('Still not verified; no mutations')
if __name__=='__main__':main()
