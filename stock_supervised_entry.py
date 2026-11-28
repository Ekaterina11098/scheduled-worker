"""Supervise startup errors before the stock journal exists; never writes marketplace stock."""
import os,sys,runpy,time,json
from pathlib import Path
from stock_supervision import resolve_destination,latest_due,notify,remember
def main(target):
    due=latest_due()
    resolve_destination()
    path=Path(target).resolve();sys.path.insert(0,str(path.parent))
    try:
        module=runpy.run_path(str(path),run_name='stock_supervised_target')
        result=module['main']()
    except BaseException as exc:
        kind=type(exc).__name__
        text='Обновление остатков '+due['label']+' не удалось завершить: '+kind+'. Ошибка возникла при старте или выполнении. Контрольный запуск выполнит автоматическую повторную проверку; подтверждённые операции повторно не отправляются.'
        try:receipt=notify(due['scope'],'startup:'+kind,text);print(json.dumps(dict(stock_startup_alert=receipt.get('state'),error_type=kind)),flush=True)
        except Exception as alert_error:print(json.dumps(dict(stock_startup_alert='failed',error_type=type(alert_error).__name__)),flush=True)
        remember(due['scope'],dict(status='startup_failed',error_type=kind))
        raise
    remember(due['scope'],dict(status=result.get('status'),delivery_done=result.get('delivery_done'),execution_complete=result.get('execution_complete'),retry_not_before=result.get('retry_not_before')))
    if result.get('status')=='waiting':
        complete=result.get('execution_complete') is True
        text=('Остатки '+due['label']+' обновлены. Ожидается завершение доставки отчёта или ручных рекомендаций.' if complete else
            'Обновление остатков '+due['label']+' ещё не завершено. Запуск приостановлен; автоматический контроль продолжит его с сохранённого места.')
        receipt=notify(due['scope'],'waiting:'+str(complete),text)
        print(json.dumps(dict(stock_waiting_alert=receipt.get('state'))),flush=True)
    return result
if __name__=='__main__':
    try:main(sys.argv[1])
    except BaseException as exc:
        print(json.dumps(dict(supervised_stock='failed',error_type=type(exc).__name__)),flush=True);raise SystemExit(1)
