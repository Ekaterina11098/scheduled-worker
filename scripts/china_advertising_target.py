"""Read a dated owner target without granting any execution permission."""
from datetime import date
KEY='china_agent:advertising_target_drr:v1'
def target_pct(bundle=None,source=None):
 for obj in(source or{},bundle or{}):
  v=obj.get('target_drr_pct')
  if type(v)in(int,float)and 0<v<100:return float(v)
 return 5.0
def resolve(io,bundle,source):
 p=io.get(KEY)if io is not None else None
 if isinstance(p,dict)and p.get('status')=='active'and p.get('cabinet')=='token_3'and p.get('source_ref'):
  day=bundle.get('day');start=p.get('effective_from');end=p.get('effective_to')
  if isinstance(day,str)and isinstance(start,str)and date.fromisoformat(start)<=date.fromisoformat(day)and(not end or date.fromisoformat(day)<=date.fromisoformat(end)):
   v=p.get('target_drr_pct')
   if type(v)in(int,float)and 0<v<100:return float(v)
 return target_pct(bundle,source)
