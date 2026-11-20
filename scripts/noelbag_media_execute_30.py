"""Owner-approved NoelBag 30-card insert at position 7. Video cards are NEVER written."""
import os,sys,json,time,io,hashlib,datetime as dt
import requests
from noelbag_media_insert7 import (Blocked,validate_plan,get_drive_assets,catalog,get_photos,
 classify,core,allowed_url,thumb,difference,EXPECTED_SHA,EXCLUDED,MAX_MEDIA,PROJECT_URL,WB_HOST,RESULT_KEY)
from noelbag_media_execute import original_backup, client, read_nm
from pathlib import Path

APPROVAL="APPROVED_NOELBAG_30_NO_VIDEO_INSERT7_20261120"
BATCH_KEY="noelbag_media_insert7:v2:execution_30"
READY_IDS={1473243914,1473243897,1473243898,1473243816,1473243817,1473243892,
1473243824,1473243906,1473243819,1473243825,1594309320,1473243818,1473243826,
1594295903,1473243902,1473243907,1473243908,1473243827,1473243909,1473243910,
1473243911,1473243912,1473243913,1473243915,1473243916,1473243917,1473243828,
1473243918,1473243919,1473243829}

def persist(s,records,phase="running"):
    key=os.environ["SUPABASE_SECRET_KEY"]
    h={"apikey":key,"Content-Type":"application/json","Prefer":"resolution=merge-duplicates"}
    if not key.startswith("sb_secret_"):h["Authorization"]="Bearer "+key
    now=dt.datetime.now(dt.timezone.utc)
    body={"cache_key":BATCH_KEY,"payload":{"phase":phase,"records":records,
        "verified":sum(x["status"]=="verified_at_7" for x in records),
        "duplicate":sum(x["status"]=="skipped_duplicate" for x in records),
        "errors":sum(x["status"].startswith("ERROR") for x in records)},
        "updated_at":now.isoformat(),"expires_at":(now+dt.timedelta(days=30)).isoformat()}
    res=s.post(PROJECT_URL+"/rest/v1/telegram_api_cache?on_conflict=cache_key",
        headers=h,json=body,timeout=45)
    res.raise_for_status()

def wait_card(token,nm,condition,retries=12,delay=10):
    for i in range(retries):
        if i:time.sleep(delay)
        c=read_nm(token,nm)
        if condition(c):return c
    raise Blocked("readback_timeout_or_uncertain")

def compare_old_images(reference, current):
    return len(reference)==len(current) and all(
      difference(thumb(x),thumb(y))<=10 for x,y in zip(reference,current))

def execute_one(token,s,row,slide):
    nm=int(row["nmID_WB_China"]); article=row["vendorCode"]
    before=read_nm(token,nm)
    if before.get("video"):raise Blocked("video_card_must_remain_untouched")
    originals=get_photos(before)
    state=classify(before,article,nm,slide,originals)
    if state["status"]=="already_present":
        return {"nmID":nm,"article":article,"status":"skipped_duplicate","position":state["position"]}
    if state["status"]!="ready_insert_at_7":raise Blocked("not_ready")
    if len(originals)+1>MAX_MEDIA:raise Blocked("photo_limit")
    original_backup(s,nm,originals)
    newer=read_nm(token,nm)
    if newer.get("photos")!=before.get("photos") or newer.get("video")!=before.get("video") or core(newer)!=core(before):
        raise Blocked("concurrent_change_before_write")

    # Upload to WB itself first, no temporary or external media links.
    resp=requests.post(WB_HOST+"/content/v3/media/file",
         headers={"Authorization":token,"X-Nm-Id":str(nm),"X-Photo-Number":str(len(originals)+1)},
         files={"uploadfile":("approved.png",io.BytesIO(slide),"image/png")},timeout=100)
    if resp.status_code!=200 or resp.json().get("error") is not False:
        raise Blocked("append_rejected_or_uncertain")
    def appended(c):
        if c.get("video") or core(c)!=core(before):raise Blocked("nonmedia_or_video_changed_after_append")
        if len(c.get("photos",[]))!=len(originals)+1:return False
        raw=get_photos(c)
        if not compare_old_images(originals,raw[:-1]):
            raise Blocked("old_photos_changed_after_append")
        if difference(thumb(slide),thumb(raw[-1]))>10:
            raise Blocked("new_slide_not_at_tail")
        return True
    staged=wait_card(token,nm,appended,retries=18,delay=10)
    # Reorder only already-hosted WB CDN links, preserving original exact sequence.
    cdn_urls=[allowed_url(p) for p in staged["photos"]]
    ordered=cdn_urls[:6]+[cdn_urls[-1]]+cdn_urls[6:-1]
    if len(ordered)!=len(set(ordered)):raise Blocked("duplicate_media_urls")
    before_reorder=read_nm(token,nm)
    if before_reorder.get("photos")!=staged.get("photos") or core(before_reorder)!=core(before) or before_reorder.get("video"):
        raise Blocked("concurrent_change_before_reorder")
    time.sleep(1)
    resp=requests.post(WB_HOST+"/content/v3/media/save",
        headers={"Authorization":token},json={"nmId":nm,"data":ordered},timeout=100)
    if resp.status_code!=200 or resp.json().get("error") is not False:
        raise Blocked("reorder_rejected_or_uncertain")
    def verify(c):
        if c.get("video") or core(c)!=core(before):raise Blocked("nonmedia_or_video_changed_after_reorder")
        if len(c.get("photos",[]))!=len(originals)+1:return False
        raw=get_photos(c)
        return (difference(thumb(slide),thumb(raw[6]))<=10 and
                compare_old_images(originals,raw[:6]+raw[7:]))
    wait_card(token,nm,verify,retries=18,delay=10)
    return {"nmID":nm,"article":article,"status":"verified_at_7",
            "photo_count_before":len(originals),"photo_count_after":len(originals)+1}

