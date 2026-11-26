"""Tests for category labels derived from the picking list for WB IP named only 'ИП'."""
import unittest
import fbs_document_chain as m

class T:
 def __init__(self, names):
  self.names=names
 def request(self, base, path, method="GET", body=None, params=None):
  if path=="entity/customerorder/metadata":
   return {"states":[{"name":"Возврат на ФБО","meta":{"href":m.MS+"entity/customerorder/metadata/states/1","type":"state","mediaType":"application/json"}}]}
  if path.startswith("entity/product/"):
   item=self.names[path.split("/")[-1]]
   return {"id":path.split("/")[-1],"name":item[0],"article":item[1],"archived":False}
  raise AssertionError("Unexpected network request: "+path)

def pos(i):
 return {"assortment":{"meta":{"href":m.MS+"entity/product/"+str(i)}},"quantity":1}

class CaseTests(unittest.TestCase):
 def worker(self, items, cabinet="token_2"):
  w=m.Worker(T({str(i+1):item for i,item in enumerate(items)}),None,
     {"cabinet":cabinet,"order_annotation":{"state_name":"Возврат на ФБО","comment_prefix":"ИП","cabinet_word":"ИП"}})
  w._annotation_positions=[pos(i+1) for i in range(len(items))]
  return w
 def comment(self, items):
  w=self.worker(items)
  return w.order_annotation({"name":"ИП","closedAt":"2026-11-14T10:08:58Z"})["description"]
 def test_only_bags(self):
  self.assertEqual(self.comment([("Сумка кожа Celinea кремовая","660-CelineaBag-cream")]),"14 11 26 ИП Сумки")
 def test_only_umbrellas(self):
  self.assertEqual(self.comment([("Зонт складной розовый","101-Zont-pink")]),"14 11 26 ИП Зонты")
 def test_only_kizy(self):
  self.assertEqual(self.comment([("КИЗЫ модель","12-Kizy-pink")]),"14 11 26 ИП КИЗЫ")
 def test_bags_umbrellas_mixed(self):
  self.assertEqual(self.comment([("Сумка кожа Noel","60-NoelBag-black"),("Зонт складной","41-Zont-white")]),"14 11 26 ИП Сумки и зонты")
 def test_all_three(self):
  self.assertEqual(self.comment([("Сумка кожа Noel","60-NoelBag-black"),("Зонт складной","41-Zont-white"),("КИЗЫ","Kizy")]),"14 11 26 ИП Сумки, Зонты и КИЗЫ")
 def test_unknown_blocks(self):
  with self.assertRaisesRegex(m.Stop,"manual review"):
   self.comment([("Пыльник 40х40","bag-cover")])
 def test_mixed_unknown_blocks(self):
  with self.assertRaises(m.Stop):
   self.comment([("Сумка кожа","60-NoelBag"),("Пыльник","unclassified")])
 def test_non_ip_not_overridden(self):
  w=self.worker([],cabinet="token_1")
  w.c["order_annotation"].update(comment_prefix="Киргизия",cabinet_word="Киргизия")
  desc=w.order_annotation({"name":"Сумки","closedAt":"2026-11-14T10:08:58Z"})["description"]
  self.assertEqual(desc,"14 11 26  Киргизия Сумки")

class OOOCommentTests(unittest.TestCase):
 def test_kyrgyzstan_once_when_repeated_in_supply_name(self):
  worker=m.Worker(T({}),None,{"cabinet":"token_1","order_annotation":{"state_name":"Возврат на ФБО","comment_prefix":"Киргизия","cabinet_word":"Киргизия"}})
  result=worker.order_annotation({"name":"сумки киргизия","closedAt":"2026-11-26T05:38:36Z"})["description"]
  self.assertEqual(result,"26 11 26  Киргизия сумки")
 def test_kyrgyzstan_once_for_mixed_case(self):
  worker=m.Worker(T({}),None,{"cabinet":"token_1","order_annotation":{"state_name":"Возврат на ФБО","comment_prefix":"Киргизия","cabinet_word":"Киргизия"}})
  result=worker.order_annotation({"name":"Киргизия сумки КИРГИЗИЯ зонты","closedAt":"2026-11-26T05:38:36Z"})["description"]
  self.assertEqual(result,"26 11 26  Киргизия сумки зонты")

if __name__=="__main__": unittest.main()
