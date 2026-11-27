"""Reconcile a timed-out batch; normalize only the twenty confirmed outstanding references."""
import copy,datetime,gzip,json,os,sys,time,traceback,urllib.request,urllib.error
import cny_all_remaining_refs_apply as a
p=a.p;h=a.h;r=a.r;b=a.b;m=a.m
Q='twenty_order_reference_reconcile:'
def save(db,k,v):p.save(db,Q+k,v)
def put_one(db,i,body):
 assert set(body)<={'rate','positions','overhead'} and 'rate' in body
 assert db.claim(b.ROOT+p.P+Q+'intent:'+i,{'at':m.now(),'id':i,'body':body}),'Existing recovery intent: read back without replay'
 headers={'Authorization':'Bearer '+os.environ['MOYSKLAD_API_TOKEN'],'Content-Type':'application/json','Accept':'application/json;charset=utf-8','Accept-Encoding':'gzip'}
 req=urllib.request.Request(m.MS+'entity/customerorder/'+i,data=json.dumps(body).encode(),headers=headers,method='PUT')
 try:
  with urllib.request.urlopen(req,timeout=90) as response:
   raw=response.read()
   if response.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
   result=json.loads(raw)
  save(db,'response:'+i,{'at':m.now(),'received':True,'document':result})
 except urllib.error.HTTPError as e:
  raw=e.read()
  try:
   if e.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
   detail=json.loads(raw)
  except Exception:detail={'http_status':e.code}
  save(db,'response:'+i,{'at':m.now(),'http_status':e.code,'detail':detail})
 except (TimeoutError,urllib.error.URLError):save(db,'response:'+i,{'at':m.now(),'uncertain':True})
def main():
 t=b.ReadOnly();db=m.Cache(t);auth=db.get(b.ROOT+p.P+'authorization:v1')
 assert auth and auth['authorized'] and auth['scope']=='remaining_ms_currency_references_only' and auth['preserve_prices_sums_quantities_rows_stores_documents'] and not auth['outside_ms_changes']
 key='apply:customerorder:4120';snap=db.get(b.ROOT+p.P+key+':snapshot');last=db.get(b.ROOT+p.P+key+':readback');response=db.get(b.ROOT+p.P+key+':response')
 assert response['uncertain'] and len(snap['before'])==100
 elapsed=datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(response['at'])
 assert elapsed.total_seconds()>600,'Allow prior request to settle before explicit reconciliation'
 pending=[i for i,d in last['documents'].items() if a.signature(d,'customerorder')!=a.signature(snap['goals'][i],'customerorder')]
 assert len(pending)==20
 before=r.live(t,'customerorder',list(snap['before']))
 for i,d in before.items():
  a.invariant(snap['before'][i],d,'customerorder')
  assert a.signature(d,'customerorder') in (a.signature(snap['before'][i],'customerorder'),a.signature(snap['goals'][i],'customerorder'))
  if i not in pending:assert a.signature(d,'customerorder')==a.signature(snap['goals'][i],'customerorder')
 initial=db.get(b.ROOT+p.P+'reconciled_start:v1') or db.get(b.ROOT+p.P+'start:v1')
 cc=b.fullrows(t,'entity/currency');assert h.h.ccstate(cc)==h.h.ccstate(initial['currencies'])
 base=next(c for c in cc if c.get('default'));assert base['isoCode']=='CNY' and b.D(base['rate'])==1
 wh=h.warehouse(t);assert wh==initial['warehouse_quantities']
 demand_ids=sorted({m.href(x).split('?')[0].split('/')[-1] for i in pending for x in before[i].get('demands',[])})
 linked=r.live(t,'demand',demand_ids) if demand_ids else {}
 save(db,'snapshot:v1',{'at':m.now(),'pending_ids':pending,'before':before,'linked_demands':linked,'warehouse':wh,'currencies':cc,'prior_batch_key':key,'prior_request_elapsed_seconds':elapsed.total_seconds()})
 written=0
 for i in pending:
  fresh=r.live(t,'customerorder',[i])[i];a.invariant(snap['before'][i],fresh,'customerorder')
  if a.signature(fresh,'customerorder')==a.signature(snap['goals'][i],'customerorder'):continue
  assert a.signature(fresh,'customerorder')==a.signature(snap['before'][i],'customerorder')
  q=a.body(fresh,base,'customerorder');q.pop('id')
  if not db.get(b.ROOT+p.P+Q+'intent:'+i):put_one(db,i,q);written+=1
  for attempt in range(13):
   z=r.live(t,'customerorder',[i])[i]
   if a.signature(z,'customerorder')==a.signature(snap['goals'][i],'customerorder'):break
   if attempt<12:time.sleep(10)
  save(db,'readback:'+i,{'at':m.now(),'document':z})
  a.invariant(snap['before'][i],z,'customerorder')
  assert a.signature(z,'customerorder')==a.signature(snap['goals'][i],'customerorder'),'Single-document result not confirmed'
 after=r.live(t,'customerorder',list(snap['before']))
 for i,d in after.items():
  a.invariant(snap['before'][i],d,'customerorder');assert a.signature(d,'customerorder')==a.signature(snap['goals'][i],'customerorder')
 if linked:
  linked_after=r.live(t,'demand',list(linked))
  for i,d in linked_after.items():
   a.invariant(linked[i],d,'demand');assert a.signature(linked[i],'demand')==a.signature(d,'demand')
 assert h.warehouse(t)==wh
 assert h.h.ccstate(b.fullrows(t,'entity/currency'))==h.h.ccstate(cc)
 save(db,'final_readback:v1',{'at':m.now(),'documents':after})
 p.save(db,key+':verified',{'at':m.now(),'count':len(after),'reconciled':True,'twenty_outstanding_references_verified':True,'prices_sums_quantities_rows_stores_links_preserved':True})
 save(db,'result:v1',{'status':'verified','at':m.now(),'written':written,'resolved_ids':pending,'batch_documents_verified':len(after),'documents':[{'id':i,'name':after[i]['name'],'sum_minor':after[i]['sum'],'rate':after[i]['rate']} for i in pending],'all_store_quantities_preserved':True,'all_prices_sums_rows_links_preserved':True,'outside_ms_changes':False})
 print('Outstanding references reconciled individually; all original batch documents verified.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:save(m.Cache(b.ReadOnly()),'error:v1',{'at':m.now(),'reason':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Single-document reconciliation stopped; inspect private readback.');sys.exit(1)
