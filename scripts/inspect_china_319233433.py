"""Read only: exact WB China 319233433, list scope, origin, MoySklad docs and stock."""
import json,collections,datetime as dt
import fbs_document_chain as m
SID="WB-GI-319233433"
ROOT="fbs_recovery:20261124:319233433:"
class RO(m.Transport):
 def request(self,base,path,method="GET",body=None,params=None):
  if base==m.MS and method!="GET":raise m.Stop("MS changes disabled in preflight")
  return super().request(base,path,method,body,params)
t=RO();db=m.Cache(t);c=db.get("fbs_document_chain:china:config:v1")
if not c:raise m.Stop("Missing China configuration")
w=m.Worker(t,db,c)
s=t.request(m.WB,"api/v3/supplies/"+SID)
if s.get("id")!=SID or not s.get("done"):raise m.Stop("Supply unavailable or not closed")
positions,ids=w.positions(s)
wh_ids=w._source_warehouse_ids
routes={str(v):sum(1 for x in wh_ids.values() if x==v) for v in set(wh_ids.values())}
items=[]
for p in positions:
 product=t.request(m.MS,"entity/product/"+m.href(p["assortment"]).rsplit("/",1)[-1])
 items.append({"article":product.get("article"),"name":product.get("name"),"id":product.get("id"),"quantity":p["quantity"]})
found={}
for typ in m.TYPES:
 ext=c.get("document_prefix","fbs-china")+":"+SID+":"+typ
 found[typ]=[{"id":x["id"],"name":x.get("name"),"posted":x.get("applicable")} for x in w.ms_rows("entity/"+typ,{"filter":"externalCode="+ext})]
manual=w.ms_rows("entity/customerorder",{"filter":"name="+SID})
expected_stores={2126188:("3c67619d-f25d-11ee-0a80-0c6f000a027a","МСК"),2308581:("2233c6a7-d906-11f1-0a80-197e004df0d2","Гуанджоу"),2373413:("2233c6a7-d906-11f1-0a80-197e004df0d2","Гуанджоу")}
shortages=[]
if len(routes)==1:
 origin=next(iter(routes))
 if int(origin) in expected_stores:
  store_id,_=expected_stores[int(origin)]
  stock=w.ms_rows("report/stock/all",{"filter":"store="+m.MS+"entity/store/"+store_id,"stockMode":"all","quantityMode":"all"})
  byid={m.href(row).split("?")[0]:row for row in stock}
  for p in positions:
   ref=m.href(p["assortment"]);row=byid.get(ref,{})
   if row.get("stock",0)<p["quantity"] or row.get("quantity",0)<p["quantity"]:
    detail=next((item for item in items if item["id"]==ref.rsplit("/",1)[-1]),{})
    shortages.append({"article":detail.get("article"),"required":p["quantity"],"stock":row.get("stock",0),"available":row.get("quantity",0)})
data={"status":"inspected","supply":s,"order_ids":ids,"positions":positions,"items":items,"warehouses":routes,"documents":found,"manual_orders":[{"id":x["id"],"name":x["name"]} for x in manual],"shortages":shortages,"orders_count":len(ids),"quantity":sum(p["quantity"] for p in positions)}
db.put(ROOT+"preflight:v1",data)
print(json.dumps({k:v for k,v in data.items() if k not in ("positions","order_ids")},ensure_ascii=False))
