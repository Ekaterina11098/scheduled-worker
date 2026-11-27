"""Retry only idempotent report-state traffic; never Telegram or marketplace writes."""
import time,json,re
import requests
from china_price_apply import IO

class AdvertisingIO(IO):
    def _large_report(self,key,p):
        allowed=re.fullmatch(r'china_agent:advertising_(?:source|midday_source|artifacts|midday_artifacts):\d{4}-\d{2}-\d{2}:[A-Za-z0-9_-]+',key)
        return bool(allowed) and len(json.dumps(p,ensure_ascii=False,separators=(',',':')).encode('utf-8'))>1000000

    def _report_write(self,key,p,create):
        for attempt in range(3):
            try:
                result=self.db('rpc/china_advertising_report_state_v1','POST',dict(p_key=key,p_payload=p,p_create=create))
                if type(result)is not bool:raise RuntimeError('Report state RPC response invalid')
                if not result and attempt and self.get(key)==p:return True
                return result
            except (requests.Timeout,requests.ConnectionError,RuntimeError) as error:
                transient=isinstance(error,(requests.Timeout,requests.ConnectionError)) or str(error) in {
                    'State HTTP 429','State HTTP 500','State HTTP 502','State HTTP 503','State HTTP 504','State HTTP 520','State HTTP 522','State HTTP 524'}
                if not transient:raise
                # Only scoped, idempotent report state; recover an acknowledged-late commit.
                try:
                    if self.get(key)==p:return True
                except (requests.Timeout,requests.ConnectionError,RuntimeError):pass
                if attempt==2:raise
                time.sleep((2,5)[attempt])

    def _completion(self,key,p):
        if isinstance(p,dict) and p.get('completion_notice'):
            from china_execution_notice import deliver_registered
            deliver_registered(self,key,p)

    def create(self,key,p):
        created=self._report_write(key,p,True) if self._large_report(key,p) else super().create(key,p)
        if created and self._large_report(key,p) and self.get(key)!=p:raise RuntimeError('State readback mismatch')
        if created:self._completion(key,p)
        return created

    def put(self,key,p):
        from urllib.parse import quote
        from datetime import datetime,timezone
        if self._large_report(key,p):
            if not self._report_write(key,p,False):raise RuntimeError('Report state row missing')
        else:
            self.db('telegram_api_cache?cache_key=eq.'+quote(key,safe=''),'PATCH',dict(payload=p,updated_at=datetime.now(timezone.utc).isoformat()),'return=minimal')
        if self.get(key)!=p:raise RuntimeError('State readback mismatch')
        self._completion(key,p)

    def db(self,path,method="GET",body=None,prefer=None):
        self.state_cache_read_timeout=90
        self.state_cache_compact_utf8=True
        safe=method in ('GET','PATCH') and path.startswith('telegram_api_cache?')
        for attempt in range(3):
            try:
                return super().db(path,method,body,prefer)
            except (requests.Timeout,requests.ConnectionError,RuntimeError) as error:
                transient=isinstance(error,(requests.Timeout,requests.ConnectionError)) or str(error) in {
                    "State HTTP 429","State HTTP 500","State HTTP 502","State HTTP 503","State HTTP 504"}
                if not safe or not transient or attempt==2:
                    raise
                time.sleep((2,5)[attempt])

