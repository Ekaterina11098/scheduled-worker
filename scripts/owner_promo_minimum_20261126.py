"""Exact owner-approved minimal reduction to UI-observed promotion thresholds."""
from decimal import Decimal,ROUND_FLOOR
import owner_price_rules_20261124 as engine
KEY='china_agent:owner_promo_minimum:20261126:seventeen:v1'
def make_plan(rows,a):
    selections=a['selections'];assert len(selections)==17 and len({s['article'] for s in selections})==17
    items=[]
    for s in selections:
        found=[p for p in rows if p['vendorCode']==s['article']];assert len(found)==1
        p=found[0];assert p['currencyIsoCode4217']=='CNY' and p['editableSizePrice'] is False
        sizes=p['sizes'];assert sizes and len({str(z['price']) for z in sizes})==1 and len({str(z['discountedPrice']) for z in sizes})==1
        old=Decimal(str(sizes[0]['discountedPrice']));oldbase=Decimal(str(sizes[0]['price']));discount=p['discount']
        assert old==Decimal(str(s['expected_cny'])),'Current price changed since owner report'
        assert type(discount)is int and 0<=discount<100 and oldbase==oldbase.to_integral_value()
        factor=Decimal(100-discount)/100;threshold=Decimal(str(s['threshold_cny']))
        base=int((threshold/factor).to_integral_value(rounding=ROUND_FLOOR));target=Decimal(base)*factor
        assert 1<=base<oldbase and 0<old-target<=5 and target<=threshold
        assert Decimal(base+1)*factor>threshold,'Reduction is not minimal at unchanged seller discount'
        items.append(dict(nmID=p['nmID'],article=p['vendorCode'],model=None,rate=float((target/old-1)*100),missing_price=False,action='minimal_promo_reduction',threshold_cny=str(threshold),old_base=int(oldbase),old_cny=str(old),target_cny=str(target),discount=discount,club_discount=p.get('clubDiscount'),request=dict(nmID=p['nmID'],price=base,discount=discount),status='ready'))
    return items
if __name__=='__main__':
    engine.KEY=KEY;engine.make_plan=make_plan;engine.main()
