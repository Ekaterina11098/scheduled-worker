"""OOO-only configuration reuse, guarded by current WB change markers.

This stores no statistics and never substitutes missing observations with zero.
Callers must verify token_1 seller identity before using this module.
"""
import copy,datetime,time
ROOT='ooo_agent:wb_configs:v1:token_1:'
MAX_AGE=24*3600
def seconds(value):
 try:return datetime.datetime.fromisoformat(str(value).replace('Z','+00:00')).timestamp()
 except (ValueError,TypeError):return None
def put(db,key,value):
 if db.get(key)is None:db.once(key,value)
 else:db.update(key,value)
def remember(db,rows,observed_at=None):
 at=observed_at or datetime.datetime.now(datetime.timezone.utc).isoformat()
 for cfg in rows:
  if type(cfg.get('id'))is not int or cfg.get('currency')!='KGS'or not isinstance(cfg.get('nm_settings'),list):raise ValueError('Invalid OOO config cache entry')
  put(db,ROOT+str(cfg['id']),{'status':'verified_read','observed_at':at,'configuration':copy.deepcopy(cfg)})
def invalidate(db,ids):
 at=datetime.datetime.now(datetime.timezone.utc).isoformat()
 for cid in ids:put(db,ROOT+str(cid),{'status':'dirty','invalidated_at':at})
def statuses(counts):
 return {str(row['advertId']):{'status':group['status'],'changeTime':row.get('changeTime')}for group in counts.get('adverts',[])for row in group.get('advert_list',[])}
def reusable(entry,meta,now=None):
 if not entry or entry.get('status')!='verified_read'or not meta:return False
 cfg=entry.get('configuration',{});seen=seconds(entry.get('observed_at'));changed=seconds(meta.get('changeTime'));updated=seconds(cfg.get('timestamps',{}).get('updated'))
 return (seen is not None and changed is not None and updated is not None and 0<=(now if now is not None else time.time())-seen<=MAX_AGE and seen>=changed and updated>=changed and cfg.get('currency')=='KGS'and cfg.get('status')==meta.get('status')and isinstance(cfg.get('nm_settings'),list)and bool(cfg.get('settings',{}).get('name')))
def resolve(db,ids,current,fetch,now=None):
 ids=sorted(set(map(int,ids)));out={};missing=[]
 for cid in ids:
  entry=db.get(ROOT+str(cid))
  if reusable(entry,current.get(str(cid)),now):out[str(cid)]=copy.deepcopy(entry['configuration'])
  else:missing.append(cid)
 for start in range(0,len(missing),50):
  batch=missing[start:start+50];rows=fetch(batch)
  if len(rows)!=len(batch)or{r.get('id')for r in rows}!=set(batch)or any(r.get('currency')!='KGS'for r in rows):raise RuntimeError('Configuration cache refresh coverage/currency incomplete')
  remember(db,rows)
  out.update({str(r['id']):r for r in rows})
 if set(out)!=set(map(str,ids)):raise RuntimeError('Configuration coverage incomplete')
 return out
