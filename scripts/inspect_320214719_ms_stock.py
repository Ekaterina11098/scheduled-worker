"""Read-only detailed item stock for 25 Nov WB 320214719, after MS 3007 demand rejection."""
import json,collections
import fbs_document_chain as m
SID="WB-GI-320214719"
SOURCE="3c67619d-f25d-11ee-0a80-0c6f000a027a"
class ReadOnly(m.Transport):
 def request(self,base,path,method="GET",body=None,params=None):
  if base==m.MS and method!="GET":raise m.Stop("No MS mutations")
  return super().request(base,path,method,body,params)
t=ReadOnly();db=m.Cache(t);s=db.get(m.PREFIX+SID);w=m.Worker(t,db,db.get(m.CONFIG))
if not s or s.get("status")!="demand_rejected" or not s.get("positions"):raise m.Stop("Journal changed")
data=w.ms_rows("report/stock/all",{"filter":"store="+m.MS+"entity/store/"+SOURCE,"stockMode":"all","quantityMode":"all"})
byid={m.href(row).split("?")[0]:row for row in data}
items=[]
for p in s["positions"]:
 ref=m.href(p["assortment"]);detail=t.request(m.MS,"entity/product/"+ref.rsplit("/",1)[-1])
 row=byid.get(ref,{})
 items.append({"article":detail.get("article"),"name":detail.get("name"),"needed":p["quantity"],"stock":row.get("stock",0),"available":row.get("quantity",0),"reserve":row.get("reserve",0),"inTransit":row.get("inTransit",0),"current_shortage":row.get("stock",0)<p["quantity"] or row.get("quantity",0)<p["quantity"]})
order_id=s.get("documents",{}).get("customerorder",{}).get("id")
order=t.request(m.MS,"entity/customerorder/"+order_id,params={"fields":"stock","expand":"positions"})
doc_stock=[]
for p in (order.get("positions",{}) or {}).get("rows",[]):
 ref=m.href(p.get("assortment",{}))
 doc_stock.append({"item":ref.rsplit("/",1)[-1],"quantity":p.get("quantity"),"stock":p.get("stock",{})})
out={"status":"inspected","supply":SID,"warehouse":"МСК","closedAt":s["supply"]["closedAt"],"customer_order_moment":order.get("moment"),"items":items,"order_stock_info":doc_stock}
db.put("fbs_recovery:20261125:320214719:stock_diagnostic:v1",out)
print(json.dumps({"status":"inspected","items":len(items),"shortages":[x for x in items if x["current_shortage"]],"stock_in_order":doc_stock},ensure_ascii=False))
