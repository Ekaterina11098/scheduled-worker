"""Read-only WB ООО exact supply and MoySklad document/stock verification."""
import json, datetime as dt
import fbs_document_chain as m
from fbs_wb_cabinets import ScopedCache
SID="WB-GI-320452931"
class RO(m.Transport):
 def request(self,base,path,method="GET",body=None,params=None):
  if base==m.MS and method!="GET":raise m.Stop("MS writes forbidden in preflight")
  return super().request(base,path,method,body,params)
t=RO();m.CONFIG="fbs_document_chain:ooo:config:v1";m.STATE="fbs_document_chain:ooo:state:v1";m.PREFIX="fbs_document_chain:ooo:supply:v1:"
db=ScopedCache(t,"ooo");c=db.get(m.CONFIG);w=m.Worker(t,db,c)
s=t.request(m.WB,"api/v3/supplies/"+SID)
if s.get("id")!=SID or not s.get("done"):raise m.Stop("Exact WB ООО supply missing or not closed")
positions,ids=w.positions(s)
items=[]
for p in positions:
 info=t.request(m.MS,"entity/product/"+m.href(p["assortment"]).rsplit("/",1)[-1])
 items.append({"article":info.get("article"),"name":info.get("name"),"qty":p["quantity"]})
docs={}
for kind in m.TYPES:
 ext=c.get("document_prefix","fbs-ooo")+":"+SID+":"+kind
 docs[kind]=[{"id":x["id"],"name":x.get("name"),"posted":x.get("applicable")} for x in w.ms_rows("entity/"+kind,{"filter":"externalCode="+ext})]
manual=[{"id":x["id"],"name":x["name"]} for x in w.ms_rows("entity/customerorder",{"filter":"name="+SID})]
stockpayload=dict(c["templates"]["demand"],positions=positions)
warehouse=m.href(stockpayload["store"])
stocks=w.ms_rows("report/stock/all",{"filter":"store="+warehouse,"stockMode":"all","quantityMode":"all"})
byid={m.href(x).split("?")[0]:x for x in stocks}
short=[]
for p in positions:
 ref=m.href(p["assortment"]);record=byid.get(ref,{})
 if record.get("stock",0)<p["quantity"] or record.get("quantity",0)<p["quantity"]:
  item=next((x for x in items if x["article"]==record.get("article")),{})
  short.append({"product_href":ref,"qty":p["quantity"],"stock":record.get("stock",0),"available":record.get("quantity",0),"article":item.get("article")})
result={"status":"inspected","supply":s,"positions":positions,"order_ids":ids,"orders_count":len(ids),"quantity":sum(p["quantity"] for p in positions),"items":items,"docs":docs,"manual":manual,"warehouse":warehouse,"shortages":short,"currency":{k:c["templates"][k].get("rate") for k in m.TYPES}}
db.put("fbs_recovery:20261125:ooo-320452931:preflight:v1",result)
print(json.dumps({k:v for k,v in result.items() if k not in ("positions","order_ids")},ensure_ascii=False))
