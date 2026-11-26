"""Render original card covers for visual audit only, no image edits to WB."""
import json,io,base64,requests
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
from PIL import Image,ImageDraw,ImageFont
from china_cloud_cost_control import Cache
c=Cache();ROOT='china_agent:owner_cart79_27:v1';d=c.get(ROOT+':result');cards=d['cards']['data']['rows'];assert len(cards)==79
old=requests.sessions.Session.request
def guard(s,method,url,*a,**kw):
 u=urlparse(url);m=method.upper();ok=(u.hostname==urlparse(c.url).hostname and m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/'))or(m=='GET'and u.hostname.endswith('.wbbasket.ru'))
 assert ok,'Only public cover reads and private result cache';return old(s,method,url,*a,**kw)
requests.sessions.Session.request=guard
def fetch(card):
 try:
  p=card['photos'][0];url=p.get('c246x328')or p['big'];r=requests.get(url,timeout=(6,16));r.raise_for_status();im=Image.open(io.BytesIO(r.content)).convert('RGB');im.thumbnail((176,236));return card,im,None
 except Exception as e:return card,None,type(e).__name__
try:
 cards=sorted(cards,key=lambda x:x['vendorCode']);results=list(ThreadPoolExecutor(max_workers=4).map(fetch,cards));font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',11)
 for page in range(5):
  key=ROOT+':covers:'+str(page)
  if c.get(key):continue
  part=results[page*16:(page+1)*16];im=Image.new('RGB',(720,1040),'white');dr=ImageDraw.Draw(im);labels=[]
  for i,(card,pic,error)in enumerate(part):
   x=(i%4)*180;y=(i//4)*260
   if pic:im.paste(pic,(x+(180-pic.width)//2,y))
   text=card['vendorCode'];dr.text((x+2,y+237),text[:24],fill='black',font=font);labels.append({'article':text,'nm':card['nmID'],'error':error})
  b=io.BytesIO();im.save(b,format='JPEG',quality=88);c.put(key,dict(image_base64=base64.b64encode(b.getvalue()).decode(),labels=labels,mime='image/jpeg'))
 print(json.dumps({'pages':5,'images':len(results),'errors':sum(bool(x[2])for x in results)}))
finally:requests.sessions.Session.request=old
