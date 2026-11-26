"""Readback-based campaign composition history; analytical cache writes only."""
import collections,datetime,hashlib,json
ROOT='ooo_agent:campaign_composition:v1:'
MSK=datetime.timezone(datetime.timedelta(hours=3))
FIELDS=('sum','sum_price','orders','clicks','views')

def signature(cfg):
 value={'currency':cfg.get('currency'),'bid_type':cfg.get('bid_type'),'placements':cfg.get('settings',{}).get('placements'),
        'members':sorted(({'nm':n['nm_id'],'bids':n.get('bids_kopecks',{})}for n in cfg.get('nm_settings',[])),key=lambda n:n['nm'])}
 return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def observe(previous,cfg,observed_at):
 """Reordering, name edits and pauses must not look like SKU/bid changes."""
 members=sorted(n['nm_id']for n in cfg.get('nm_settings',[]));fingerprint=signature(cfg)
 if previous and previous.get('fingerprint')==fingerprint:
  return dict(previous,last_seen_at=observed_at)
 old=set((previous or{}).get('members',[]));new=set(members)
 return {'fingerprint':fingerprint,'members':members,'first_seen_at':observed_at,'last_seen_at':observed_at,
         'changed_observed_at':observed_at if previous else None,'removed':sorted(old-new)if previous else[],
         'added':sorted(new-old)if previous else[],'previous_fingerprint':(previous or{}).get('fingerprint'),
         'basis':'difference_between_successful_configuration_readbacks; observation is not exact mutation time'}

def context(db,configs,observed_at,evidence,day,persist=False):
 result={};cache={}
 # Read a dated previous configuration when upgrading an existing installation.
 previous_day=(datetime.date.fromisoformat(day)-datetime.timedelta(days=1)).isoformat()
 previous_evidence=db.get('ooo_agent:morning:'+previous_day+':evidence')or{}
 historical=previous_evidence.get('sources',{}).get('configurations',{})
 for cid,cfg in configs.items():
  if cfg.get('status')==7:continue
  key=ROOT+str(cid);old=db.get(key)
  if not old and str(cid)in historical.get('data',{}):old=observe(None,historical['data'][str(cid)],historical.get('observed_at',observed_at))
  value=observe(old,cfg,observed_at);result[str(cid)]=value
  if persist:
   db.update(key,value)if db.get(key)else db.once(key,value)
 return result

def retained_projection(cid,cfg,evidence,day):
 """Historical SKU subset only. Never label it actual performance after cleanup."""
 members={n['nm_id']for n in cfg.get('nm_settings',[])};end=datetime.date.fromisoformat(day)-datetime.timedelta(days=1)
 start=end-datetime.timedelta(days=13);total=collections.Counter();by_day={}
 for campaign in evidence['sources']['advertising14']['data']:
  if campaign['advertId']!=int(cid):continue
  for d in campaign.get('days',[]):
   dt=d['date'][:10]
   if not str(start)<=dt<=str(end):continue
   values=collections.Counter()
   for app in d.get('apps',[]):
    for n in app.get('nms',[]):
     if n['nmId']in members:values.update({k:n.get(k,0)for k in FIELDS})
   by_day[dt]=dict(values);total.update(values)
 return {'basis':'historical_attribution_to_current_members_not_post_cleanup_effect','period':[str(start),str(end)],
         'totals':dict(total),'by_day':by_day,'drr':total['sum']/total['sum_price']*100 if total['sum_price']>0 else None}

def funding_assessment(evaluate,cid,cfg,campaign,balance,rows,missing,evidence,day,composition):
 projection=retained_projection(cid,cfg,evidence,day)
 metadata={'composition':composition,'retained_historical_projection':projection,'funding_basis':'current_native_campaign'}
 base=evaluate(cid,cfg,campaign,balance,rows,missing)
 if base['decision']in('owner_hold','ineligible_campaign_status'):return dict(base,**metadata)
 changed=(composition or{}).get('changed_observed_at')
 if changed:
  first=(datetime.datetime.fromisoformat(changed).astimezone(MSK).date()+datetime.timedelta(days=1)).isoformat()
  end=(datetime.date.fromisoformat(day)-datetime.timedelta(days=1)).isoformat()
  returned=next((c for c in evidence['sources']['advertising14']['data']if c['advertId']==int(cid)),{})
  by_day={d['date'][:10]:d for d in returned.get('days',[])if first<=d['date'][:10]<=end}
  metadata.update(funding_basis='native_full_days_after_observed_composition_change',first_full_day=first)
  if first>end or end not in by_day:
   result=base
   result.update(decision='awaiting_post_cleanup_statistics',amount_kgs=None,pre_cleanup_decision=result['decision'],day_drr=None,three_drr=None)
   return dict(result,**metadata)
  period=[(datetime.date.fromisoformat(end)-datetime.timedelta(days=i)).isoformat()for i in (2,1,0)]
  required=[d for d in period if d>=first];missing=[d for d in required if d not in by_day]
  post={'day':{k:by_day[end].get(k,0)for k in FIELDS},'three':{k:sum(by_day[d].get(k,0)for d in required if d in by_day)for k in FIELDS}}
  metadata.update(post_cleanup_metrics=post,post_cleanup_full_days=len(required))
  return dict(evaluate(cid,cfg,post,balance,rows,missing),**metadata)
 return dict(base,**metadata)
