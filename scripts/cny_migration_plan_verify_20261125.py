"""Verify private full backup coverage and create the immutable conversion plan."""
import collections,sys
from decimal import Decimal
import cny_migration_backup_20261125 as b
m=b.m;ROOT=b.ROOT
def main():
 t=b.ReadOnly();db=m.Cache(t);manifest=db.get(ROOT+'backup_manifest:v1')
 assert manifest
 for g in ('orders','shipments','other'):
  result=db.get(ROOT+'backup_result:'+g)
  if not result or result['status']!='complete':raise m.Stop('Full baseline partition not yet complete')
 assert db.get(ROOT+'backup_extra_result:v1')['status']=='complete'
 stats=[];currency_ids={m.href(x) for x in manifest['currencies']}
 all_types=[(x['type'],x['count'],False) for x in manifest['counts']]+[('inventory',db.get(ROOT+'scope_extra:inventory')['count'],True)]
 for typ,count,extra in all_types:
  ids=set();positions=0;oldtotal=Decimal(0);targettotal=Decimal(0);actualtotal=Decimal(0);adjustments=0;deviations=0;missing=[]
  for offset in range(0,count,100):
   part=db.get(ROOT+('backup_extra:'+typ+':'+str(offset) if extra else 'backup:'+typ+':page:'+str(offset)))
   assert part and part['status']=='complete'
   docs=part['rows'] if extra else part['documents']
   assert part['sha256']==b.digest(docs)
   plans=[]
   for d in docs:
    assert d['id'] not in ids;ids.add(d['id'])
    pp=d.get('positions',{}).get('rows',[]) if isinstance(d.get('positions'),dict) else []
    if isinstance(d.get('positions'),dict):assert len(pp)==d['positions']['meta']['size']
    if isinstance(d.get('rate'),dict):
     assert m.href(d['rate'].get('currency',{})) in currency_ids
     assert b.D(d['rate'].get('value',1))==1
    if typ=='salesreturn':assert isinstance(d.get('demand'),dict),'Unbased return requires explicit cost conversion'
    p=b.plan(d,pp)
    assert len(p['price_minor'])==len(pp)
    positions+=len(pp);oldtotal+=b.D(d.get('sum'));targettotal+=b.D(p['target_minor']);actualtotal+=b.D(p['actual_minor'])
    adjustments+=p['adjusted_index']>=0;deviations+=b.D(p['deviation_minor'])!=0
    plans.append({'id':d['id'],'name':d.get('name'),'type':typ,'source_updated':d.get('updated'),**p})
   b.put(db,'verified_plan:'+typ+':page:'+str(offset),{'status':'complete','source_sha256':part['sha256'],'records':plans,'at':m.now()})
  assert len(ids)==count
  stats.append({'type':typ,'documents':count,'positions':positions,'source_minor':str(oldtotal),'target_minor':str(targettotal),'planned_minor':str(actualtotal),'adjusted_documents':adjustments,'deviation_documents':deviations})
 for typ in ('product','bundle','variant','service'):
  count=manifest['auxiliary'][typ]['count'];ids=set()
  for offset in range(0,count,100):
   part=db.get(ROOT+'backup_aux:'+typ+':'+str(offset));assert part['sha256']==b.digest(part['rows'])
   for item in part['rows']:
    assert item['id'] not in ids;ids.add(item['id'])
    for price in [item[k] for k in ('buyPrice','minPrice') if k in item]+item.get('salePrices',[]):
     assert m.href(price.get('currency',{})) in currency_ids
  assert len(ids)==count
 proof=db.get(ROOT+'batch_read_proof:v1');assert proof and proof['exact_ids'] and proof['positions_complete']
 result={'status':'complete','document_types':stats,'at':m.now(),'ms_writes':0,'extra_inventories_included':True,'rounding_policy':'adjust_one_existing_unit_price_to_nearest_reachable_document_total'}
 b.put(db,'verified_plan:v1',result)
 print('Full source coverage and nearest reachable totals verified privately. No MS mutations.')
if __name__=='__main__':main()
