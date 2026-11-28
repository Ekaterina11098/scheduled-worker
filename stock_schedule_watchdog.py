"""Independent schedule watchdog; dispatches the existing idempotent stock worker only."""
import os,json,time
from datetime import datetime,timezone
from urllib import request
from stock_supervision import latest_due,resolve_destination,notify,load_cache,save_cache
BASE='https://api.github.com/repos/Ekaterina11098/scheduled-worker'
WORKFLOW='stock-daily-1630-prepared.yml'
def github(path,method='GET',payload=None):
    body=None if payload is None else json.dumps(payload).encode()
    req=request.Request(BASE+path,data=body,method=method,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','Content-Type':'application/json'})
    with request.urlopen(req,timeout=25) as r:return json.load(r) if r.status!=204 else {}
def stamp(value):return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()
def evaluate(due,status,runs,now):
    if now-due['opened_at']<900:return dict(action='wait',reason='opening_grace')
    if status and status.get('scope')==due['scope'] and (status.get('status')=='done' or (status.get('execution_complete') is True and status.get('delivery_done') is True)):
        return dict(action='healthy',reason='execution_and_report_confirmed')
    current=[r for r in runs if stamp(r['created_at'])>=due['opened_at']]
    if any(r['status'] in ('queued','pending','in_progress','waiting','requested') and now-stamp(r['created_at'])<75*60 for r in current):
        return dict(action='running',reason='existing_worker_active')
    if status and status.get('scope')==due['scope'] and status.get('retry_not_before',0) and status['retry_not_before']>now:
        return dict(action='wait',reason='provider_cooldown',until=status['retry_not_before'])
    if current and now-max(stamp(r['created_at']) for r in current)<600:return dict(action='wait',reason='bounded_retry_interval')
    return dict(action='dispatch',reason='missing_start' if not current else 'unfinished_or_failed')
def read_status(scope):
    import psycopg
    from stock_deploy_support import HOST,ROLE,PROJECT,password
    with psycopg.connect(host=HOST,port=5432,dbname='postgres',user=ROLE+'.'+PROJECT,password=password(),sslmode='require',connect_timeout=5,
        options='-c search_path=stock_execution,pg_catalog -c statement_timeout=8000') as db:
        key='technical:stock-status:v1:'+scope.removeprefix('technical:stock-daily:')
        row=db.execute('SELECT snapshot FROM stock_runs WHERE id=%s',(key,)).fetchone()
        return json.loads(row[0]) if row else None
def main():
    now=time.time();due=latest_due();state=github('/actions/workflows/'+WORKFLOW)
    runs=github('/actions/workflows/'+WORKFLOW+'/runs?per_page=50')['workflow_runs']
    cached=load_cache();status=None
    try:status=read_status(due['scope'])
    except Exception as exc:
        print(json.dumps(dict(watchdog_database_status=type(exc).__name__)),flush=True)
        last=cached.get('last_result',{})
        if last.get('scope')==due['scope']:status=last
    decision=evaluate(due,status,runs,now)
    print(json.dumps(dict(stock_watchdog=decision,scope=due['scope'],workflow_state=state['state'])),flush=True)
    if decision['action'] in ('healthy','running','wait'):return decision
    resolve_destination()
    if state['state']!='active':
        notify(due['scope'],'schedule_disabled','Обновление остатков '+due['label']+' не запущено: расписание GitHub отключено. Нужна проверка планировщика.')
        return dict(action='blocked',reason='workflow_disabled')
    cached=load_cache();last=cached.get('last_dispatch',{})
    if last.get('scope')==due['scope'] and now-last.get('at',0)<600:return dict(action='wait',reason='dispatch_already_requested')
    text=('Пропущен запуск обновления остатков '+due['label']+'. Контроль обнаружил пропуск и запускает восстановление.' if decision['reason']=='missing_start' else
        'Обновление остатков '+due['label']+' ещё не завершено. Контроль запускает продолжение с сохранённого места; подтверждённые записи повторяться не будут.')
    receipt=notify(due['scope'],'watchdog:'+decision['reason'],text)
    cached=load_cache();cached['last_dispatch']=dict(scope=due['scope'],at=now,state='claimed');save_cache(cached)
    try:github('/actions/workflows/'+WORKFLOW+'/dispatches','POST',dict(ref='main',inputs=dict(slot=due['slot'])))
    except Exception:
        cached['last_dispatch']['state']='uncertain';save_cache(cached);raise
    cached['last_dispatch']['state']='requested';save_cache(cached)
    print(json.dumps(dict(stock_recovery_dispatch='requested',scope=due['scope'],alert=receipt.get('state'))),flush=True)
    return decision
if __name__=='__main__':
    from stock_supervision import run_cli
    run_cli(main)
