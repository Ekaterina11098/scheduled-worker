"""Single-use recovery: exact three WB China consignments closed on 25 November 2026, CNY."""
import copy,datetime as dt,json,os,collections
import fbs_document_chain as m
SID_LIST=("WB-GI-320214719","WB-GI-320215134","WB-GI-320384463")
DAY="2026-11-25"
CNY_ID="3c67e3a6-f25d-11ee-0a80-0c6f000a027f"
CNY_REF=m.MS+"entity/currency/"+CNY_ID
ROOT="fbs_recovery:20261125:"
t=m.Transport();db=m.Cache(t)
config=copy.deepcopy(db.get(m.CONFIG))
census=db.get(ROOT+"census:v1")
if not config or config.get("cabinet")!="token_3" or not config.get("writes_enabled") or config.get("status")!="active" or not config.get("scope_confirmed"):
 raise m.Stop("China configuration not active")
if not census or census.get("status")!="inspected":raise m.Stop("Source census not verified")
if {x["id"] for x in census["wb"].get("china",[]) if x["id"] in SID_LIST}!=set(SID_LIST):raise m.Stop("Expected three supplies absent in preflight")
live_currency=t.request(m.MS,"entity/currency/"+CNY_ID)
if live_currency.get("isoCode")!="CNY" or live_currency.get("archived"):raise m.Stop("Configured currency is not active CNY")
for typ in m.TYPES:
 template=config["templates"][typ]
 if m.href(template.get("rate",{}).get("currency",{}))!=CNY_REF:raise m.Stop("Wrong template currency for "+typ)
config["execution_policy"]={**config.get("execution_policy",{}),"forbid_negative_stock":True}
w=m.Worker(t,db,config)
decision=w.execution_permission(direct=True)
if decision:raise m.Stop(decision["reason"])
if w._execution_permit.get("kind")!="manual" or w._execution_permit.get("supply_ids")!=set(SID_LIST):
 raise m.Stop("Approval scope not equal exact three supplies")
report={"at":m.now(),"date":DAY,"currency":"CNY","rate_rub_per_cny":"MoySklad default","status":"running","completed":[],"blocked":[]}
def record():db.put(ROOT+"recovery:v1",report)
record()
supplies={s["id"]:s for s in w.supplies() if s.get("id") in SID_LIST}
for sid in SID_LIST:
 try:
  s=supplies.get(sid)
  if not s or not s.get("done") or m.stamp(s["closedAt"]).astimezone(dt.timezone(dt.timedelta(hours=3))).date().isoformat()!=DAY:
   raise m.Stop("WB supply closed/date mismatch")
  prior=db.get(m.PREFIX+sid)
  if prior and (prior.get("inflight") or prior.get("documents") or prior.get("status")=="complete"):
   raise m.Stop("Journal contains documents or uncertain write")
  pre=next(x for x in census["wb"]["china"] if x["id"]==sid)
  if any(pre["existing"].values()) or pre["manual_orders"]:
   raise m.Stop("Census had prior MS documents")
  for typ in m.TYPES:
   ext=config.get("document_prefix","fbs-china")+":"+sid+":"+typ
   if w.ms_rows("entity/"+typ,{"filter":"externalCode="+ext}):
    raise m.Stop("Live duplicate MS "+typ)
  if w.ms_rows("entity/customerorder",{"filter":"name="+sid}):
   raise m.Stop("Live manual MS order exists")
  state=copy.deepcopy(prior) if prior else {"supply":s,"status":"discovered","discovered_at":m.now()}
  if prior and prior.get("status") not in ("prepared","discovered","customerorder_rejected","demand_rejected","salesreturn_rejected"):
   raise m.Stop("Existing ledger state requires manual review")
  state["supply"]=s
  if prior and "positions" in state:
   positions,ids=w.positions(s)
   if positions!=state["positions"] or ids!=state["order_ids"]:raise m.Stop("Frozen WB picking list changed")
  w.process(state)
  if state.get("status")!="complete":raise m.Stop("Chain incomplete")
  quantity=sum(x["quantity"] for x in state["positions"])
  docs={}
  for typ in m.TYPES:
   info=state["documents"][typ]
   doc=t.request(m.MS,"entity/"+typ+"/"+info["id"])
   if doc.get("applicable") is not True or doc.get("sum")!=0:
    raise m.Stop("Not posted or non-zero "+typ)
   currency=doc.get("rate",{})
   currency_href=m.href(currency.get("currency",{}))
   if not currency_href.startswith(m.MS+"entity/currency/"):raise m.Stop("Missing MS currency "+typ)
   currency_obj=t.request(m.MS,"entity/currency/"+currency_href.rsplit("/",1)[-1])
   if currency_obj.get("isoCode")!="CNY":raise m.Stop("MS document is not in CNY "+typ)
   route=state["warehouse_routing"]
   expect_store=route["return_store_id"] if typ=="salesreturn" else route["source_store_id"]
   if m.href(doc["store"]).rsplit("/",1)[-1]!=expect_store:
    raise m.Stop("Wrong MS store in "+typ)
   rows=w.ms_rows("entity/"+typ+"/"+info["id"]+"/positions")
   a=collections.Counter({m.href(p["assortment"]):p["quantity"] for p in state["positions"]})
   b=collections.Counter({m.href(p["assortment"]):p["quantity"] for p in rows})
   if a!=b or sum(p["quantity"] for p in rows)!=quantity or any(p["price"]!=0 for p in rows):
    raise m.Stop("Positions changed in "+typ)
   docs[typ]={"name":info["name"],"currency":"CNY","rate":currency.get("value"),"currency_id":currency_href.rsplit("/",1)[-1]}
  report["completed"].append({"id":sid,"quantity":quantity,"articles":len(state["positions"]),"warehouse":state["warehouse_routing"]["source_store"],"docs":docs})
 except Exception as e:
  report["blocked"].append({"id":sid,"reason":str(e) if isinstance(e,m.Stop) else type(e).__name__})
 record()
report["status"]="complete" if not report["blocked"] else "requires_attention"
report["completed_at"]=m.now();record()
print(json.dumps(report,ensure_ascii=False))
if report["blocked"]:raise SystemExit(1)
