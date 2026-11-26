"""MS read-only incoming header counts; no cache dependency and no business data output."""
import collections,json
import cny_migration_backup_20261125 as b
m=b.m;t=b.ReadOnly()
cc=b.fullrows(t,'entity/currency');base=next(c for c in cc if c.get('default'))
assert base['isoCode']=='CNY' and b.D(base['rate'])==1
result={}
for typ in ('supply','enter'):
 rows=b.fullrows(t,'entity/'+typ)
 normalized=sum(m.href(d.get('rate',{}).get('currency',{}))==m.href(base) and b.D(d.get('rate',{}).get('value',1))==1 for d in rows)
 result[typ]={'total':len(rows),'base_currency_rate_one':normalized,'remaining':len(rows)-normalized}
print(json.dumps({'read_at':m.now(),'incoming_headers':result,'ms_writes':0},sort_keys=True))
