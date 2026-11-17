"""Complete the exact saved human confirmation335 after obsolete test recovery."""
import json,os
from china_price_apply import IO,PREFIX,process,notify,validate_approval,day
KEY='china_agent:price_recommendation_approval:v2:-1004342917488:335:5122667182:c78d5975eebd05da8e9a2c4433b021eff05d537c21fe293a95771a19ec1a1e53'
EXPECTED={'1473242762':'259.5','1473242764':'182.5','1473243440':'279.6','1473243827':'229.5','1473243828':'218.5','1473243908':'229.5','1556488187':'95','1556488188':'89.28','1556488194':'92.16'}
def main():
 assert day()=='2026-11-16'and os.environ['GITHUB_REPOSITORY']=='Ekaterina11098/scheduled-worker'and os.environ['GITHUB_REF']=='refs/heads/main'
 io=IO();a=io.get(KEY);validate_approval(KEY,a)
 assert a['actor_user_id']==5122667182 and a['report_job_id']==335 and a['report_message_id']==1057
 assert a['report_sha256']=='86cc10bafa5ac188143084621eef53e164a67fb439e0bf00346888e73a2b130f'
 assert {s['nm_id']:s['target_cny']for s in a['selections']}==EXPECTED and len(a['selections'])==9
 e=process(io,KEY,polls=12)
 notify(io,KEY,e)
 print(json.dumps(dict(status=e['status'],upload_id=e.get('upload_id'),items=[dict(article=x['selection']['article'],status=x['status'],reason=x.get('reason'))for x in e.get('items',[])]),ensure_ascii=False))
if __name__=='__main__':main()

