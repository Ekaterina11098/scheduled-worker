"""Keep pre-window archives out of current report rows without inventing zero statistics."""
from datetime import date,datetime
from zoneinfo import ZoneInfo

def outside_window_without_statistics(campaign, statistics, window_start):
 if statistics is not None or campaign.get('status') != 7:return False
 deleted=(campaign.get('timestamps')or{}).get('deleted')
 if not isinstance(deleted,str):return False
 try:
  moment=datetime.fromisoformat(deleted.replace('Z','+00:00'))
  if moment.tzinfo is None:return False
  return moment.astimezone(ZoneInfo('Europe/Moscow')).date()<date.fromisoformat(window_start)
 except (ValueError,TypeError):return False

def _has_report_activity(metrics):
 if metrics is None:return False
 # Impressions alone on a closed campaign do not create a useful current action row.
 # Keep their counters in totals; never hide money, clicks or attributed orders.
 for key in ('spend','amount','orders','clicks'):
  value=metrics.get(key,0)
  if value is not None and (not isinstance(value,(int,float)) or value!=0):return True
 return False

def _archived_before(row,window_start):
 state=dict(row.get('budget_inventory_state')or{})
 if state.get('id')not in(None,row.get('id')):return False
 state['timestamps']=dict(state.get('timestamps')or{})
 if row.get('status')==7:
  state.setdefault('status',7)
  if row.get('archived_at'):state.setdefault('timestamps',{})['deleted']=row['archived_at']
 return outside_window_without_statistics(state,None,window_start)

def report_view(bundle):
 """Omit inactive pre-window archive rows; financial history remains in the source."""
 days=bundle.get('days')or[]
 if not days:return bundle
 kept=[];omitted=[]
 for row in bundle.get('campaigns',[]):
  if _archived_before(row,days[0]) and not _has_report_activity(row.get('period')) and not _has_report_activity(row.get('last')):
   if any(x.get('action')for x in row.get('focus',[])):raise ValueError('Archived row contains an executable action')
   omitted.append(dict(campaign_id=row['id'],window_start=days[0],reason='inactive_pre_window_archive'));continue
  kept.append(row)
 if not omitted:return bundle
 if not kept:raise ValueError('Archive view would empty report')
 return dict(bundle,campaigns=kept,presentation_omitted_archives=omitted)

def midday_view(bundle):
 """Filter presentation only; retain every known archive counter in the totals."""
 if not bundle.get('day'):return bundle
 kept=[];omitted=[];totals=[]
 for row in bundle.get('campaigns',[]):
  hidden=_archived_before(row,bundle['day']) and not _has_report_activity(row.get('today'))
  if hidden:
   if row.get('attention')or row.get('financial_action'):raise ValueError('Archived row contains an executable action')
   omitted.append(dict(campaign_id=row['id'],window_start=bundle['day'],reason='inactive_pre_window_archive'))
  else:kept.append(row)
  if not hidden or row.get('today')is not None:totals.append(row)
 if not omitted:return bundle
 if not kept:raise ValueError('Archive view would empty report')
 return dict(bundle,campaigns=kept,presentation_omitted_archives=omitted,presentation_totals_campaigns=totals)
