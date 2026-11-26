"""Read-only cost evidence for exact private owner-selected products."""
from datetime import datetime,timezone,timedelta
from china_price_apply import IO
from china_moysklad_read import Reader
KEY='china_agent:owner_guangzhou_costs:20261126:ten:v1'
def main():
    io=IO();a=io.get(KEY);assert a and len(a['articles'])==10
    old=io.get(KEY+':result')
    if old and old.get('status')=='complete':return
    ms=Reader();out=dict(status='reading',rows=[],observed_at=datetime.now(timezone.utc).isoformat(),moysklad_writes=0,wb_writes=0,telegram_calls=0)
    if not old:assert io.create(KEY+':result',out)
    for article in a['articles']:
        products=ms.pages('/entity/product',{'filter':'article='+article})
        exact=[p for p in products if p.get('article','').casefold()==article.casefold()]
        if not exact:
            code=article.split('-')[0];byid={}
            for suffix in ['с','c']:
                for p in ms.pages('/entity/product',{'filter':'code='+code+suffix}):
                    if p.get('code')==code+suffix:byid[p['id']]=p
            exact=list(byid.values())
        r=dict(article=article)
        if len(exact)!=1:r['error']='Product missing or ambiguous';out['rows'].append(r);io.put(KEY+':result',out);continue
        p=exact[0];r.update(product_id=p['id'],code=p.get('code'),ms_article=p.get('article'),name=p.get('name'),buyPrice=p.get('buyPrice'),archived=p.get('archived'))
        href=p['meta']['href'];params={'filter':'stockMode=all;quantityMode=all;product='+href}
        reports=ms.pages('/report/stock/all',params)
        r['current_reports']=[{k:x.get(k) for k in ('article','code','stock','reserve','quantity','price','sum')} for x in reports]
        positive=[x for x in reports if float(x.get('price') or 0)>0]
        r['cogs_source']='current_global_stock_report_RUB'
        if not positive:
            for days in [1,2,3,7,14,30,60]:
                moment=(datetime.now(timezone.utc)+timedelta(hours=3)-timedelta(days=days)).strftime('%Y-%m-%d 23:59:59')
                historical=ms.pages('/report/stock/all',dict(params,moment=moment))
                positive=[x for x in historical if float(x.get('price') or 0)>0]
                if positive:r.update(cogs_source='last_confirmed_positive_stock_report_RUB',cost_moment=moment);break
        if len(positive)==1:r['cogs_rub']=positive[0]['price']/100
        else:r['cost_error']='No unique confirmed positive stock cost'
        out['rows'].append(r);io.put(KEY+':result',out)
    out.update(status='complete',completed_at=datetime.now(timezone.utc).isoformat());io.put(KEY+':result',out)
    print('Read-only cost evidence complete; no prices or documents changed')
if __name__=='__main__':main()
