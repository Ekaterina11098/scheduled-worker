import json
import fbs_document_chain as m
t=m.Transport()
p=t.request(m.MS,"entity/product/5ac9f518-0d63-11f1-0a80-0334001b7932")
print(json.dumps({"article":p.get("article"),"name":p.get("name"),"code":p.get("code"),"archived":p.get("archived")},ensure_ascii=False))
