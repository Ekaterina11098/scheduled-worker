"""Read-only exact November 24 China stock shortage and anti-duplicate reconciliation."""
import json,collections
import fbs_document_chain as m
SID="WB-GI-319792093"
KEY="fbs_document_chain:china:supply:v1:"+SID
class T(m.Transport):
 def request(self,base,path,method="GET",body=None,params=None):
  if base==m.MS and method!="GET":raise m.Stop("No MS changes in preflight")
  return super().request(base,path,method,body,params)
t=T();db=m.Cache(t);state=db.get(KEY);c=db.get("fbs_document_chain:china:config:v1")
if not state or not c or state.get("supply",{}).get("id")!=SID:raise m.Stop("Invalid journal")
w=m.Worker(t,db,c)
origin=state.get("warehouse_routing",{}).get("source_store_id")
if origin!="3c67619d-f25d-11ee-0a80-0c6f000a027a":raise m.Stop("Unexpected origin")
stocks=w.ms_rows("report/stock/all",{"filter":"store="+m.MS+"entity/store/"+origin,"stockMode":"all","quantityMode":"all"})
byid={m.href(row).split("?")[0]:row for row in stocks}
needed=collections.Counter()
for p in state.get("positions",[]):
 needed[m.href(p["assortment"]).split("?")[0]]+=p["quantity"]
shortages=[]
for product,quantity in needed.items():
 stock=byid.get(product,{})
 if stock.get("stock",0)<quantity or stock.get("quantity",0)<quantity:
  detail=t.request(m.MS,"entity/product/"+product.split("/")[-1])
  shortages.append({"article":detail.get("article"),"name":detail.get("name"),"required":quantity,"stock":stock.get("stock",0),"available":stock.get("quantity",0)})
docs={}
for typ in m.TYPES:
 ext=c.get("document_prefix","fbs-china")+":"+SID+":"+typ
 docs[typ]=[{"id":d["id"],"name":d.get("name")} for d in w.ms_rows("entity/"+typ,{"filter":"externalCode="+ext})]
byname=[{"id":d["id"],"name":d.get("name")} for d in w.ms_rows("entity/customerorder",{"filter":"name="+SID})]
supply=t.request(m.WB,"api/v3/supplies/"+SID)
result={"at":m.now(),"supply":SID,"name":supply.get("name"),"closedAt":supply.get("closedAt"),"done":supply.get("done"),"source_store":"МСК","required_total":sum(needed.values()),"unique_products":len(needed),"shortages":shortages,"documents":docs,"customerorders_by_name":byname,"status":"needs_owner_decision" if shortages else "stock_sufficient"}
db.put("fbs_recovery:20261124:319792093:readback:v1",result)
print(json.dumps(result,ensure_ascii=False))
