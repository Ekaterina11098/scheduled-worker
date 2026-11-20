"""Read exact WB cancellation dates for all current manual candidates. No stock writes or messages."""
import json,time
import tg_agent_new as g
from stock_deploy_support import runtime_db,seal
from stock_operation_store import Store,canonical,Stopped
from stock_execution_fence import cloud_writer
from stock_shared_requests import SharedRequests
ROOT='technical:owner-cancel-trial:2026-11-20:1'
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   s=Store(db,postgres=True);d=json.loads(s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(ROOT,)).fetchone()[0]);db.commit()
   old=json.loads(s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(d['approval']['manual_scope'],)).fetchone()[0]);db.commit()
   arts={r['article'] for p in old.get('manual_packets_v1',[]) if p.get('state')=='confirmed' for r in p.get('rows',[])}
   x={'started':time.time(),'status':'reading','cabinets':{},'errors':[]};d['cancel_dates_audit']=x
   def save():
    with s.transaction():s.sql('UPDATE stock_runs SET snapshot=? WHERE id=?',(canonical(d),ROOT))
   shared=SharedRequests(s);g.STOCK_REQUEST_GATE=shared;g.STOCK_SHARED_ORDERS=shared
   g.check_run_budget=lambda:None;g._CACHE_GET=lambda k:shared.get(k);g._CACHE_SET=lambda k,v,ttl:shared.put(k,v,ttl)
   api=g.api
   def onlyget(method,*args,**kw):
    if method!='GET':raise Stopped('Read-only cancellation date audit')
    return api(method,*args,**kw)
   g.api=onlyget;save()
   for cab,token in enumerate(g.cabinet_tokens()):
    try:
     cursor='2026-11-01';found={};count=0
     for _ in range(20):
      rows=g.api('GET',g.WB_STATS+'/api/v1/supplier/orders',token,params={'dateFrom':cursor,'flag':0},retry_read_network=True)
      if not isinstance(rows,list):raise Stopped('WB statistics orders missing')
      count+=len(rows)
      for r in rows:
       art=g.norm(r.get('supplierArticle'))
       if art in arts and r.get('isCancel') is True:
        key=str(r.get('srid'))
        found[key]={'article':art,'cabinet':cab,**{k:r.get(k) for k in ('srid','date','lastChangeDate','isCancel','cancelDate','warehouseType')}}
      if len(rows)<80000:break
      nxt=rows[-1].get('lastChangeDate')
      if not nxt or nxt==cursor:raise Stopped('WB statistics pagination incomplete')
      cursor=nxt
     else:raise Stopped('WB statistics page bound')
     x['cabinets'][str(cab)]={'complete':True,'observed':time.time(),'scanned':count,'cancelled':list(found.values())};save()
    except Exception as exc:x['errors'].append({'cabinet':cab,'type':type(exc).__name__,'error':str(exc)});save()
   x.update(status='complete' if not x['errors'] else 'partial',completed=time.time());save();seal('manual-cancellation-dates',x)
   print(json.dumps({'status':x['status'],'cabinets':len(x['cabinets']),'stock_writes':0}))
