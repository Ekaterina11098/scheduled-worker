"""One owner-authorized price operation; inputs/results remain in private storage."""
import json,re,time
from datetime import datetime,timezone
from decimal import Decimal,ROUND_CEILING
from china_price_apply import IO
KEY='china_agent:owner_price_rules:20261124:7and15:v1'
def stamp():return datetime.now(timezone.utc).isoformat()
def make_plan(rows,a):
    excluded=set(a['excluded_models']);seen=set();items=[]
    for p in rows:
        nm=p['nmID'];assert nm not in seen;seen.add(nm)
        assert p['currencyIsoCode4217']=='CNY' and p['editableSizePrice'] is False
        sizes=p['sizes'];assert sizes and len({str(z['price']) for z in sizes})==1 and len({str(z['discountedPrice']) for z in sizes})==1
        old=Decimal(str(sizes[0]['discountedPrice']));base=Decimal(str(sizes[0]['price']));discount=p['discount']
        assert old>=0 and base>=0 and base==base.to_integral_value() and type(discount)is int and 0<=discount<100
        factor=Decimal(100-discount)/100;assert abs(old-base*factor)<=Decimal('.01')
        m=re.match(r'^(\d+)(?:-|$)',p['vendorCode']);model=int(m[1]) if m else None
        missing_price=not old or not base
        rate=0 if model in excluded or missing_price else 7 if model==a['special_model'] or old>Decimal(str(a['threshold_cny'])) else 15
        newbase=int((base*(1+Decimal(rate)/100)).to_integral_value(rounding=ROUND_CEILING)) if rate else int(base)
        target=Decimal(newbase)*factor
        items.append(dict(nmID=nm,article=p['vendorCode'],model=model,rate=rate,missing_price=bool(missing_price and model not in excluded),old_base=int(base),old_cny=str(old),target_cny=str(target),discount=discount,club_discount=p.get('clubDiscount'),request=dict(nmID=nm,price=newbase,discount=discount),status='excluded' if not rate else 'ready'))
    assert excluded<={x['model'] for x in items} and any(x['model']==a['special_model'] for x in items)
    assert 1<=len([x for x in items if x['rate']])<=1000
    return items
def all_prices(io):
    out=[]
    for offset in range(0,21000,1000):
        rows=io.wb('/api/v2/list/goods/filter?limit=1000&offset='+str(offset))['listGoods'];out+=rows
        if len(rows)<1000:return out
    raise ValueError('Incomplete pagination')
def main():
    io=IO();a=io.get(KEY)
    assert a and a['authorized'] is True and a['source']=='owner_current_codex_chat' and a['telegram_notifications'] is False
    assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
    ekey=KEY+':execution';e=io.get(ekey)
    if e and e['status'] in ('done','uncertain','failed'):return
    io.capability()
    if not e:
        rows=all_prices(io);items=make_plan(rows,a)
        assert len(rows)>=a['minimum_expected_cards']
        for x in items:
            if not x['rate']:continue
            lock=io.get('china_agent:price_write_lock:v1:'+str(x['nmID']))
            assert not lock or lock.get('status') not in ('submitting','submitted','uncertain'),'Existing unfinished price upload'
        e=dict(status='preflight',created_at=stamp(),items=items,source_prices=rows,wb_writes=0,telegram_sends=0)
        assert io.create(ekey,e),'Operation already claimed'
    if e['status']=='submitting':
        e.update(status='uncertain',reason='Submission may have succeeded; do not retry');io.put(ekey,e);return
    if e['status']=='preflight':
        fresh={p['nmID']:p for p in all_prices(io)}
        assert len(fresh)==len(e['source_prices']) and all(fresh[p['nmID']]==p for p in e['source_prices']),'Prices changed during preflight'
        for x in e['items']:
            if not x['rate']:continue
            lk='china_agent:price_write_lock:v1:'+str(x['nmID']);prev=io.get(lk)
            assert not prev or prev.get('status') not in ('submitting','submitted','uncertain') or prev.get('execution')==ekey
            v=dict(execution=ekey,status='submitting',created_at=stamp())
            if prev:io.put(lk,v)
            else:assert io.create(lk,v)
        e.update(status='submitting',submitted_at=stamp());io.put(ekey,e)
        try:
            reply=io.wb('/api/v2/upload/task','POST',{'data':[x['request'] for x in e['items'] if x['rate']]})
            assert type(reply.get('id'))is int and reply['id']>0
            e.update(status='submitted',upload_id=reply['id'],upload_response=reply,wb_writes=1);io.put(ekey,e)
        except Exception:
            e.update(status='uncertain',reason='Unknown submission result; no retry');io.put(ekey,e);raise RuntimeError('Submission requires readback') from None
    if e['status']=='submitted':
        for _ in range(45):
            try:
                state=io.wb('/api/v2/history/tasks?uploadID='+str(e['upload_id']));e['wb_state']=state
                if state.get('status') in (3,4,5,6):
                    details=io.wb('/api/v2/history/goods/task?uploadID='+str(e['upload_id'])+'&limit=1000&offset=0')
                    assert details.get('uploadID')==e['upload_id']
                    e['wb_details']=details;fresh={p['nmID']:p for p in all_prices(io)}
                    for x in e['items']:
                        p=fresh.get(x['nmID'],{});x['readback']=p
                        expected=x['request']['price'];ok=p.get('vendorCode')==x['article'] and p.get('currencyIsoCode4217')=='CNY' and p.get('discount')==x['discount'] and p.get('clubDiscount')==x['club_discount'] and bool(p.get('sizes')) and all(Decimal(str(z['price']))==expected and abs(Decimal(str(z['discountedPrice']))-Decimal(x['target_cny']))<=Decimal('.01') for z in p['sizes'])
                        goods=[g for g in details.get('historyGoods',[]) if g.get('nmID')==x['nmID']]
                        if x['rate']:ok=ok and state.get('status') in (3,5) and bool(goods) and not any(g.get('errorText') for g in goods)
                        x['status']=('applied' if x['rate'] else 'no_price_verified' if x['missing_price'] else 'excluded_verified') if ok else 'failed'
                        if x['rate']:io.put('china_agent:price_write_lock:v1:'+str(x['nmID']),dict(execution=ekey,status='done' if ok else 'uncertain',upload_id=e['upload_id']))
                    e.update(status='done',completed_at=stamp(),summary={s:sum(x['status']==s for x in e['items']) for s in ('applied','excluded_verified','no_price_verified','failed')});io.put(ekey,e)
                    io.put('china_agent:prices:v1',dict(rows=list(fresh.values()),observed_at=stamp(),source='wb_api_verified_owner_price_rules'))
                    print(json.dumps(e['summary']));return
            except Exception:e['last_check']='Readback pending'
            io.put(ekey,e);time.sleep(10)
        raise RuntimeError('WB upload remains pending; do not resubmit')
if __name__=='__main__':main()
