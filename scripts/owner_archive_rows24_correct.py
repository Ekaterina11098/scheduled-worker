"""Owner-authorized presentation-only correction. No WB access or new plan."""
import copy,json,hashlib,base64,os,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_advertising_midday import render_midday,covered_totals
from china_archived_report_window import midday_view
from china_daily_ad_actions import BIND
from china_loss_control import CHAT,BOT,PLAN,digest
from china_report_buttons import ROOT as BUTTON_ROOT
ROOT='china_agent:owner_archive_rows_correction:2026-11-24:v1'
ART='china_agent:advertising_midday_artifacts:2026-11-24:ready-v2'
DEL='china_agent:advertising_midday_delivery:2026-11-24:ready-v2'
STATES=[{"id":40892162,"status":4,"timestamps":{"created":"2026-10-12T15:24:35.245159+03:00","deleted":"2100-01-01T00:00:00+03:00","started":None,"updated":"2026-10-12T15:24:35.245159+03:00"}},{"id":40933588,"status":9,"timestamps":{"created":"2026-10-13T11:48:13.397736+03:00","deleted":"2100-01-01T00:00:00+03:00","started":"2026-10-18T19:48:22.488916+03:00","updated":"2026-11-24T12:07:01.994902+03:00"}},{"id":40945478,"status":9,"timestamps":{"created":"2026-10-13T16:08:21.346551+03:00","deleted":"2100-01-01T00:00:00+03:00","started":"2026-10-13T16:08:21.378771+03:00","updated":"2026-11-24T09:39:39.714983+03:00"}},{"id":40945502,"status":9,"timestamps":{"created":"2026-10-13T16:08:55.926837+03:00","deleted":"2100-01-01T00:00:00+03:00","started":"2026-10-13T16:08:55.956185+03:00","updated":"2026-11-18T09:07:57.471567+03:00"}},{"id":40964981,"status":9,"timestamps":{"created":"2026-10-14T10:27:54.827837+03:00","deleted":"2100-01-01T00:00:00+03:00","started":"2026-10-14T10:27:54.8707+03:00","updated":"2026-11-21T09:30:15.432641+03:00"}},{"id":41055480,"status":9,"timestamps":{"created":"2026-10-16T14:43:02.617383+03:00","deleted":"2100-01-01T00:00:00+03:00","started":"2026-11-24T08:54:16.671378+03:00","updated":"2026-11-24T08:54:16.671378+03:00"}},{"id":41155909,"status":9,"timestamps":{"created":"2026-10-20T10:37:04.346064+03:00","deleted":"2100-01-01T00:00:00+03:00","started":"2026-10-20T10:37:04.396062+03:00","updated":"2026-11-24T08:45:26.077786+03:00"}},{"id":41187173,"status":9,"timestamps":{"created":"2026-10-21T10:23:35.004601+03:00","deleted":"2100-01-01T00:00:00+03:00","started":"2026-10-21T10:23:35.054211+03:00","updated":"2026-11-09T10:29:43.359876+03:00"}},{"id":41270309,"status":9,"timestamps":{"created":"2026-10-23T18:33:03.784323+03:00","deleted":"2100-01-01T00:00:00+03:00","started":"2026-10-25T14:05:51.108497+03:00","updated":"2026-11-24T09:39:56.370581+03:00"}},{"id":41298169,"status":9,"timestamps":{"created":"2026-10-25T16:39:37.904412+03:00","deleted":"2100-01-01T00:00:00+03:00","started":"2026-10-28T13:21:34.702391+03:00","updated":"2026-11-24T08:41:53.170445+03:00"}},{"id":41325622,"status":9,"timestamps":{"created":"2026-10-26T16:31:58.221489+03:00","deleted":"2100-01-01T00:00:00+03:00","started":"2026-10-26T17:09:58.077954+03:00","updated":"2026-11-23T08:44:35.514042+03:00"}},{"id":41332083,"status":9,"timestamps":{"created":"2026-10-26T21:11:05.864386+03:00","deleted":"2100-01-01T00:00:00+03:00","started":"2026-11-17T10:35:41.759571+03:00","updated":"2026-11-24T12:07:20.3161+03:00"}},{"id":41680341,"status":9,"timestamps":{"created":"2026-11-08T09:48:23.851226+03:00","deleted":"2100-01-01T00:00:00+03:00","started":"2026-11-09T12:10:16.207022+03:00","updated":"2026-11-11T09:41:45.91065+03:00"}},{"id":41779660,"status":9,"timestamps":{"created":"2026-11-11T10:04:44.77098+03:00","deleted":"2100-01-01T00:00:00+03:00","started":"2026-11-17T10:39:07.934087+03:00","updated":"2026-11-24T08:42:27.146965+03:00"}},{"id":41967612,"status":9,"timestamps":{"created":"2026-11-17T11:33:42.772178+03:00","deleted":"2100-01-01T00:00:00+03:00","started":"2026-11-20T10:07:59.278226+03:00","updated":"2026-11-24T08:42:36.210713+03:00"}},{"id":42022679,"status":9,"timestamps":{"created":"2026-11-19T00:09:54.868135+03:00","deleted":"2100-01-01T00:00:00+03:00","started":"2026-11-19T00:10:39.16049+03:00","updated":"2026-11-22T17:44:37.314796+03:00"}},{"id":42068186,"status":9,"timestamps":{"created":"2026-11-20T10:44:14.613432+03:00","deleted":"2100-01-01T00:00:00+03:00","started":"2026-11-20T10:44:45.769143+03:00","updated":"2026-11-24T08:42:47.459372+03:00"}},{"id":42068228,"status":9,"timestamps":{"created":"2026-11-20T10:45:00.22595+03:00","deleted":"2100-01-01T00:00:00+03:00","started":"2026-11-22T10:53:07.319215+03:00","updated":"2026-11-22T10:53:07.319215+03:00"}},{"id":42068265,"status":9,"timestamps":{"created":"2026-11-20T10:45:44.657135+03:00","deleted":"2100-01-01T00:00:00+03:00","started":"2026-11-21T10:05:09.747076+03:00","updated":"2026-11-23T08:45:22.512973+03:00"}},{"id":42088552,"status":9,"timestamps":{"created":"2026-11-20T17:22:29.988465+03:00","deleted":"2100-01-01T00:00:00+03:00","started":"2026-11-22T23:28:18.147743+03:00","updated":"2026-11-24T09:40:27.496232+03:00"}},{"id":40811856,"status":7,"timestamps":{"created":"2026-10-09T11:56:25.815677+03:00","deleted":"2026-11-13T13:12:40.197817+03:00","started":"2026-10-14T21:27:41.648056+03:00","updated":"2026-11-13T13:12:40.197817+03:00"}},{"id":41155824,"status":7,"timestamps":{"created":"2026-10-20T10:35:24.588137+03:00","deleted":"2026-11-11T09:40:19.46114+03:00","started":"2026-10-20T10:35:24.634704+03:00","updated":"2026-11-11T09:40:19.46114+03:00"}},{"id":41270471,"status":7,"timestamps":{"created":"2026-10-23T18:43:32.063714+03:00","deleted":"2026-11-11T09:40:29.194607+03:00","started":"2026-10-25T14:06:18.456321+03:00","updated":"2026-11-11T09:40:29.194607+03:00"}},{"id":41270474,"status":7,"timestamps":{"created":"2026-10-23T18:43:44.745625+03:00","deleted":"2026-11-02T00:13:25.342591+03:00","started":"2026-10-25T14:06:42.978615+03:00","updated":"2026-11-02T00:13:25.342591+03:00"}},{"id":41296359,"status":7,"timestamps":{"created":"2026-10-25T13:51:51.374231+03:00","deleted":"2026-11-20T09:56:52.897697+03:00","started":"2026-11-10T11:33:35.756041+03:00","updated":"2026-11-20T09:56:52.897697+03:00"}},{"id":41296363,"status":7,"timestamps":{"created":"2026-10-25T13:52:07.628576+03:00","deleted":"2026-11-15T01:47:57.4624+03:00","started":"2026-11-12T13:46:42.158358+03:00","updated":"2026-11-15T01:47:57.4624+03:00"}},{"id":41325637,"status":7,"timestamps":{"created":"2026-10-26T16:32:23.664414+03:00","deleted":"2026-11-17T10:08:43.196147+03:00","started":"2026-11-14T11:07:39.717779+03:00","updated":"2026-11-17T10:08:43.196147+03:00"}},{"id":41413113,"status":7,"timestamps":{"created":"2026-10-29T14:09:49.33084+03:00","deleted":"2026-10-29T23:17:29.980116+03:00","started":"2026-10-29T18:46:40.107997+03:00","updated":"2026-10-29T23:17:29.980116+03:00"}},{"id":41415271,"status":7,"timestamps":{"created":"2026-10-29T15:12:04.892569+03:00","deleted":"2026-10-29T23:18:37.451649+03:00","started":"2026-10-29T15:16:09.080299+03:00","updated":"2026-10-29T23:18:37.451649+03:00"}},{"id":41570073,"status":7,"timestamps":{"created":"2026-11-04T13:58:03.955826+03:00","deleted":"2026-11-11T09:41:37.237257+03:00","started":"2026-11-04T13:58:31.36681+03:00","updated":"2026-11-11T09:41:37.237257+03:00"}},{"id":41680449,"status":7,"timestamps":{"created":"2026-11-08T09:57:46.645199+03:00","deleted":"2026-11-22T10:54:50.19338+03:00","started":"2026-11-15T01:48:08.544534+03:00","updated":"2026-11-22T10:54:50.19338+03:00"}},{"id":41756218,"status":7,"timestamps":{"created":"2026-11-10T15:45:15.894864+03:00","deleted":"2026-11-17T11:26:33.758986+03:00","started":"2026-11-10T15:45:15.946064+03:00","updated":"2026-11-17T11:26:33.758986+03:00"}},{"id":41925305,"status":7,"timestamps":{"created":"2026-11-16T12:36:07.356125+03:00","deleted":"2026-11-18T23:29:05.832386+03:00","started":"2026-11-16T12:36:33.197397+03:00","updated":"2026-11-18T23:29:05.832386+03:00"}},{"id":42068146,"status":7,"timestamps":{"created":"2026-11-20T10:43:28.60207+03:00","deleted":"2026-11-22T10:53:22.942891+03:00","started":"2026-11-20T10:43:58.7307+03:00","updated":"2026-11-22T10:53:22.942891+03:00"}}]
def main():
 orig=requests.sessions.Session.request
 def guard(s,method,url,*args,**kw):
  u=urlparse(url)
  ok=(u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname and method.upper()in('GET','POST','PATCH')and u.path.startswith('/rest/v1/'))or(u.hostname=='api.telegram.org'and method.upper()=='POST'and u.path.rsplit('/',1)[-1]in('getMe','editMessageMedia','deleteMessage'))
  assert ok,'Presentation correction only; WB access prohibited'
  return orig(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 io=AdvertisingIO();existing=io.get(ROOT)
 if existing:
  assert existing.get('status')=='verified','Existing attempt requires inspection; no replay'
  print(json.dumps(dict(status='already_verified',wb_writes=0)));return
 a=io.get(ART);d=io.get(DEL);menu=io.get('china_agent:main_menu:v1:report:drr')
 assert a['status']=='frozen' and d['status']=='delivered'
 assert [p['message_id']for p in d['parts']]==[1148,1149]
 assert [f['action_count']for f in a['files']]==[1,0]
 f0=a['files'][0];p=io.get(PLAN+f0['plan_id']);p1=io.get(PLAN+a['files'][1]['plan_id'])
 assert p['plan_sha256']==digest(p['items'])==f0['plan_sha256'] and len(p['items'])==1 and not p1['items']
 bound=io.get(BIND+'1148');buttons=io.get(BUTTON_ROOT+'message:1148')
 assert bound['plan_id']==p['plan_id'] and buttons['plan_sha256']==p['plan_sha256']
 b=copy.deepcopy(a['bundle']);states={c['id']:c for c in STATES}
 for c in b['campaigns']:
  s=states[c['id']];c.update(status=s['status'],archived_at=(s.get('timestamps')or{}).get('deleted'))
 view=midday_view(b);assert len(view['campaigns'])==19 and len(view['presentation_omitted_archives'])==14
 before=covered_totals(b['campaigns']);after=covered_totals(view['presentation_totals_campaigns'])
 assert before['total']==after['total'] # coverage row counts intentionally change, financial counters do not
 files=render_midday(b);assert len(files)==1 and files[0]['actions']==p['items']
 f=files[0];receipt0=buttons['receipt'];markup=receipt0['reply_markup']
 v=dict(status='prepared',before_artifact=a,before_delivery=d,before_menu=menu,omitted=view['presentation_omitted_archives'],totals_before=before,totals_after=after,wb_writes=0,actions_unchanged=True,plan_id=p['plan_id'],plan_sha256=p['plan_sha256'],image_sha256=hashlib.sha256(f['bytes']).hexdigest())
 assert io.create(ROOT,v)
 assert io.tg('getMe',{})['id']==BOT
 caption='Китай · промежуточный отчёт · 2026-11-24 · 1/1. Ответьте «Сделай всё» для 1 новых действий только этого PNG.'
 v['status']='editing';io.put(ROOT,v)
 r=requests.post('https://api.telegram.org/bot'+io.bot+'/editMessageMedia',data=dict(chat_id=str(CHAT),message_id='1148',media=json.dumps(dict(type='photo',media='attach://photo',caption=caption),ensure_ascii=False),reply_markup=json.dumps(markup,ensure_ascii=False)),files={'photo':('midday.png',f['bytes'],'image/png')},timeout=(10,60))
 j=r.json();assert r.ok and j.get('ok')is True
 receipt=j['result'];assert receipt['chat']['id']==CHAT and receipt['message_id']==1148 and receipt['reply_markup']==markup
 v.update(status='edited',edit_receipt=receipt);io.put(ROOT,v)
 # Preserve exact executable plan, selected button registry and approval state.
 buttons.update(receipt=receipt,delivery_method='editMessageMedia',revision_source_key=ROOT)
 io.put(BUTTON_ROOT+'message:1148',buttons)
 assert io.get(BIND+'1148')==bound and io.get(PLAN+p['plan_id'])==p
 v['status']='deleting_empty_page';io.put(ROOT,v)
 deletion=io.tg('deleteMessage',dict(chat_id=CHAT,message_id=1149));assert deletion is True
 v.update(status='deleted_empty_page',delete_receipt=deletion);io.put(ROOT,v)
 nf=dict(f0,b64=base64.b64encode(f['bytes']).decode(),page=1,total=1)
 a.update(bundle=b,files=[nf],presentation_revision='empty_archives_hidden_v1',presentation_correction_ref=ROOT)
 io.put(ART,a)
 part=dict(d['parts'][0]);part.update(receipt=receipt,caption=caption,status='sent',sha256=v['image_sha256'],delivery_method='editMessageMedia')
 d.update(parts=[part],presentation_correction_ref=ROOT);io.put(DEL,d)
 # Keep the current report generation; removing the empty second page changes no validity.
 page=dict(next(x for x in menu['pages']if x['message_id']==1148),receipt=receipt)
 menu.update(pages=[page],message_ids=[1148],message_id=1148,receipt=receipt,plan_id=p['plan_id'],plan_sha256=p['plan_sha256'])
 io.put('china_agent:main_menu:v1:report:drr',menu)
 # The empty deleted page has no actions and cannot be used for navigation.
 empty_binding=io.get(BIND+'1149')or{}
 io.put(ROOT+':deleted_page_binding',empty_binding)
 assert io.get(ART)['files'][0]['plan_sha256']==p['plan_sha256']
 assert io.get(DEL)['parts'][0]['receipt']['message_id']==1148
 assert io.get(BUTTON_ROOT+'message:1148')['token']==buttons['token']
 v.update(status='verified',completed_at=datetime.now(timezone.utc).isoformat(),visible_campaigns=19,hidden_archives=14,message_id=1148,deleted_message_id=1149)
 io.put(ROOT,v)
 print(json.dumps(dict(status='verified',message_id=1148,deleted_message_id=1149,visible=19,hidden=14,actions=1,wb_writes=0)))
if __name__=='__main__':main()
