"""Read private checkpoint status without MS requests or operational data output."""
import json
import cny_incoming_refs_apply as x
b=x.b;m=x.m
t=b.ReadOnly();db=m.Cache(t)
p=db.get(b.ROOT+x.P+'apply_progress:v1') or {}
v=db.get(b.ROOT+x.P+'result:v1') or {}
e=db.get(b.ROOT+x.P+'error:apply:v1') or {}
print(json.dumps({'progress_at':p.get('at'),'verified_documents':p.get('verified'),'counts':p.get('counts'),'result_status':v.get('status'),'result_at':v.get('at'),'written':v.get('written'),'already_correct':v.get('already_correct'),'quantities_preserved':v.get('all_store_quantities_preserved'),'prices_rows_order_preserved':v.get('all_prices_rows_order_preserved'),'last_error_at':e.get('at')},sort_keys=True))
