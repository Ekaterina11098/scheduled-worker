"""Retry only three preflight-blocked items of the exact human confirmation341."""
import copy
def main():
 from china_loss_execute import IO
 from china_loss_control import PLAN,APPROVAL
 from china_daily_ad_actions import EXEC,process_and_deliver
 io=IO();a=io.get(APPROVAL+'341');p=io.get(PLAN+a['plan_id']);io.validate_owner(a)
 e=io.get(EXEC+p['plan_id']);byid={x['id']:x for x in p['items']}
 assert len(p['items'])==7 and sum(x['amount_cny']for x in p['items'])==2100
 blocked=[s for s in e['items']if s['status']=='blocked']
 assert {byid[s['id']]['campaign_id']for s in blocked}=={41779660}
 assert all(not s.get('steps')and not s.get('request')and not s.get('wb_writes')for s in blocked)
 assert all(s['status']=='verified'for s in e['items']if s not in blocked)
 key='china_agent:owner_budget341_preflight_recovery:2026-11-17:v3'
 assert not io.get(key),'Existing recovery audit; inspect before retry'
 assert io.create(key,dict(status='preflight',original_execution=copy.deepcopy(e),job_id=341,scope=[s['id']for s in blocked]))
 e['preflight_recovery_key']=key;e['items']=[s for s in e['items']if s not in blocked];e['status']='running'
 io.put(EXEC+p['plan_id'],e)
 result=process_and_deliver(io,a,p)
 io.put(key,dict(status=result['status'],job_id=341,verified=sum(s['status']=='verified'for s in result['items']),original_blocked=blocked,execution_key=EXEC+p['plan_id']))
if __name__=='__main__':main()
