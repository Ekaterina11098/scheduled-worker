"""Owner correction of exact identities from an earlier verified operation."""
from decimal import Decimal,ROUND_CEILING
import owner_price_rules_20261124 as engine
KEY='china_agent:owner_price_correction:20261124:seven_and_coats:v1'
def make_plan(rows,a):
    by_id={p['nmID']:p for p in rows};assert len(by_id)==len(rows)
    assert len(a['selections'])==13 and len({s['nmID'] for s in a['selections']})==13
    items=[]
    for s in a['selections']:
        p=by_id[s['nmID']]
        assert p['vendorCode']==s['article'] and p['currencyIsoCode4217']=='CNY' and p['editableSizePrice'] is False
        assert p['discount']==s['discount'] and p.get('clubDiscount')==s['club_discount']
        assert p.get('sizes') and all(Decimal(str(z['price']))==s['expected_base'] and abs(Decimal(str(z['discountedPrice']))-Decimal(s['expected_cny']))<=Decimal('.01') for z in p['sizes']),'Price changed since prior verified operation'
        if s['action']=='restore':
            base=s['restore_base'];target=Decimal(s['restore_cny']);assert 'furcoat' in s['article'].lower()
        else:
            assert s['action']=='raise' and s['expected_base']>0
            rate=7 if Decimal(s['expected_cny'])>400 else 15
            base=int((Decimal(s['expected_base'])*(1+Decimal(rate)/100)).to_integral_value(rounding=ROUND_CEILING))
            target=Decimal(base)*Decimal(100-s['discount'])/100
        assert Decimal(base)*Decimal(100-s['discount'])/100==target
        assert (base<s['expected_base'])==(s['action']=='restore')
        items.append(dict(nmID=s['nmID'],article=s['article'],action=s['action'],model=None,rate=float((target/Decimal(s['expected_cny'])-1)*100),missing_price=False,old_base=s['expected_base'],old_cny=s['expected_cny'],target_cny=str(target),discount=s['discount'],club_discount=s['club_discount'],request=dict(nmID=s['nmID'],price=base,discount=s['discount']),status='ready'))
    assert sum(x['action']=='restore' for x in items)==6 and sum(x['action']=='raise' for x in items)==7
    return items
if __name__=='__main__':
    engine.KEY=KEY;engine.make_plan=make_plan;engine.main()
