"""Requested read-only funding/composition supplement. No Telegram or WB mutations."""
import json,runpy,tempfile
from pathlib import Path
from china_codex_cloud import DB
ROOT='ooo_agent:funding_review:2026-11-26'
def main():
 db=DB();request=db.get(ROOT+':request')or{}
 if request.get('status')!='approved_read_only'or request.get('cabinet')!='token_1':raise PermissionError('Exact read-only request required')
 cid=request['cid'];source=request['source_key'];target=ROOT+':evidence'
 if type(cid)is not int or source!='ooo_agent:morning:2026-11-26:evidence':raise PermissionError('Scope mismatch')
 base=db.get(source)or{}
 if base.get('status')!='finished':raise RuntimeError('Complete dated evidence required')
 assets=json.loads(Path(__file__).with_name('ooo_report_templates.json').read_text())
 code=assets['collector'];old=next(l for l in code.splitlines()if l.startswith('IDS='))
 code=code.replace(old,'IDS='+repr([cid])).replace("KEY='ooo_agent:morning:2026-11-12:evidence'",'KEY='+repr(target))
 line=next(l for l in code.splitlines()if 'ids=sorted(set(IDS)|'in l)
 code=code.replace(line,'   ids=list(IDS)')
 code=code.replace(';db.once(KEY,state)',";state['sources']=json.loads(json.dumps(db.get("+repr(source)+")[\"sources\"]));state['sources'].pop('configurations',None);state['sources'].pop('budgets',None);db.once(KEY,state)")
 code=code.replace(" def read(label,fn):\n  try:"," def read(label,fn):\n  if state['sources'].get(label,{}).get('status')=='complete':return\n  try:")
 code=code.replace("  state.update(status='finished'", "  read('focused_live',lambda:raw('advert-api.wildberries.ru','/adv/v3/fullstats',params={'ids':str(IDS[0]),'beginDate':'2026-11-26','endDate':'2026-11-26'}))\n  state.update(status='finished'")
 with tempfile.TemporaryDirectory()as tmp:
  path=Path(tmp)/'read.py';path.write_text(code,encoding='utf-8');runpy.run_path(str(path),run_name='__main__')
 result=db.get(target)or{}
 if result.get('status')!='finished'or any(v.get('status')!='complete'for v in result.get('sources',{}).values()):raise RuntimeError('Read incomplete; private evidence retained')
 print('Actual campaign configuration, budget and current statistics saved privately; no mutations or delivery')
if __name__=='__main__':main()
