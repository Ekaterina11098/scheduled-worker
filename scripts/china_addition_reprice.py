"""Reconcile an independently verified price change without changing approved ad scope."""
import copy,math
def number(v):
 return type(v)in(int,float)and math.isfinite(v)
def reconcile(io,item,price,stock,published):
 e=copy.deepcopy(item['growth_evidence']);nm=item['nm_id']
 if price['article'].casefold()!=item['article'].casefold():raise ValueError('Addition article identity changed')
 if not stock.get('coverage_complete') or len(stock.get('rows',[]))!=1:raise ValueError('Addition MSK stock coverage incomplete')
 st=stock['rows'][0];free=st['stock']-st['reserve']
 if free<=0 or published.get('amounts',{}).get(str(nm),0)<=0:raise ValueError('Addition current stock unavailable')
 current=price['seller_price'];old=e['price_cny']
 if not number(current)or current<=0:raise ValueError('Addition current price unavailable')
 if current!=old:
  key='china_agent:price_write_lock:v1:'+str(nm);proof=io.get(key)or{};r=proof.get('readback')or{}
  prices={z.get('discountedPrice')for z in r.get('sizes',[])}
  execution=io.get(proof.get('execution',''))or{}
  if proof.get('status')!='done'or execution.get('status')!='done'or r.get('nmID')!=nm or r.get('vendorCode','').casefold()!=item['article'].casefold()or r.get('currencyIsoCode4217')!='CNY'or prices!={current}:
   raise ValueError('Addition changed price lacks verified execution receipt')
  required=['buyout','commission_pct','tax_pct','payment_reserve_pct','expected_margin_before_ads_cny','own_cogs_rub','fx_rub_per_cny']
  if any(not number(e.get(k))for k in required):raise ValueError('Addition repricing economics incomplete')
  q=e['buyout'];retained=1-sum(e[k]for k in ['commission_pct','tax_pct','payment_reserve_pct'])/100
  if not 0<q<=1 or not 0<retained<=1:raise ValueError('Addition repricing rates invalid')
  e['expected_margin_before_ads_cny']+=q*(current-old)*retained
  e['price_reconciliation']=dict(source_key=key,execution_key=proof['execution'],previous_price_cny=old,current_price_cny=current,price_margin_delta_cny=q*(current-old)*retained)
 fx=e['fx_rub_per_cny']
 if not number(fx)or fx<=0 or not number(st.get('price'))or st['price']<=0:raise ValueError('Addition current COGS or exchange rate unavailable')
 e['expected_margin_before_ads_cny']-=e['buyout']*(st['price']/100-e['own_cogs_rub'])/fx
 if e['expected_margin_before_ads_cny']<=0:raise ValueError('Addition current economics no longer positive')
 e.update(price_cny=current,seller_price_cny=current,own_cogs_rub=st['price']/100,stock_free=free,published_stock=published['amounts'][str(nm)],price_observed_at=price.get('observed_at'),preflight_recalculated=True)
 return e
