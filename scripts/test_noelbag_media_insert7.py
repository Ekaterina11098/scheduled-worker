"""Pure-mock and deterministic unit checks. No network, no WB media writes."""
import io, unittest
from unittest.mock import patch
from PIL import Image
import noelbag_media_insert7 as n

def picture(colour):
    img=Image.new("RGB",(1086,1448),colour); buf=io.BytesIO();img.save(buf,format="PNG");return buf.getvalue()
def card(nm=1473243893,num=10):
    return {"nmID":nm,"vendorCode":"041-NoelBag-beige","photos":[{"big":f"https://basket-47.wbbasket.ru/vol14732/part1473243/{nm}/images/big/{i}.webp"} for i in range(1,num+1)],
            "title":"same","description":"unchanged","dimensions":{"length":1,"width":2},"characteristics":[{"id":1,"value":["a"]}],"sizes":[{"skus":["bar"]}]}
class Tests(unittest.TestCase):
    def setUp(self):
        self.target=picture((10,10,200))
        self.prior=[picture((40+i*10,140,50)) for i in range(10)]
    def test_hash_deterministic(self):
        self.assertEqual(n.digest(self.target),n.digest(self.target))
    def test_no_false_duplicate(self):
        self.assertEqual(n.classify(card(),"041-NoelBag-beige",1473243893,self.target,self.prior)["status"],"ready_insert_at_7")
    def test_existing_at_7_skipped(self):
        a=self.prior.copy();a[6]=self.target
        self.assertEqual(n.classify(card(),"041-NoelBag-beige",1473243893,self.target,a)["position"],7)
    def test_duplicate_at_other_position_skipped(self):
        a=self.prior.copy();a[1]=self.target
        self.assertEqual(n.classify(card(),"041-NoelBag-beige",1473243893,self.target,a)["status"],"already_present")
    def test_wrong_nm_blocked(self):
        with self.assertRaises(n.Blocked):n.classify(card(),"041-NoelBag-beige",123,self.target,self.prior)
    def test_wrong_vendor_blocked(self):
        with self.assertRaises(n.Blocked):n.classify(card(),"044-NoelBag-black",1473243893,self.target,self.prior)
    def test_too_few_photos_blocked(self):
        with self.assertRaises(n.Blocked):n.classify(card(num=5),"041-NoelBag-beige",1473243893,self.target,self.prior[:5])
    def test_video_blocked(self):
        c=card();c["video"]={"url":"x"}
        with self.assertRaises(n.Blocked):n.classify(c,"041-NoelBag-beige",1473243893,self.target,self.prior)
    def test_photo_limit_blocked(self):
        a=[picture((i*7%256,120,90)) for i in range(30)]
        with self.assertRaises(n.Blocked):n.classify(card(num=30),"041-NoelBag-beige",1473243893,self.target,a)
    def test_no_mixed_up_ids(self):
        rows=[{"nmID_WB_China":"1473243891","action":"skip","image":"1.png"},{"nmID_WB_China":"1473243893","image":"1.png"}]
        report=n.preflight(rows,{"1.png":self.target},[card()],lambda _:self.prior)
        self.assertEqual(report["ready"],1);self.assertEqual(report["excluded"],[1473243891]);self.assertEqual(report["wb_writes"],0)
    def test_preflight_blocked_missing_card(self):
        row=[{"nmID_WB_China":"1473243893","image":"1.png"}]
        report=n.preflight(row,{"1.png":self.target},[],lambda c:[])
        self.assertEqual(report["blocked"],1)
if __name__=="__main__":unittest.main()
