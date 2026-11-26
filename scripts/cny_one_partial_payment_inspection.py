"""Inspect one private-configured payment chain; MS GET only."""
import sys,traceback
import cny_document_rollout as r
b=r.b;m=b.m
P='one_partial_payment_rate:'
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(b.ROOT+P+'config:v1')
 assert cfg and cfg['mode']=='inspect' and len(cfg['documents'])==5
 docs={typ:r.live(t,typ,[ident])[ident] for typ,ident in cfg['documents'].items()}
 currencies=b.fullrows(t,'entity/currency')
 assert all(b.D(d['sum'])==cfg['expected_sum_minor'] for d in docs.values())
 b.put(db,P+'inspection:v1',{'status':'complete','at':m.now(),'documents':docs,'currencies':currencies,'ms_writes':0})
 print('Selected chain and currencies inspected; private result saved; MS writes zero.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:b.put(m.Cache(b.ReadOnly()),P+'error:v1',{'at':m.now(),'detail':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Inspection stopped; see private journal.');sys.exit(1)
