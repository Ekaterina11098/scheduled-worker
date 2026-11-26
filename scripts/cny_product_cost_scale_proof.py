"""Read-only evidence tying one incoming document rate to stock cost scale."""
import sys,traceback
import cny_document_rollout as r
b=r.b;m=b.m;P='product_cost_currency_audit:'
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(b.ROOT+P+'proof_config:v1');assert cfg and cfg['mode']=='read_only'
 assert cfg['document_type']=='supply'
 d=r.live(t,'supply',[cfg['document_id']])[cfg['document_id']]
 pp=[p for p in r.rows(d) if m.href(p['assortment'])==cfg['product_href']];assert len(pp)==1
 stock=b.fullrows(t,'report/stock/all',{'filter':'stockMode=all;quantityMode=all;product='+cfg['product_href']})
 result={'status':'complete','at':m.now(),'document_id':d['id'],'document_name':d['name'],'document_sum_minor':d['sum'],'document_rate':d['rate'],'baseline_unit_minor':cfg['baseline_unit_minor'],'current_unit_minor':pp[0]['price'],'quantity':pp[0]['quantity'],'effective_base_unit_minor':float(b.D(pp[0]['price'])*b.D(d['rate'].get('value',1))),'stock_rows':stock,'ms_writes':0}
 b.put(db,P+'proof_result:v1',result)
 print('Read-only cost scaling evidence saved privately; MS writes zero.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:b.put(m.Cache(b.ReadOnly()),P+'proof_error:v1',{'at':m.now(),'detail':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Read-only proof stopped; inspect private diagnostics.');sys.exit(1)
