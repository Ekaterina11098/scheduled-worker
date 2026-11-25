"""Owner-approved one-off WB China 319233433, exactly the 25-order PDF dated 25 Nov."""
import collections,copy,datetime as dt,json
import fbs_document_chain as m
SID="WB-GI-319233433"
DAY="2026-11-25"
SOURCE="2233c6a7-d906-11f1-0a80-197e004df0d2"
RETURN="c599b096-a784-11f1-0a80-15f1000f8193"
ORDERS={6339130621,6339505941,6339586239,6339833228,6339840050,6340025081,6340295385,6341081775,6341217310,6341833230,6342019671,6342522127,6343227385,6343291033,6343416727,6343418891,6343825884,6344347014,6345133026,6345301742,6345345736,6345720995,6346450088,6346669061,6346820599}
PDF_ARTICLES={"025-MadisonBag-zblack":1,"026-MadisonBag-zcoffee":1,"157-CelineaBag-black":1,"161-SamantaBag-black":3,"163-SamantaBag-coffee":3,"164-SamantaBag-darkred":1,"339-CristineBag-black":2,"341-ElodieBag-black":1,"342-ElodieBag-coffee":2,"345-AurelieBag-black":1,"359-CelesteBag-darkred":1,"360-CelesteBag-coffee":1,"361-CelesteBag-black":1,"363-CelineaBag-darkred":2,"364-CelineaBag-coffee":1,"70-CelineaBag-zblack":1,"71-CelineaBag-zcoffee":1,"72-CelineaBag-zdarkred":1}
t=m.Transport();db=m.Cache(t);config=copy.deepcopy(db.get(m.CONFIG))
if not config or config.get("cabinet")!="token_3" or config.get("status")!="active" or not config.get("writes_enabled") or not config.get("scope_confirmed"):
 raise m.Stop("China cabinet not activated")
config["execution_policy"]={**config.get("execution_policy",{}),"forbid_negative_stock":True}
w=m.Worker(t,db,config)
decision=w.execution_permission(direct=True)
if decision:raise m.Stop(decision["reason"])
if w._execution_permit.get("supply_ids")!={SID}:raise m.Stop("Wrong manual approval scope")
snapshot=db.get("fbs_recovery:20261124:319233433:preflight:v1")
if not snapshot or snapshot.get("status")!="inspected" or snapshot.get("quantity")!=25 or set(snapshot.get("order_ids",[]))!=ORDERS:
 raise m.Stop("Preflight differs from 25-unit PDF")
if snapshot.get("documents")!={k:[] for k in m.TYPES} or snapshot.get("manual_orders"):
 raise m.Stop("Previous snapshot found potential duplicate")
if db.get(m.PREFIX+SID):
 raise m.Stop("Supply already has a journal; requires manual reconciliation")
supply=t.request(m.WB,"api/v3/supplies/"+SID)
if not supply.get("done") or supply.get("id")!=SID or supply.get("name")!=snapshot["supply"]["name"]:
 raise m.Stop("WB supply not closed or identity changed")
if m.stamp(supply["closedAt"]).astimezone(dt.timezone(dt.timedelta(hours=3))).date().isoformat()!=DAY:
 raise m.Stop("Supply closed on different Moscow day")
positions,ids=w.positions(supply)
if set(ids)!=ORDERS or len(ids)!=25 or len(positions)!=18 or sum(x["quantity"] for x in positions)!=25:
 raise m.Stop("Live WB picking list differs from approved 25-unit PDF")
if positions!=snapshot["positions"]:
 raise m.Stop("Product identities changed since read-only check")
origin_ids=set(w._source_warehouse_ids.values())
if origin_ids!={2373413}:
 raise m.Stop("Unexpected WB source warehouse, not Guangzhou")
actual=collections.Counter()
for pos in positions:
 p=t.request(m.MS,"entity/product/"+m.href(pos["assortment"]).rsplit("/",1)[-1])
 if p.get("archived") or not p.get("article"):
  raise m.Stop("Product not identified")
 actual[p["article"]]+=pos["quantity"]
if dict(actual)!=PDF_ARTICLES:
 raise m.Stop("Exact 25-unit PDF article quantities disagree with WB")
for kind in m.TYPES:
 code=config.get("document_prefix","fbs-china")+":"+SID+":"+kind
 if w.ms_rows("entity/"+kind,{"filter":"externalCode="+code}):
  raise m.Stop("Existing MS document found; no duplicate creation")
if w.ms_rows("entity/customerorder",{"filter":"name="+SID}):
 raise m.Stop("Existing MS order named after supply")
state={"supply":supply,"status":"discovered","discovered_at":m.now(),"positions":positions,"order_ids":ids}
stock=copy.deepcopy(config["templates"]["demand"])
stock["store"]["meta"]["href"]=m.MS+"entity/store/"+SOURCE
stock["positions"]=positions
w.require_available_stock(stock,state)
# Run the existing guarded worker, which independently verifies WB source warehouse and links.
w.process(state)
if state.get("status")!="complete":raise m.Stop("Document chain incomplete")
docs={}
for kind in m.TYPES:
 info=state["documents"][kind]
 d=t.request(m.MS,"entity/"+kind+"/"+info["id"])
 source=RETURN if kind=="salesreturn" else SOURCE
 if m.href(d.get("store",{})).rsplit("/",1)[-1]!=source or d.get("applicable") is not True or d.get("sum")!=0:
  raise m.Stop("Wrong MS store or posting for "+kind)
 rows=w.ms_rows("entity/"+kind+"/"+d["id"]+"/positions")
 counter=collections.Counter({m.href(v["assortment"]):v["quantity"] for v in rows})
 expected=collections.Counter({m.href(v["assortment"]):v["quantity"] for v in positions})
 if counter!=expected or any(v["price"]!=0 for v in rows):
  raise m.Stop("MS item identity/quantity/price mismatch")
 docs[kind]={"name":d["name"],"id":d["id"],"description":d.get("description")}
print(json.dumps({"status":"complete","supply":SID,"quantity":25,"unique_articles":18,"removed_order_6346595797":True,"source":"Гуанджоу","return":"Гонконг WB FBO","documents":docs},ensure_ascii=False))
