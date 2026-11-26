"""Authorized correction of three supply currency references with stock quantity invariants."""
import copy,gzip,json,os,sys,time,traceback,urllib.request,urllib.error
import cny_one_chain_align_test as a
r=a.r;b=a.b;m=a.m;P='gray_umbrella_cost_apply:'
def save(db,k,v):b.put(db,P+k,v)
def inv(old,new):
 a.invariants(old,new)
 assert [r.psig(p) for p in r.rows(old)]==[r.psig(p) for p in r.rows(new)],'Position data or unit prices changed'
 assert b.D(old['sum'])==b.D(new['sum']),'Nominal document sum changed'
def ccstate(cc):return sorted([{k:c.get(k) for k in ('id','isoCode','rate','default','multiplicity','indirect','archived','name')} for c in cc],key=lambda x:x['id'])
def bystore(t):return b.fullrows(t,'report/stock/bystore',{'filter':'stockMode=all'})
def stocks(rows,affected):
 out={}
 for d in rows:
  href=m.href(d).split('?')[0]
  if href in affected:
   assert href not in out
   out[href]={m.href(x).split('?')[0]:r.number(x['stock']) for x in d['stockByStore']}
 assert set(out)==set(affected),'Incomplete affected-product warehouse snapshot'
 return out
def cost(t,cfg):
 rr=b.fullrows(t,'report/stock/all',{'filter':'stockMode=all;quantityMode=all;product='+cfg['product_href']})
 assert len(rr)==1
 return rr[0]
