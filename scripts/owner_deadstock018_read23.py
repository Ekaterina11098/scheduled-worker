import json,time,requests
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner_deadstock:2026-11-23:v1'
def main():
 io=AdvertisingIO()
 if io.get(ROOT+':extra018'):print('Already read');return
 body={'settings':{'cursor':{'limit':100},'filter':{'textSearch':'018','withPhoto':-1}}}
 r=requests.post('https://content-api.wildberries.ru/content/v2/get/cards/trash',headers={'Authorization':io.token},json=body,timeout=(10,55));out={'status_code':r.status_code,'wb_writes':0}
 if r.ok:
  j=r.json();out['response']=j;out['matches']=[x for x in j.get('cards',[])if str(x.get('vendorCode','')).startswith('018-JuneBag')]
 else:out['error']=r.text[:500]
 io.create(ROOT+':extra018',out);print(json.dumps({'http':r.status_code,'matches':len(out.get('matches',[]))}))
if __name__=='__main__':main()
