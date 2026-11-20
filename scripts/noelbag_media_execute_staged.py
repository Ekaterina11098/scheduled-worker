"""Owner-approved NoelBag 30 video-free photos: staged append then verified reorder.
Never append twice after a successful WB request. Skip video cards entirely.
"""
import os,sys,io,time,json,hashlib,datetime as dt
import requests
from urllib.parse import quote
from pathlib import Path
from noelbag_media_insert7 import (Blocked,validate_plan,get_drive_assets,get_photos,core,
    allowed_url,thumb,difference,EXPECTED_SHA,EXCLUDED,MAX_MEDIA,PROJECT_URL,WB_HOST,RESULT_KEY)
from noelbag_media_execute import original_backup,client
from noelbag_media_execute_30 import READY_IDS,APPROVAL
BUCKET="owner-media-recovery"
PREFIX="noelbag-insert7-approved/v1/backup/"
JOURNAL="noelbag_media_insert7:v3:execution_30"

def read_nm(token,nm,retries=2):
    for k in range(retries):
        request={"settings":{"sort":{"ascending":False},"cursor":{"limit":100},
                 "filter":{"withPhoto":-1,"textSearch":str(nm)}}}
        r=requests.post(WB_HOST+"/content/v2/get/cards/list",
             headers={"Authorization":token},json=request,timeout=90)
        if r.status_code==429:raise Blocked("wb_rate_limited")
        r.raise_for_status()
        data=r.json();pages=data.get("cards") or data.get("data",{}).get("cards") or []
        hits=[c for c in pages if c.get("nmID")==nm]
        if len(hits)>1:raise Blocked("ambiguous_nmID")
        if len(hits)==1:return hits[0]
        if k+1<retries:time.sleep(6)
    return None

def backup(s,nm):
    r=s.post(PROJECT_URL+"/storage/v1/object/list/"+BUCKET,
      json={"prefix":PREFIX+str(nm)+"/","limit":100,"offset":0},timeout=60)
    r.raise_for_status()
    names=sorted(x["name"] for x in r.json() if x.get("name","").endswith(".webp"))
    if not names:return []
    out=[]
    for i,name in enumerate(names,1):
        if not name.startswith(f"{i:02d}-"):raise Blocked("backup_numbering_invalid")
        path=quote(BUCKET+"/"+PREFIX+str(nm)+"/"+name,safe="/")
        rr=s.get(PROJECT_URL+"/storage/v1/object/authenticated/"+path,timeout=60)
        rr.raise_for_status()
        digest=hashlib.sha256(rr.content).hexdigest()
        if digest!=name.split("-",1)[1].split(".")[0]:raise Blocked("backup_sha_invalid")
        out.append(rr.content)
    return out

def same_images(left,right):
    return len(left)==len(right) and all(
      difference(thumb(x),thumb(y))<=10 for x,y in zip(left,right))

def slide_matches(images,slide):
    scores=[difference(thumb(slide),thumb(raw)) for raw in images]
    matched=[i+1 for i,s in enumerate(scores) if s<=10]
    if len(matched)>1:raise Blocked("multiple_matching_slides")
    if not matched and scores and min(scores)<15:raise Blocked("ambiguous_similar_slide")
    return matched

def check_identity(c,row):
    if c.get("nmID")!=int(row["nmID_WB_China"]) or c.get("vendorCode","").casefold()!=row["vendorCode"].casefold():
        raise Blocked("card_identity_changed")
    if c.get("video"):raise Blocked("video_card_must_not_be_written")
    if len(c.get("photos",[]))<6:raise Blocked("fewer_than_six_photos")

def save(s,rows,phase):
    key=os.environ["SUPABASE_SECRET_KEY"]
    h={"apikey":key,"Content-Type":"application/json","Prefer":"resolution=merge-duplicates"}
    if not key.startswith("sb_secret_"):h["Authorization"]="Bearer "+key
    now=dt.datetime.now(dt.timezone.utc)
    totals={status:sum(x["status"]==status for x in rows) for status in [
      "verified_at_7","skipped_duplicate","append_submitted","awaiting_reorder",
      "reorder_submitted","ERROR_STOP"]}
    body={"cache_key":JOURNAL,"payload":{"phase":phase,"targets":rows,"totals":totals},
          "updated_at":now.isoformat(),"expires_at":(now+dt.timedelta(days=30)).isoformat()}
    r=s.post(PROJECT_URL+"/rest/v1/telegram_api_cache?on_conflict=cache_key",headers=h,json=body,timeout=60)
    r.raise_for_status()