def write_once(db,cfg,bodies):
 assert len(bodies)==3 and {x['id'] for x in bodies}==set(cfg['supplies'])
 assert all(set(x)=={'id','rate','positions'} for x in bodies)
 assert db.claim(b.ROOT+P+'write_intent:v1',{'status':'intended','at':m.now(),'bodies':bodies}),'Existing intent: reconcile before replay'
 headers={'Authorization':'Bearer '+os.environ['MOYSKLAD_API_TOKEN'],'Content-Type':'application/json','Accept':'application/json;charset=utf-8','Accept-Encoding':'gzip'}
 req=urllib.request.Request(m.MS+'entity/supply',data=json.dumps(bodies).encode(),headers=headers,method='POST')
 try:
  with urllib.request.urlopen(req,timeout=120) as resp:
   raw=resp.read()
   if resp.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
   value=json.loads(raw)
  save(db,'write_response:v1',{'at':m.now(),'received':True,'documents':value})
 except urllib.error.HTTPError as e:
  raw=e.read()
  try:
   if e.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
   detail=json.loads(raw)
  except Exception:detail={'http_status':e.code}
  save(db,'write_response:v1',{'at':m.now(),'received':True,'http_status':e.code,'detail':detail})
 except (TimeoutError,urllib.error.URLError):save(db,'write_response:v1',{'at':m.now(),'received':False,'uncertain':True})
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(b.ROOT+P+'config:v1')
 assert cfg and cfg['authorized'] and cfg['scope']=='three_selected_supply_currency_refs_preserve_nominal_prices'
 assert len(cfg['supplies'])==3 and cfg['preserve_all_store_quantities'] and not cfg['outside_ms_changes']
 assert not db.get(b.ROOT+P+'snapshot:v1'),'Existing attempt: reconcile before replay'
 cc=b.fullrows(t,'entity/currency');base=next(x for x in cc if x.get('default'))
 assert base['id']==cfg['base_currency_id'] and base['isoCode']=='CNY' and b.D(base['rate'])==1
 before=r.live(t,'supply',cfg['supplies']);affected=set();bodies=[];goals=copy.deepcopy(before)
 for i,d in before.items():
  inv(cfg['before'][i],d);assert r.signature(cfg['before'][i],'supply')==r.signature(d,'supply'),'Supply changed since inspection'
  assert b.D(d['rate'].get('value',1))==12 and d['applicable'] and not d.get('payments')
  targetrows=[x for x in r.rows(d) if m.href(x['assortment'])==cfg['product_href']]
  assert len(targetrows)==1 and b.D(targetrows[0]['price'])==cfg['target_unit_minor']
  q={'id':i,'rate':{'currency':m.meta(base),'value':1},'positions':[]}
  for p in r.rows(d):
   assert p['assortment']['meta']['type']=='product' and b.D(p['price'])==int(p['price'])
   affected.add(m.href(p['assortment']))
   pp={k:copy.deepcopy(p[k]) for k in r.FIELDS if k in p}
   pp['assortment']=m.meta(p['assortment']);pp['price']=p['price'];q['positions'].append(pp)
  assert len(q['positions'])<=1000
  bodies.append(q);goals[i]['rate']=q['rate']
 po_ids=sorted({m.href(d.get('purchaseOrder',{})).split('/')[-1] for d in before.values() if d.get('purchaseOrder')})
 linked_before=r.live(t,'purchaseorder',po_ids) if po_ids else {}
 wh_before=bystore(t);stock_before=stocks(wh_before,affected);cost_before=cost(t,cfg)
 assert b.D(cost_before['stock'])==cfg['expected_stock']
 save(db,'snapshot:v1',{'at':m.now(),'before':before,'goals':goals,'bodies':bodies,'currencies':cc,'affected_product_hrefs':sorted(affected),'warehouse_stock_before':stock_before,'cost_before':cost_before,'linked_purchaseorders_before':linked_before})
 fresh=r.live(t,'supply',cfg['supplies'])
 for i,d in fresh.items():inv(before[i],d);assert r.signature(before[i],'supply')==r.signature(d,'supply'),'Concurrent document edit'
 assert stocks(bystore(t),affected)==stock_before,'Stock changed before write'
 write_once(db,cfg,bodies)
 after=r.live(t,'supply',cfg['supplies']);save(db,'readback:v1',{'at':m.now(),'documents':after})
 for i,d in after.items():
  inv(before[i],d);assert r.signature(goals[i],'supply')==r.signature(d,'supply'),'Supply target mismatch; stop without replay'
 save(db,'documents_verified:v1',{'status':'verified','at':m.now(),'documents':len(after)})
 wh_after=bystore(t);stock_after=stocks(wh_after,affected)
 save(db,'warehouse_readback:v1',{'at':m.now(),'before':stock_before,'after':stock_after})
 assert stock_after==stock_before,'Warehouse quantities differ after write'
 confirmed=None
 for attempt in range(21):
  current=cost(t,cfg)
  assert b.D(current['stock'])==cfg['expected_stock'],'Target product quantity changed'
  qty=b.D(current['stock']);unit=b.D(current['price'])
  save(db,'cost_progress:v1',{'at':m.now(),'attempt':attempt,'stock':current['stock'],'unit_minor':current['price'],'total_minor':float(qty*unit)})
  if b.R(unit)==cfg['target_unit_minor'] and b.R(qty*unit)==cfg['target_total_minor']:
   confirmed=current;break
  if attempt<20:time.sleep(15)
 assert confirmed is not None,'Cost report has not reached target; no additional mutations or quantity changes performed'
 final_docs=r.live(t,'supply',cfg['supplies']);final_stock=stocks(bystore(t),affected)
 for i,d in final_docs.items():inv(before[i],d);assert r.signature(goals[i],'supply')==r.signature(d,'supply')
 assert final_stock==stock_before,'Final warehouse quantity mismatch'
 assert ccstate(cc)==ccstate(b.fullrows(t,'entity/currency')),'Currency settings changed'
 linked_after=r.live(t,'purchaseorder',po_ids) if po_ids else {}
 for i,d in linked_after.items():assert r.signature(linked_before[i],'purchaseorder')==r.signature(d,'purchaseorder'),'Linked order monetary data changed'
 save(db,'result:v1',{'status':'verified','at':m.now(),'documents':final_docs,'warehouse_stock_before':stock_before,'warehouse_stock_after':final_stock,'affected_products':len(affected),'cost_before':cost_before,'cost_after':confirmed,'target_stock':cfg['expected_stock'],'target_unit_minor':cfg['target_unit_minor'],'target_total_minor':cfg['target_total_minor'],'all_store_quantities_preserved':True,'all_position_prices_quantities_order_preserved':True,'document_nominal_sums_preserved':True,'currency_settings_unchanged':True,'linked_purchaseorders_unchanged':True,'global_counterparty_balance_checked':False,'outside_ms_changes':False})
 print('Selected supply currency references and target stock cost verified; all warehouse quantities preserved.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:save(m.Cache(b.ReadOnly()),'error:v1',{'at':m.now(),'detail':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Selected supply test stopped; inspect private readback before any retry.');sys.exit(1)
