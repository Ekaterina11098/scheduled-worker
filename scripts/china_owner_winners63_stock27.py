"""Read only63 stock currency-aware evidence."""
import json
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
from china_moysklad_read import Reader
io=AdvertisingIO();root='china_agent:owner_winners63_27:v1';scope=io.get(root+':scope')
assert len(scope['items'])==63
key=root+':stock'
if io.get(key):raise SystemExit('Preserved existing stock')
s=Reader().stock([x['article']for x in scope['items']],'msk')
assert io.create(key,dict(status='complete',stock=s,currency_metadata_key=root+':result',cost_unit='raw_minor_account_base_currency',observed_at=datetime.now(timezone.utc).isoformat(),wb_writes=0,telegram_calls=0))
print(json.dumps(dict(rows=len(s['rows']),missing=s['missing_articles'])))
