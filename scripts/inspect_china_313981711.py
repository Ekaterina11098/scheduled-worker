"""Read-only reconciliation: exact WB supply 313981711 and MoySklad documents."""
import json
import fbs_document_chain as m
SID="WB-GI-313981711"
KEY="fbs_document_chain:china:supply:v1:"+SID
class ReadOnly(m.Transport):
    def request(self,base,path,method="GET",body=None,params=None):
        if base==m.MS and method!="GET":raise m.Stop("MoySklad writes prohibited")
        return super().request(base,path,method,body,params)
t=ReadOnly();db=m.Cache(t)
state=db.get(KEY); config=db.get("fbs_document_chain:china:config:v1")
if not state or not config:raise m.Stop("Missing configured ledger")
worker=m.Worker(t,db,config)
result={"supply":SID,"journal_status":state.get("status"),"docs":{},"orders_by_name":[],"errors":[]}
try:
 s=t.request(m.WB,"api/v3/supplies/"+SID)
 result["wb_supply"]={k:s.get(k) for k in ("id","name","done","closedAt")}
except Exception as e:
 result["errors"].append("WB: "+str(e))
for typ in m.TYPES:
    item=state.get("documents",{}).get(typ)
    row={"journal_id":item.get("id") if item else None}
    if item:
        try:
            d=t.request(m.MS,"entity/"+typ+"/"+item["id"])
            positions=worker.ms_rows("entity/"+typ+"/"+item["id"]+"/positions")
            row.update(exists=True,name=d.get("name"),description=d.get("description"),posted=d.get("applicable"),total=d.get("sum"),store=m.href(d.get("store",{})),quantity=sum(p.get("quantity",0) for p in positions),lines=len(positions),prices_ok=all(p.get("price")==0 for p in positions))
        except Exception as e:
            row.update(exists=False,error=str(e))
    try:
        code=config.get("document_prefix","fbs-china")+":"+SID+":"+typ
        matches=worker.ms_rows("entity/"+typ,{"filter":"externalCode="+code})
        row["external_matches"]=[{"id":v["id"],"name":v.get("name")} for v in matches]
    except Exception as e:
        result["errors"].append("Search "+typ+": "+str(e))
    result["docs"][typ]=row
try:
    matches=worker.ms_rows("entity/customerorder",{"filter":"name="+SID})
    result["orders_by_name"]=[{"id":v["id"],"name":v.get("name")} for v in matches]
except Exception as e:result["errors"].append("Name search: "+str(e))
result["status"]="inspected" if not result["errors"] else "partial"
db.put("fbs_recovery:20261118:313981711:readback:v1",result)
print(json.dumps(result,ensure_ascii=False))
