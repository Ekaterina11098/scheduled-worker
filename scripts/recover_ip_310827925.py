"""Exact owner approved IP WB supply repair, with category verified from MoySklad product."""
import copy,datetime as dt,json
import fbs_document_chain as m
from fbs_wb_cabinets import ScopedCache
SID="WB-GI-310827925"
ARTICLES={"101-Zont-pink":1,"155-ReginaBag-pink":1,"41-Zont-white":1,"60-NoelBag-black":1}
DESC="14 11 26 ИП Сумки и зонты"
m.CONFIG="fbs_document_chain:ip:config:v1"
m.STATE="fbs_document_chain:ip:state:v1"
m.PREFIX="fbs_document_chain:ip:supply:v1:"
t=m.Transport()
db=ScopedCache(t,"ip")
c=copy.deepcopy(db.get(m.CONFIG))
if not c or c.get("cabinet")!="token_2" or c.get("status")!="active" or not c.get("writes_enabled"):
 raise m.Stop("IP cabinet not active")
c["execution_policy"]={**c.get("execution_policy",{}),"forbid_negative_stock":True}
class SpecificWorker(m.Worker):
 def order_annotation(self,supply,route=None):
  if supply.get("id")!=SID or supply.get("name")!="ИП":
   raise m.Stop("Unexpected supply identity or name")
  meta=self.t.request(m.MS,"entity/customerorder/metadata")
  states=[s for s in meta.get("states",[]) if s.get("name")=="Возврат на ФБО"]
  if len(states)!=1:raise m.Stop("Required order state missing")
  return {"description":DESC,"state":m.meta(states[0])}
w=SpecificWorker(t,db,c)
decision=w.execution_permission(direct=True)
if decision:raise m.Stop(decision["reason"])
if w._execution_permit.get("supply_ids")!={SID}:raise m.Stop("Approval outside exact supply")
key=m.PREFIX+SID
existing=db.get(key)
if existing and (existing.get("inflight") or existing.get("documents") or existing.get("status") not in ("prepared", "discovered")):
 raise m.Stop("Existing journal requires reconciliation")
supplies=[s for s in w.supplies() if s.get("id")==SID]
if len(supplies)!=1 or not supplies[0].get("done") or supplies[0].get("name")!="ИП":
 raise m.Stop("Source WB supply missing, not closed or changed")
supply=supplies[0]
day=m.stamp(supply["closedAt"]).astimezone(dt.timezone(dt.timedelta(hours=3))).date().isoformat()
if day!="2026-11-14":raise m.Stop("WB date mismatch")
positions,ids=w.positions(supply)
if len(ids)!=4 or len(positions)!=4 or sum(p["quantity"] for p in positions)!=4:
 raise m.Stop("Source four-item scope differs")
if existing and (existing.get("positions") != positions or existing.get("order_ids") != ids):
 raise m.Stop("Previously frozen WB pick list has changed")
actual={}
for pos in positions:
 p=t.request(m.MS,"entity/product/"+m.href(pos["assortment"]).rsplit("/",1)[-1])
 if p.get("archived") or not p.get("article"):raise m.Stop("Archived or unnamed product")
 actual[p["article"]]=pos["quantity"]
if actual!=ARTICLES:raise m.Stop("Category/product identities changed")
for kind in m.TYPES:
 ext=c.get("document_prefix","fbs-ip")+":"+SID+":"+kind
 if w.ms_rows("entity/"+kind,{"filter":"externalCode="+ext}):
  raise m.Stop("Existing MS "+kind+" document, manual reconciliation needed")
if w.ms_rows("entity/customerorder",{"filter":"name="+SID}):
 raise m.Stop("Existing MS order found")
state=copy.deepcopy(existing) if existing else {"supply":supply,"status":"discovered","discovered_at":m.now()}
# Check exact stock BEFORE creating even the customer order.
stock=copy.deepcopy(c["templates"]["demand"]);stock["positions"]=positions
w.require_available_stock(stock,state)
w.process(state)
if state.get("status")!="complete":raise m.Stop("Incomplete document chain")
results={}
for kind in m.TYPES:
 info=state["documents"][kind]
 doc=t.request(m.MS,"entity/"+kind+"/"+info["id"])
 expected_store=m.href(c["templates"][kind]["store"])
 if doc.get("description")!=DESC or doc.get("applicable") is not True or doc.get("sum")!=0 or m.href(doc.get("store",{}))!=expected_store:
  raise m.Stop("Incorrect document comment, store, posting or sum")
 rows=w.ms_rows("entity/"+kind+"/"+info["id"]+"/positions")
 if len(rows)!=4 or sum(r["quantity"] for r in rows)!=4 or any(r["price"]!=0 for r in rows):raise m.Stop("Position mismatch")
 results[kind]={"name":info["name"],"id":info["id"]}
print(json.dumps({"status":"complete","supply":SID,"articles":ARTICLES,"quantity":4,"comment":DESC,"documents":results},ensure_ascii=False))
