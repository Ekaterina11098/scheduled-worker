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

def report_view(bundle):
 """Do not publish inventory-only rows archived before the displayed period."""
 days=bundle.get('days')or[]
 if not days:return bundle
 kept=[];omitted=[]
 for row in bundle.get('campaigns',[]):
  state=row.get('budget_inventory_state')or{}
  if row.get('period')is None and row.get('last')is None and row.get('status')==7 and state.get('id')==row.get('id') and outside_window_without_statistics(state,None,days[0]):
   omitted.append(dict(campaign_id=row['id'],deleted_at=state['timestamps']['deleted'],window_start=days[0]));continue
  kept.append(row)
 if not omitted:return bundle
 if not kept:raise ValueError('Archive view would empty report')
 return dict(bundle,campaigns=kept,presentation_omitted_archives=omitted)
