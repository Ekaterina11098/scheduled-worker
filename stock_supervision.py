"""Verified encrypted stock notice cache and database-independent failure delivery."""
import os,json,time,hashlib,hmac,base64
from pathlib import Path
from datetime import datetime,timedelta,timezone
from urllib import request,error
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
AAD=b'veschi-stock-supervision-v1'
MSK=timezone(timedelta(hours=3))
def cache_path():return Path(os.environ.get('STOCK_SUPERVISION_CACHE_DIR',os.environ.get('RUNNER_TEMP','.')))/'state.aes.json'
def cache_key():return hmac.new(os.environ['SUPABASE_SECRET_KEY'].encode(),AAD,hashlib.sha256).digest()
def load_cache():
    p=cache_path()
    if not p.exists():return {}
    envelope=json.loads(p.read_text())
    return json.loads(AESGCM(cache_key()).decrypt(base64.b64decode(envelope['nonce']),base64.b64decode(envelope['ciphertext']),AAD))
def save_cache(value):
    p=cache_path();p.parent.mkdir(parents=True,exist_ok=True)
    nonce=os.urandom(12);raw=json.dumps(value,ensure_ascii=False,sort_keys=True).encode()
    v=dict(nonce=base64.b64encode(nonce).decode(),ciphertext=base64.b64encode(AESGCM(cache_key()).encrypt(nonce,raw,AAD)).decode())
    tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(v));os.replace(tmp,p)
def resolve_destination():
    import psycopg
    cached=load_cache()
    password=hmac.new(os.environ['SUPABASE_SECRET_KEY'].encode(),b'veschi:review-approval-login:20261015:v1',hashlib.sha256).hexdigest()
    try:
        with psycopg.connect(host='aws-0-eu-central-1.pooler.supabase.com',port=5432,dbname='postgres',
            user='review_approval_login_20261015.abxgjoqlddhtcmjcjwxw',password=password,sslmode='require',connect_timeout=5,
            options='-c statement_timeout=10000') as db:
            row=db.execute("SELECT payload FROM review_approval.source_cache WHERE cache_key='reviews:content-group:v1'").fetchone()
    except (psycopg.Error,OSError):
        dest=cached.get('destination',{})
        if dest.get('verified') is not True or not 0<=time.time()-dest.get('verified_at',0)<=7*86400:raise RuntimeError('Verified report destination unavailable')
    else:
        if not row or row[0].get('enabled') is not True or row[0].get('destination_verified') is not True:
            raise RuntimeError('Verified content group is required; private delivery forbidden')
        dest=dict(chat_id=str(row[0]['chat_id']),verified=True,verified_at=time.time())
        if not dest['chat_id'].startswith('-'):raise RuntimeError('Verified stock group required')
        cached['destination']=dest;save_cache(cached)
    os.environ['TELEGRAM_ALLOWED_CHAT_ID']=str(dest['chat_id'])
    os.environ['STOCK_REPORT_DESTINATION_VERIFIED']='true'
    return dest['chat_id']
def latest_due(now=None):
    local=(now or datetime.now(timezone.utc)).astimezone(MSK)
    day=local.date()
    if local.hour>=20:hour=20;slot='1630';suffix=''
    elif local.hour>=5:hour=5;slot='0700';suffix=':0700'
    else:day-=timedelta(days=1);hour=20;slot='1630';suffix=''
    opened=datetime.combine(day,datetime.min.time(),MSK).replace(hour=hour)
    return dict(slot=slot,scope='technical:stock-daily:'+day.isoformat()+suffix,opened_at=opened.timestamp(),
        label=day.strftime('%d.%m')+' '+str(hour).zfill(2)+':00 МСК')
def notify(scope,kind,text,sender=None):
    if os.getenv('STOCK_REPORT_DESTINATION_VERIFIED')!='true':raise RuntimeError('Unverified notification destination')
    cached=load_cache();dest=cached.get('destination',{})
    if str(dest.get('chat_id'))!=os.environ['TELEGRAM_ALLOWED_CHAT_ID'] or dest.get('verified') is not True:
        raise RuntimeError('Verified encrypted destination mismatch')
    key=hashlib.sha256((scope+':'+kind).encode()).hexdigest()
    notices=cached.setdefault('notices',{})
    notices={k:v for k,v in notices.items() if time.time()-v.get('at',0)<14*86400};cached['notices']=notices
    old=notices.get(key,{})
    if old.get('state') in ('sent','confirmed','uncertain','rejected'):return old
    if old.get('next_at',0)>time.time():return old
    notices[key]=dict(state='sent',at=time.time());save_cache(cached)
    try:
        if sender:
            response=sender(dest['chat_id'],text)
        else:
            payload=json.dumps(dict(chat_id=dest['chat_id'],text=text)).encode()
            req=request.Request('https://api.telegram.org/bot'+os.environ['TELEGRAM_BOT_TOKEN']+'/sendMessage',data=payload,headers={'Content-Type':'application/json'})
            with request.urlopen(req,timeout=20) as r:response=json.load(r)
    except error.HTTPError as exc:
        if exc.code==429:
            try:wait=json.loads(exc.read()).get('parameters',{}).get('retry_after')
            except Exception:wait=None
            if type(wait) is int and wait>0:
                notices[key]=dict(state='retryable',at=time.time(),next_at=time.time()+wait);save_cache(cached);return notices[key]
        notices[key]=dict(state='rejected',at=time.time(),http_status=exc.code);save_cache(cached);raise RuntimeError('Stock alert HTTP '+str(exc.code)) from None
    except BaseException:
        notices[key]=dict(state='uncertain',at=time.time());save_cache(cached);raise
    if not isinstance(response,dict) or response.get('ok') is not True or not response.get('result',{}).get('message_id'):
        notices[key]=dict(state='rejected',at=time.time());save_cache(cached);raise RuntimeError('Stock alert rejected')
    notices[key]=dict(state='confirmed',at=time.time(),message_id=response['result']['message_id']);save_cache(cached)
    return notices[key]
def remember(scope,value):
    cached=load_cache();cached['last_result']=dict(scope=scope,at=time.time(),**value);save_cache(cached)
