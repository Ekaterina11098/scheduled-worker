import unittest
from china_price_apply import notify
class Fake:
    def __init__(self,records):self.records=records;self.calls=[]
    def get(self,key):return self.records.get(key)
    def create(self,*args):self.calls.append('create');return True
    def put(self,*args):self.calls.append('put')
    def tg(self,*args):self.calls.append('send');return {'chat':{'id':-1004342917488},'message_id':1}
class NoticePermissions(unittest.TestCase):
    def test_direct_silence(self):
        io=Fake({'a':{'telegram_notifications':False}})
        notify(io,'a',{'status':'done','items':[]})
        self.assertEqual(io.calls,[])
    def test_inherited_owner_silence(self):
        io=Fake({'a':{'owner_approval_key':'owner'},'owner':{'telegram_notifications':False}})
        notify(io,'a',{'status':'done','items':[]})
        self.assertEqual(io.calls,[])
    def test_missing_owner_fails_closed(self):
        io=Fake({'a':{'owner_approval_key':'owner'}})
        notify(io,'a',{'status':'done','items':[]})
        self.assertEqual(io.calls,[])
    def test_current_telegram_confirmation_keeps_result(self):
        io=Fake({'a':{'report_date':'2026-11-18'}})
        notify(io,'a',{'status':'done','items':[]})
        self.assertEqual(io.calls,['create','send','put'])
if __name__=='__main__':unittest.main()