def confirm_plan(s,manifest):
    q=s.get(PROJECT_URL+"/rest/v1/telegram_api_cache",params={"cache_key":"eq."+RESULT_KEY,"select":"payload"},timeout=40)
    q.raise_for_status();res=q.json()
    if len(res)!=1:raise Blocked("preflight_not_found")
    plan=res[0]["payload"]
    if any(plan.get(k)!=v for k,v in {"status":"checked","mode":"read_only","ready":30,
       "blocked":15,"already_present":0}.items()):raise Blocked("unexpected_preflight_summary")
    expect={int(t["nmID"]):t for t in plan["targets"]}
    if {nm for nm,t in expect.items() if t["status"]=="ready_insert_at_7"}!=READY_IDS:
        raise Blocked("ready_target_set_mismatch")
    for row in manifest:
        nm=int(row["nmID_WB_China"])
        if nm in READY_IDS and expect[nm]["slide"]!=row["image"]:
            raise Blocked("slide_mapping_mismatch")

def staging(token,s,rows,assets):
    results=[]
    for row in rows:
        nm=int(row["nmID_WB_China"]);slide=assets[row["image"]]
        rec={"nmID":nm,"article":row["vendorCode"],"slide":row["image"]}
        try:
            c=read_nm(token,nm,retries=8)
            if c is None:raise Blocked("card_unavailable_before_append")
            check_identity(c,row)
            originals=get_photos(c)
            hits=slide_matches(originals,slide)
            back=backup(s,nm)
            rec["baseline_core"]=core(c)
            rec["before_count"]=len(back) if back else len(originals)
            if hits:
                pos=hits[0]
                rec["position"]=pos
                if pos==7:
                    if back and not same_images(back,originals[:6]+originals[7:]):
                        raise Blocked("existing_slide_original_photos_not_preserved")
                    rec["status"]="verified_at_7" if nm in {1473243914,1473243897} else "skipped_duplicate"
                elif back and pos==len(originals)==len(back)+1 and same_images(back,originals[:-1]):
                    rec["status"]="awaiting_reorder"
                else:
                    rec["status"]="skipped_duplicate"
            else:
                if back:
                    if not same_images(back,originals):raise Blocked("backup_existing_but_live_changed")
                    # A previous append might still be processing: never issue another.
                    raise Blocked("old_backup_without_visible_slide_no_safe_retry")
                if len(originals)>=MAX_MEDIA:raise Blocked("photo_limit")
                original_backup(s,nm,originals)
                current=read_nm(token,nm,retries=8)
                if current is None:raise Blocked("card_missing_before_append")
                if current.get("video") or core(current)!=core(c) or current.get("photos")!=c.get("photos"):
                    raise Blocked("concurrent_change_before_append")
                time.sleep(1)
                r=requests.post(WB_HOST+"/content/v3/media/file",
                   headers={"Authorization":token,"X-Nm-Id":str(nm),
                            "X-Photo-Number":str(len(originals)+1)},
                   files={"uploadfile":("approved.png",io.BytesIO(slide),"image/png")},timeout=100)
                if r.status_code!=200 or r.json().get("error") is not False:
                    raise Blocked("append_rejected_or_uncertain")
                rec["status"]="append_submitted";rec["append_at"]=time.time()
            results.append(rec)
            save(s,results,"staging")
            print("STAGE",nm,rec["status"],flush=True)
        except Exception as e:
            rec["status"]="ERROR_STOP";rec["reason"]=str(e) if isinstance(e,Blocked) else type(e).__name__
            results.append(rec);save(s,results,"stopped")
            print("STAGE_STOP",json.dumps(rec,ensure_ascii=False),flush=True)
            raise
    return results

