"""Read-only exact WB IP source and MoySklad chain preflight."""
import json,os,datetime as dt
import fbs_document_chain as m
SID="WB-GI-310043377"
ROOT="fbs_recovery:20261113:310043377:"
class T(m.Transport):
 def request(self,base,path,method="GET",body=None,params=None):
  if base==m.MS and method!="GET":raise m.Stop("MS writes prohibited")
  return super().request(base,path,method,body,params)
t=T();db=m.Cache(t);c=db.get("fbs_document_chain:ip:config:v1")
w=m.Worker(t,db,c)
supplies=[s for s in w.supplies() if s.get("id")==SID]
if len(supplies)!=1:raise m.Stop("WB IP supply not found uniquely")
s=supplies[0]
found={}
for kind in m.TYPES:
 ext=c.get("document_prefix","fbs-ip")+":"+SID+":"+kind
 rows=w.ms_rows("entity/"+kind,{"filter":"externalCode="+ext})
 found[kind]=[{"id":r["id"],"name":r["name"],"store":m.href(r.get("store",{})),"applicable":r.get("applicable")} for r in rows]
manual=w.ms_rows("entity/customerorder",{"filter":"name="+SID})
out={"status":"inspected","supply":s,"docs":found,"orders_by_name":[{"id":o["id"],"name":o["name"]} for o in manual]}
if s.get("done"):
 positions,ids=w.positions(s)
 out["positions"]=positions
 out["ids"]=ids
 out["count"]=sum(p["quantity"] for p in positions)
 out["distinct_products"]=len(positions)
db.put(ROOT+"preflight:v1",out)
print(json.dumps({"status":out["status"],"supply":s,"count":out.get("count"),"distinct_products":out.get("distinct_products"),"docs":found,"orders_by_name":out["orders_by_name"]},ensure_ascii=False))