def main():
    if os.getenv("NOEL_MEDIA_WRITE_APPROVED")!=APPROVAL:raise Blocked("owner_approval_missing")
    if os.getenv("GITHUB_REPOSITORY")!="Ekaterina11098/scheduled-worker":raise Blocked("wrong_repository")
    s=client();token=os.environ["WB_TOKEN_3"]
    manifest=validate_plan(Path(__file__).with_name("noelbag_media_manifest.csv"))
    rows=[r for r in manifest if int(r["nmID_WB_China"]) in READY_IDS]
    if len(rows)!=30 or len(READY_IDS)!=30:raise Blocked("approved_target_count_mismatch")
    res=s.get(PROJECT_URL+"/rest/v1/telegram_api_cache",
              params={"cache_key":"eq."+RESULT_KEY,"select":"payload"},timeout=40)
    res.raise_for_status();records=res.json()
    if len(records)!=1:raise Blocked("preflight_report_not_found")
    plan=records[0]["payload"]
    if any(plan.get(k)!=v for k,v in {"mode":"read_only","status":"checked","ready":30,
         "blocked":15,"already_present":0}.items()):raise Blocked("preflight_numbers_changed")
    expected={int(t["nmID"]):t for t in plan["targets"]}
    if {n for n,t in expected.items() if t["status"]=="ready_insert_at_7"}!=READY_IDS:
        raise Blocked("preflight_ready_set_changed")
    if any(expected[int(r["nmID_WB_China"])]["slide"]!=r["image"] for r in rows):
        raise Blocked("preflight_asset_mapping_changed")
    assets=get_drive_assets(PROJECT_URL,{"apikey":os.environ["SUPABASE_SECRET_KEY"]})
    results=[]
    for r in rows:
        nm=int(r["nmID_WB_China"])
        try:
            result=execute_one(token,s,r,assets[r["image"]])
            results.append(result);persist(s,results)
            print("CARD_RESULT",json.dumps(result,ensure_ascii=False),flush=True)
        except Exception as e:
            reason=str(e) if isinstance(e,Blocked) else type(e).__name__
            record={"nmID":nm,"article":r["vendorCode"],"status":"ERROR_STOP",
                    "reason":reason}
            results.append(record);persist(s,results,"stopped")
            print("CARD_STOP",json.dumps(record,ensure_ascii=False),flush=True)
            raise
    persist(s,results,"complete")
    print("FINAL_EXECUTION",json.dumps(results,ensure_ascii=False),flush=True)
if __name__=="__main__":
    try:main()
    except Exception as e:
        print("EXECUTION_STOPPED",str(e) if isinstance(e,Blocked) else type(e).__name__,file=sys.stderr)
        sys.exit(2)