def reorder(token,s,results,assets):
    start=time.time()
    while True:
        pending=[r for r in results if r["status"] in ("append_submitted","awaiting_reorder","reorder_submitted")]
        if not pending:
            save(s,results,"complete");return
        if time.time()-start>7200:
            raise Blocked("global_readback_deadline")
        changed=False
        for rec in pending:
            nm=rec["nmID"]
            try:
                c=read_nm(token,nm,retries=2)
                if c is None:continue
                row={"nmID_WB_China":str(nm),"vendorCode":rec["article"]}
                check_identity(c,row)
                if core(c)!=rec["baseline_core"]:raise Blocked("non_media_changed")
                live=get_photos(c)
                back=backup(s,nm)
                if len(back)!=rec["before_count"]:raise Blocked("backup_count_changed")
                hits=slide_matches(live,assets[rec["slide"]])
                if not hits:
                    if rec["status"]=="append_submitted" and len(live)==len(back) and same_images(back,live):
                        if time.time()-rec.get("append_at",start)>1800:raise Blocked("append_not_visible_after_30_minutes")
                        continue
                    raise Blocked("new_media_missing_or_invalid_count")
                pos=hits[0]
                if pos==7:
                    if len(live)!=len(back)+1 or not same_images(back,live[:6]+live[7:]):
                        raise Blocked("original_photos_differ_after_reorder")
                    rec["status"]="verified_at_7";rec["position"]=7
                    rec["photo_count_after"]=len(live)
                    rec.pop("baseline_core",None)
                    changed=True;save(s,results,"verifying")
                    print("VERIFIED",nm,len(live),flush=True)
                    continue
                if pos!=len(live) or len(live)!=len(back)+1 or not same_images(back,live[:-1]):
                    raise Blocked("unexpected_slide_position_or_old_photo_mismatch")
                if rec["status"]=="reorder_submitted":
                    if time.time()-rec.get("reorder_at",start)>1800:
                        raise Blocked("reorder_not_visible_after_30_minutes")
                    continue
                current=read_nm(token,nm,retries=5)
                if current is None or current.get("video") or core(current)!=core(c) or current.get("photos")!=c.get("photos"):
                    continue
                urls=[allowed_url(p) for p in current["photos"]]
                new_urls=urls[:6]+[urls[-1]]+urls[6:-1]
                if len(new_urls)!=len(set(new_urls)):raise Blocked("duplicate_urls")
                time.sleep(1)
                response=requests.post(WB_HOST+"/content/v3/media/save",
                    headers={"Authorization":token},json={"nmId":nm,"data":new_urls},timeout=100)
                if response.status_code!=200 or response.json().get("error") is not False:
                    raise Blocked("reorder_rejected_or_uncertain")
                rec["status"]="reorder_submitted";rec["reorder_at"]=time.time()
                changed=True;save(s,results,"reordering")
                print("REORDER_SENT",nm,flush=True)
            except Exception as e:
                rec["status"]="ERROR_STOP"
                rec["reason"]=str(e) if isinstance(e,Blocked) else type(e).__name__
                save(s,results,"stopped")
                print("REORDER_STOP",json.dumps(rec,ensure_ascii=False),flush=True)
                raise
        if not changed:time.sleep(30)

def main():
    if os.environ.get("NOEL_MEDIA_WRITE_APPROVED")!=APPROVAL:raise Blocked("approval_missing")
    if os.environ.get("GITHUB_REPOSITORY")!="Ekaterina11098/scheduled-worker":raise Blocked("wrong_runner")
    s=client();token=os.environ["WB_TOKEN_3"]
    manifest=validate_plan(Path(__file__).with_name("noelbag_media_manifest.csv"))
    rows=[r for r in manifest if int(r["nmID_WB_China"]) in READY_IDS]
    if len(rows)!=30:raise Blocked("ready_count_invalid")
    confirm_plan(s,manifest)
    assets=get_drive_assets(PROJECT_URL,{"apikey":os.environ["SUPABASE_SECRET_KEY"]})
    recs=staging(token,s,rows,assets)
    reorder(token,s,recs,assets)
    print("FINAL",json.dumps([{k:v for k,v in x.items() if k not in ("baseline_core","append_at","reorder_at")}
                 for x in recs],ensure_ascii=False),flush=True)
if __name__=="__main__":
    try:main()
    except Exception as e:
        print("STOPPED",str(e) if isinstance(e,Blocked) else type(e).__name__,file=sys.stderr)
        sys.exit(2)
