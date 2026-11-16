"""Read only exact WB IP 14 Nov 310827925 source, products, live documents and stock."""
import json,datetime as dt
import fbs_document_chain as m
SID="WB-GI-310827925"
ROOT="fbs_recovery:20261114:310827925:"
class ReadOnly(m.Transport):
 def request(self,base,path,method="GET",body=None,params=None):
  if base==m.MS and method!="GET":raise m.Stop("MS writes prohibited")
  return super().request(base,path,method,body,params)
t=ReadOnly();db=m.Cache(t);c=db.get("fbs_document_chain:ip:config:v1");w=m.Worker(t,db,c)
supplies=[x for x in w.supplies() if x.get("id")==SID]
if len(supplies)!=1:raise m.Stop("Exact WB supply unavailable")
s=supplies[0]
found={}
for typ in m.TYPES:
 ext=c.get("document_prefix","fbs-ip")+":"+SID+":"+typ
 found[typ]=[{"id":v["id"],"name":v["name"],"applicable":v.get("applicable")} for v in w.ms_rows("entity/"+typ,{"filter":"externalCode="+ext})]
manual=[{"id":v["id"],"name":v["name"]} for v in w.ms_rows("entity/customerorder",{"filter":"name="+SID})]
state=db.get("fbs_document_chain:ip:supply:v1:"+SID)
result={"status":"inspected","supply":s,"documents":found,"manual_orders":manual,"previous_status":state.get("status") if state else None}
if s.get("done"):
 positions,ids=w.positions(s)
 items=[]
 for pos in positions:
  product=t.request(m.MS,"entity/product/"+m.href(pos["assortment"]).rsplit("/",1)[-1])
  items.append({"article":product.get("article"),"name":product.get("name"),"quantity":pos["quantity"],"id":product.get("id")})
 result.update(positions=positions,order_ids=ids,quantity=sum(x["quantity"] for x in positions),items=items,previous_matches=(state is not None and state.get("positions")==positions and state.get("order_ids")==ids))
db.put(ROOT+"preflight:v1",result)
print(json.dumps({k:v for k,v in result.items() if k not in ("positions","order_ids")},ensure_ascii=False))
