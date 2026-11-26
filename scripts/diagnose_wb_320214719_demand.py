"""Single guarded diagnostic for HTTP 412 on WB 320214719 demand. No duplicate writes."""
import collections,copy,datetime as dt,json,re
import fbs_document_chain as m
SID="WB-GI-320214719"
KEY=m.PREFIX+SID
SOURCE="3c67619d-f25d-11ee-0a80-0c6f000a027a"
RETURN="c599b096-a784-11f1-0a80-15f1000f8193"
original_urlopen=m.urllib.request.urlopen
def filtered_urlopen(req,timeout=None):
 try:
  return original_urlopen(req,timeout=timeout)
 except m.urllib.error.HTTPError as error:
  if req.method=="POST" and req.full_url.split("?")[0]==m.MS+"entity/demand":
   try:
    body=json.loads(error.read().decode("utf-8"))
    entries=body.get("errors",[])
    messages=[]
    for entry in entries[:8]:
     desc=str(entry.get("error",""))
     desc=re.sub(r"https?://[^ ]+","[URL]",desc)
     desc=re.sub(r"(?i)(bearer|token|password|api_key)\\s*[:=]\\s*[^ ]+","[redacted]",desc)
     messages.append({"code":entry.get("code"),"message":desc[:400]})
    print(json.dumps({"event":"moysklad_demand_validation","http_status":error.code,"issues":messages},ensure_ascii=False))
   except Exception:
    print(json.dumps({"event":"moysklad_demand_validation","http_status":error.code,"issues":"Response not parseable"}))
  raise
m.urllib.request.urlopen=filtered_urlopen
t=m.Transport();db=m.Cache(t);c=copy.deepcopy(db.get(m.CONFIG))
if c.get("cabinet")!="token_3" or not c.get("writes_enabled") or c.get("status")!="active":
 raise m.Stop("China writer not active")
for typ in m.TYPES:
 rate=c["templates"][typ].get("rate",{})
 if m.href(rate.get("currency",{}))!=m.MS+"entity/currency/3c67e3a6-f25d-11ee-0a80-0c6f000a027f" or "value" in rate:
  raise m.Stop("Native configured CNY rate changed")
c["execution_policy"]={**c.get("execution_policy",{}),"forbid_negative_stock":True}
w=m.Worker(t,db,c)
permit=w.execution_permission(direct=True)
if permit:raise m.Stop(permit["reason"])
if w._execution_permit.get("supply_ids")!={SID}:raise m.Stop("Approval scope mismatch")
state=db.get(KEY)
if not state or state.get("status")!="demand_rejected" or state.get("inflight") or set(state.get("documents",{}))!={"customerorder"}:
 raise m.Stop("Partial chain state changed; do not retry")
route=state.get("warehouse_routing",{})
if route.get("source_store_id")!=SOURCE or route.get("return_store_id")!=RETURN:
 raise m.Stop("Warehouse mismatch")
if not state.get("positions") or not state.get("order_ids"):
 raise m.Stop("Frozen WB positions absent")
if not state.get("supply",{}).get("done"):
 raise m.Stop("WB supply not closed")
w.validate_source(state)
# Compare live MS order identity and check no demand or return already exists.
order_info=state["documents"]["customerorder"]
order=t.request(m.MS,"entity/customerorder/"+order_info["id"])
if order.get("name")!=SID or not order.get("applicable") or m.href(order["store"]).rsplit("/",1)[-1]!=SOURCE:
 raise m.Stop("Existing order identity, posting or origin changed")
for typ in ("demand","salesreturn"):
 ext=c.get("document_prefix","fbs-china")+":"+SID+":"+typ
 if w.ms_rows("entity/"+typ,{"filter":"externalCode="+ext}):
  raise m.Stop("Existing MS "+typ+" document found")
stock=copy.deepcopy(c["templates"]["demand"])
stock["store"]["meta"]["href"]=m.MS+"entity/store/"+SOURCE
stock["positions"]=state["positions"]
w.require_available_stock(stock,state)
# Only attempt the exact original chain via existing idempotent Worker.process.
w.process(state)
if state.get("status")!="complete":raise m.Stop("Chain not complete")
qty=sum(p["quantity"] for p in state["positions"])
out={}
for typ in m.TYPES:
 info=state["documents"][typ]
 d=t.request(m.MS,"entity/"+typ+"/"+info["id"])
 if d.get("applicable") is not True or d.get("sum")!=0:
  raise m.Stop("Wrong posting or sum")
 expected=RETURN if typ=="salesreturn" else SOURCE
 if m.href(d["store"]).rsplit("/",1)[-1]!=expected:raise m.Stop("Store mismatch")
 curr=d.get("rate",{}).get("currency",{})
 cid=m.href(curr).rsplit("/",1)[-1]
 currency=t.request(m.MS,"entity/currency/"+cid)
 if currency.get("isoCode")!="CNY":raise m.Stop("Not CNY")
 rows=w.ms_rows("entity/"+typ+"/"+info["id"]+"/positions")
 tally=lambda z:collections.Counter({m.href(p["assortment"]):p["quantity"] for p in z})
 if tally(rows)!=tally(state["positions"]) or any(p["price"]!=0 for p in rows):raise m.Stop("Position mismatch")
 out[typ]=info["name"]
print(json.dumps({"status":"complete","supply":SID,"qty":qty,"docs":out,"currency":"CNY"},ensure_ascii=False))
