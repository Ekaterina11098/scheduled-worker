"""Owner-approved exact WB China 319792093: resume the archived prepared chain only."""
import copy,datetime as dt,json
import fbs_document_chain as m
SID="WB-GI-319792093"
DAY="2026-11-24"
SOURCE="3c67619d-f25d-11ee-0a80-0c6f000a027a"
RETURN="c599b096-a784-11f1-0a80-15f1000f8193"
PRODUCT="614-MayaBag-black"
KEY=m.PREFIX+SID
t=m.Transport();db=m.Cache(t);config=copy.deepcopy(db.get(m.CONFIG))
if not config or config.get("cabinet")!="token_3" or config.get("status")!="active" or not config.get("writes_enabled") or not config.get("scope_confirmed"):
 raise m.Stop("China cabinet not authorized/active")
config["execution_policy"]={**config.get("execution_policy",{}),"forbid_negative_stock":True}
w=m.Worker(t,db,config)
gate=w.execution_permission(direct=True)
if gate:raise m.Stop(gate["reason"])
if getattr(w,"_execution_permit",{}).get("supply_ids")!={SID}:raise m.Stop("Approval must be only exact supply")
state=db.get(KEY)
if not state or state.get("status")!="prepared" or state.get("inflight") or state.get("documents"):
 raise m.Stop("Prepared journal not safe to resume")
route=state.get("warehouse_routing") or {}
if route.get("wb_warehouse_id")!=2126188 or route.get("source_store_id")!=SOURCE or route.get("return_store_id")!=RETURN:
 raise m.Stop("Approved routing not frozen correctly")
if len(state.get("order_ids",[]))!=43 or len(state.get("positions",[]))!=26 or sum(p["quantity"] for p in state["positions"])!=43:
 raise m.Stop("Frozen WB picking quantity changed")
supply=state["supply"]
if supply.get("id")!=SID or supply.get("name","").strip().casefold()!="сумки китай" or not supply.get("done"):
 raise m.Stop("WB supply identity changed")
if m.stamp(supply["closedAt"]).astimezone(dt.timezone(dt.timedelta(hours=3))).date().isoformat()!=DAY:
 raise m.Stop("WB local close date changed")
w.validate_source(state)
# Check live product identity, no manual documents, and available stock before first write.
expected_missing_href=m.MS+"entity/product/54db0c0c-fb7d-11f0-0a80-1aaa000fccb2"
if sum(p["quantity"] for p in state["positions"] if m.href(p.get("assortment",{}))==expected_missing_href)!=1:
 raise m.Stop("The formerly missing position has changed")
p=t.request(m.MS,"entity/product/"+expected_missing_href.split("/")[-1])
if p.get("article")!=PRODUCT or p.get("archived"):
 raise m.Stop("MayaBag product mismatch or archived")
for typ in m.TYPES:
 ext=config.get("document_prefix","fbs-china")+":"+SID+":"+typ
 if w.ms_rows("entity/"+typ,{"filter":"externalCode="+ext}):
  raise m.Stop("Existing MS document found: "+typ)
if w.ms_rows("entity/customerorder",{"filter":"name="+SID}):
 raise m.Stop("Existing manual order found")
stock=copy.deepcopy(config["templates"]["demand"])
stock["store"]["meta"]["href"]=m.MS+"entity/store/"+SOURCE
stock["positions"]=state["positions"]
w.require_available_stock(stock,state)
# Still no documents or negative stock: complete exact original chain with normal retry guard.
w.process(state)
if state.get("status")!="complete":raise m.Stop("Chain not fully complete")
verified={}
expected_quantity=sum(p["quantity"] for p in state["positions"])
for typ in m.TYPES:
 info=state["documents"][typ]
 d=t.request(m.MS,"entity/"+typ+"/"+info["id"])
 expect=RETURN if typ=="salesreturn" else SOURCE
 if m.href(d.get("store",{})).rsplit("/",1)[-1]!=expect or d.get("applicable") is not True or d.get("sum")!=0:
  raise m.Stop("MS posting/store/sum readback mismatch on "+typ)
 positions=w.ms_rows("entity/"+typ+"/"+info["id"]+"/positions")
 if sum(x["quantity"] for x in positions)!=expected_quantity or any(x["price"]!=0 for x in positions):
  raise m.Stop("MS positions or zero price readback mismatch on "+typ)
 verified[typ]={"name":d["name"],"id":d["id"],"quantity":expected_quantity}
print(json.dumps({"status":"complete","supply":SID,"source":"МСК","return":"Гонконг WB FBO","quantity":expected_quantity,"articles":26,"documents":verified},ensure_ascii=False))
