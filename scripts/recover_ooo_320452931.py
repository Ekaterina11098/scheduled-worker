"""Single-use approved WB ООО order WB-GI-320452931, two exact bags, CNY."""
import copy,datetime as dt,json,collections
import fbs_document_chain as m
from fbs_wb_cabinets import ScopedCache
SID="WB-GI-320452931"; DATE="2026-11-26"
EXPECTED={"524-SamiraBag-black":1,"605-MadisonBag-cream":1}
CNY_ID="3c67e3a6-f25d-11ee-0a80-0c6f000a027f"
SOURCE="3c67619d-f25d-11ee-0a80-0c6f000a027a"
m.CONFIG="fbs_document_chain:ooo:config:v1"
m.STATE="fbs_document_chain:ooo:state:v1"
m.PREFIX="fbs_document_chain:ooo:supply:v1:"
t=m.Transport();db=ScopedCache(t,"ooo");config=copy.deepcopy(db.get(m.CONFIG))
if not config or config.get("cabinet")!="token_1" or config.get("status")!="active" or not config.get("writes_enabled") or not config.get("scope_confirmed"):raise m.Stop("ООО writer is not active")
for typ in m.TYPES:
 if m.href(config["templates"][typ].get("rate",{}).get("currency",{})).rsplit("/",1)[-1]!=CNY_ID:raise m.Stop("Template currency changed for "+typ)
config["execution_policy"]={**config.get("execution_policy",{}),"forbid_negative_stock":True}
w=m.Worker(t,db,config)
gate=w.execution_permission(direct=True)
if gate:raise m.Stop(gate["reason"])
if w._execution_permit.get("kind")!="manual" or w._execution_permit.get("supply_ids")!={SID}:raise m.Stop("Approval scope mismatch")
pre=db.get("fbs_recovery:20261125:ooo-320452931:preflight:v1")
if not pre or pre.get("status")!="inspected" or pre.get("quantity")!=2 or len(pre.get("order_ids",[]))!=2 or any(pre.get("docs",{}).values()) or pre.get("manual"):raise m.Stop("Read-only preflight no longer valid")
if db.get(m.PREFIX+SID):raise m.Stop("Existing WB ООО ledger needs review")
supplies=[s for s in w.supplies() if s.get("id")==SID]
if len(supplies)!=1 or not supplies[0].get("done"):raise m.Stop("WB supply missing/not closed")
s=supplies[0]
if s.get("name")!=pre["supply"]["name"] or s.get("closedAt")!=pre["supply"]["closedAt"]:raise m.Stop("Supply identity/date changed")
if m.stamp(s["closedAt"]).astimezone(dt.timezone(dt.timedelta(hours=3))).date().isoformat()!=DATE:raise m.Stop("WB close date mismatch")
positions,ids=w.positions(s)
if positions!=pre["positions"] or ids!=pre["order_ids"]:raise m.Stop("WB pick list drift")
actual={}
for p in positions:
 prod=t.request(m.MS,"entity/product/"+m.href(p["assortment"]).rsplit("/",1)[-1])
 if prod.get("archived"):raise m.Stop("Archived product")
 actual[prod.get("article")]=p["quantity"]
if actual!=EXPECTED:raise m.Stop("Product assortment differs from two verified bags")
if m.href(config["templates"]["demand"]["store"]).rsplit("/",1)[-1]!=SOURCE:raise m.Stop("Wrong origin")
for typ in m.TYPES:
 ext=config.get("document_prefix","fbs-china")+":"+SID+":"+typ
 if w.ms_rows("entity/"+typ,{"filter":"externalCode="+ext}):raise m.Stop("Existing MS document "+typ)
if w.ms_rows("entity/customerorder",{"filter":"name="+SID}):raise m.Stop("Existing manual MS customer order")
state={"supply":s,"positions":positions,"order_ids":ids,"status":"prepared","discovered_at":m.now()}
payload=copy.deepcopy(config["templates"]["demand"]);payload["positions"]=positions
w.require_available_stock(payload,state)
w.process(state)
if state.get("status")!="complete":raise m.Stop("MS chain incomplete")
out={}
for typ in m.TYPES:
 info=state["documents"][typ];doc=t.request(m.MS,"entity/"+typ+"/"+info["id"])
 if doc.get("applicable") is not True or doc.get("sum")!=0:raise m.Stop("Posting or total mismatch")
 expected_store=m.href(config["templates"][typ]["store"])
 if m.href(doc.get("store",{}))!=expected_store:raise m.Stop("MS store mismatch")
 cur=doc.get("rate",{}).get("currency",{})
 id=m.href(cur).rsplit("/",1)[-1]
 if t.request(m.MS,"entity/currency/"+id).get("isoCode")!="CNY":raise m.Stop("Document not in yuan")
 rows=w.ms_rows("entity/"+typ+"/"+info["id"]+"/positions")
 tally=lambda arr:collections.Counter({m.href(p["assortment"]):p["quantity"] for p in arr})
 if tally(rows)!=tally(positions) or any(p["price"]!=0 for p in rows):raise m.Stop("MS item readback mismatch")
 out[typ]={"name":doc["name"],"id":doc["id"],"currency":"CNY","quantity":2,"comment":doc.get("description")}
print(json.dumps({"status":"complete","supply":SID,"quantity":2,"articles":actual,"documents":out},ensure_ascii=False))
