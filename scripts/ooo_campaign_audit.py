"""One requested read-only configuration supplement; no Telegram or WB mutations."""
import datetime,json,os,runpy,tempfile
from pathlib import Path
from china_codex_cloud import DB

def main():
 day='2026-11-24' # Exact requested dated evidence; never collect another day implicitly.
 original='ooo_agent:morning:'+day+':evidence'
 target='ooo_agent:campaign_review:'+day+':evidence'
 db=DB();e=db.get(original)or{}
 if e.get('status')!='finished':raise RuntimeError('Completed dated morning evidence required')
 t=json.loads((Path(__file__).parent/'ooo_report_templates.json').read_text())
 c=t['collector'].replace("KEY='ooo_agent:morning:2026-11-12:evidence'",'KEY='+repr(target))
 # Reuse dated catalogue, stock, buyouts/funnel and fullstats; read ONLY missing settings/budgets.
 c=c.replace(";db.once(KEY,state)",";state['sources']=json.loads(json.dumps(db.get("+repr(original)+")[\"sources\"]));state['sources'].pop('configurations',None);state['sources'].pop('budgets',None);db.once(KEY,state)")
 c=c.replace(" def read(label,fn):\n  try:"," def read(label,fn):\n  if state['sources'].get(label,{}).get('status')=='complete':return\n  try:")
 with tempfile.TemporaryDirectory()as temp:
  path=Path(temp)/'read.py';path.write_text(c,encoding='utf-8');runpy.run_path(str(path),run_name='__main__')
 result=db.get(target)or{}
 if result.get('status')!='finished'or any(v.get('status')!='complete'for v in result.get('sources',{}).values()):raise RuntimeError('Read-only supplement incomplete; retained privately')
 print('Read-only supplement saved privately; no writes or Telegram calls')
if __name__=='__main__':main()
