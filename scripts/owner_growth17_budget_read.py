"""One exact budget read to finish owner audit; no mutations or Telegram."""
import os,json,requests
from datetime import datetime,timezone
from china_cloud_cost_control import Cache
ROOT='china_agent:owner_growth_audit:2026-11-17:v1'
IDS=[40933588,40945478,40945502,40964981,41055480,41155909,41187173,41270309,41296359,41298169,41325622,41332083,41680341,41680449,41779660,41925305,41967612]
def main():
 c=Cache();assert c.create(ROOT+':budget_read_claim',dict(at=datetime.now(timezone.utc).isoformat(),wb_writes=0))
 r=requests.post('https://advert-api.wildberries.ru/api/advert/v2/budget',headers={'Authorization':os.environ['WB_TOKEN_3']},json=dict(advertIds=IDS),timeout=(10,60));r.raise_for_status();j=r.json();rows=j['adverts']
 assert len(rows)==len(IDS) and {x['advertId']for x in rows}==set(IDS) and all(x['currency']=='CNY'and type(x['total'])in(int,float)and x['total']>=0 for x in rows)
 value=dict(status='complete',cabinet='token_3',observed_at=datetime.now(timezone.utc).isoformat(),rows=rows,wb_writes=0,telegram_calls=0,model_calls=0,grants_action_permission=False)
 c.put(ROOT+':budgets',value);print(json.dumps(dict(status='complete',campaigns=len(rows),wb_writes=0,telegram_calls=0)))
if __name__=='__main__':main()
