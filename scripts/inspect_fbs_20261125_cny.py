"""Read-only 25 Nov WB / Ozon recovery inventory and MoySklad currency verification."""
import os, json, datetime as dt
import fbs_document_chain as m
from fbs_wb_cabinets import ScopedCache
DATE="2026-11-25"
ROOT="fbs_recovery:20261125:"
T=dt.timezone(dt.timedelta(hours=3))
class ReadOnly(m.Transport):
 def request(self,base,path,method="GET",body=None,params=None):
  if base==m.MS and method!="GET":raise m.Stop("MoySklad mutation forbidden in preflight")
  return super().request(base,path,method,body,params)
t=ReadOnly();db=m.Cache(t)
r={"at":m.now(),"date":DATE,"status":"reading","currency":{},"wb":{},"ozon":[],"errors":[]}
for cabinet,index in (("china","3"),("ip","2"),("ooo","1")):
 try:
  os.environ["WB_TOKEN_3"]=os.environ["WB_TOKEN_"+index]
  m.CONFIG="fbs_document_chain:"+cabinet+":config:v1"
  m.STATE="fbs_document_chain:"+cabinet+":state:v1"
  m.PREFIX="fbs_document_chain:"+cabinet+":supply:v1:"
  cache=ScopedCache(t,cabinet);config=cache.get(m.CONFIG)
  w=m.Worker(t,cache,config)
  if cabinet=="china":
   currency_list=w.ms_rows("entity/currency")
   r["currency"]["available"]=[{"id":x.get("id"),"name":x.get("name"),"code":x.get("code"),"isoCode":x.get("isoCode"),"archived":x.get("archived")} for x in currency_list]
  r["currency"][cabinet]={kind:config["templates"][kind].get("rate") for kind in m.TYPES}
  supplies=[]
  for s in w.supplies():
   if not s.get("done") or not s.get("closedAt"):continue
   if m.stamp(s["closedAt"]).astimezone(T).date().isoformat()!=DATE:continue
   sid=s["id"];state=cache.get(m.PREFIX+sid)
   docs={}
   for kind in m.TYPES:
    ext=config.get("document_prefix","fbs-china")+":"+sid+":"+kind
    rows=w.ms_rows("entity/"+kind,{"filter":"externalCode="+ext})
    docs[kind]=[{"id":d.get("id"),"name":d.get("name"),"currency":d.get("rate"),"store":m.href(d.get("store",{}))} for d in rows]
   manual=w.ms_rows("entity/customerorder",{"filter":"name="+sid})
   supplies.append({"id":sid,"name":s.get("name"),"closedAt":s.get("closedAt"),"state":state.get("status") if state else None,"inflight":state.get("inflight") if state else None,"existing":docs,"manual_orders":[{"id":v["id"],"name":v["name"]} for v in manual]})
  r["wb"][cabinet]=supplies
 except Exception as e:r["errors"].append({"cabinet":cabinet,"error":str(e) if isinstance(e,m.Stop) else type(e).__name__})
 db.put(ROOT+"census:v1",r)
try:
 from fbs_ozon_chain import acts
 cfg=db.get("fbs_document_chain:ozon:config:v1")
 r["currency"]["ozon"]={kind:cfg["templates"][kind].get("rate") for kind in m.TYPES}
 for a in acts():
  if a.get("departure_date")!=DATE:continue
  sid="OZON-ACT-"+str(a["id"])
  state=db.get("fbs_document_chain:ozon:supply:v1:"+sid)
  r["ozon"].append({"act_id":a["id"],"departure_date":a.get("departure_date"),"state":state.get("status") if state else None,"raw":a})
except Exception as e:r["errors"].append({"cabinet":"ozon","error":str(e) if isinstance(e,m.Stop) else type(e).__name__})
r["status"]="inspected" if not r["errors"] else "partial"
db.put(ROOT+"census:v1",r)
print(json.dumps({"status":r["status"],"wb":{k:v for k,v in r["wb"].items()},"ozon":[{"id":x["act_id"],"state":x["state"]} for x in r["ozon"]],"currencies":r["currency"],"errors":r["errors"]},ensure_ascii=False))
