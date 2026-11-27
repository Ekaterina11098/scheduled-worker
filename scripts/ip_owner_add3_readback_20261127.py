"""Read-only diagnosis of three accepted additions after definite bid400. No PATCH."""
import sys,json,time,requests
sys.path.insert(0,'scripts')
from owner_ad_tests23 import State,ReadWB,stamp
from ip_owner_add3_20261127 import Run,ROOT,project
db=State();prior=db.get(ROOT+':execution')or{};key=ROOT+':readback:v2'
if db.get(key):raise SystemExit('Existing readback retained')
if prior.get('writes',{}).get('membership',{}).get('status')!='accepted'or prior.get('writes',{}).get('bids',{}).get('status')!='rejected'or prior['writes']['bids'].get('http')!=400:raise PermissionError('Exact accepted membership / definite bid rejection required')
t=Run.__new__(Run);t.db=db;t.a=db.get(ROOT+':approval');t.wb=ReadWB(db,'token_2');t.deadline=time.time()+7200;t.s=dict(status='readback_pending',writes={},wb_write_attempts=0,started_at=stamp());t.save=lambda:db.put(key,t.s)
if not db.put(key,t.s,once=True):raise SystemExit('Readback already claimed')
try:
 t.guard();t.wb.identity();ids=sorted(map(int,prior['before']));after=t.configs(ids);t.s.update(after=after,readback_at=stamp());t.save()
 # V2 reports search-only placements while all existing bids are recommendations,
 # and the bid endpoint rejects search. V3 is needed for a field-level diagnosis,
 # only AFTER honoring the original V2 endpoint cooldown (not a rate-limit bypass).
 r=requests.get('https://advert-api.wildberries.ru/api/advert/v3/adverts',headers={'Authorization':t.wb.token},params={'advertIds':'42197035,42215760'},timeout=(10,70),allow_redirects=False)
 try:data=r.json()
 except ValueError:data={'unparseable':True}
 t.s.update(v3_http=r.status_code,v3=data,v3_read_at=stamp(),status='readback_complete');t.save()
except Exception as e:t.s.update(status='attention',error=str(e)if isinstance(e,(ValueError,RuntimeError,PermissionError))else type(e).__name__);t.save()
t.s['finished_at']=stamp();t.save();print(json.dumps({k:t.s.get(k)for k in('status','error','v3_http','wb_write_attempts')}))
if t.s['status']!='readback_complete':raise SystemExit(1)
