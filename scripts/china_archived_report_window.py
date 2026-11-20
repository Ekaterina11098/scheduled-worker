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
