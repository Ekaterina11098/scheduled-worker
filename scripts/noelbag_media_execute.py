"""Owner-gated insert-after-six WB China media executor.
NOT imported or called by the read-only preflight workflow.
Requires an approved SHA256 of the latest live preflight and a separate opt-in.
"""
import hashlib, json, os, sys, time
from urllib.parse import quote
from pathlib import Path
import requests
from noelbag_media_insert7 import (Blocked,validate_plan,get_drive_assets,catalog,get_photos,
                                   classify,core,allowed_url,thumb,difference,EXPECTED_SHA,
                                   EXCLUDED,MAX_MEDIA,PROJECT_URL,WB_HOST,RESULT_KEY)
APPROVAL="APPROVED_NOELBAG_45_INSERT_AT_POSITION_7"
BUCKET="owner-media-recovery"
PREFIX="noelbag-insert7-approved/v1/"
def client():
    key=os.environ["SUPABASE_SECRET_KEY"]
    s=requests.Session();s.headers["apikey"]=key
    if not key.startswith("sb_secret_"):s.headers["Authorization"]="Bearer "+key
    return s
def original_backup(s,nm,pics):
    for i,raw in enumerate(pics,1):
        path=f"{PREFIX}backup/{nm}/{i:02d}-{hashlib.sha256(raw).hexdigest()}.webp"
        dest=quote(BUCKET+"/"+path,safe="/")
        result=s.post(PROJECT_URL+"/storage/v1/object/"+dest,data=raw,headers={"x-upsert":"false","Content-Type":"image/webp"},timeout=60)
        if not result.ok and "exist" not in result.text.lower():raise Blocked("backup_storage_failed")
        chk=s.get(PROJECT_URL+"/storage/v1/object/authenticated/"+dest,timeout=60)
        if not chk.ok or hashlib.sha256(chk.content).digest()!=hashlib.sha256(raw).digest():raise Blocked("backup_hash_failed")
def slide_url(s,name,raw):
    path=f"{PREFIX}approved/{EXPECTED_SHA[name]}.png";dest=quote(BUCKET+"/"+path,safe="/")
    response=s.post(PROJECT_URL+"/storage/v1/object/"+dest,data=raw,headers={"x-upsert":"false","Content-Type":"image/png"},timeout=60)
    if not response.ok and "exist" not in response.text.lower():raise Blocked("approved_slide_storage_failed")
    chk=s.get(PROJECT_URL+"/storage/v1/object/authenticated/"+dest,timeout=60)
    if not chk.ok or hashlib.sha256(chk.content).hexdigest()!=EXPECTED_SHA[name]:raise Blocked("approved_slide_hash_failed")
    signed=s.post(PROJECT_URL+"/storage/v1/object/sign/"+dest,json={"expiresIn":3600},timeout=60)
    signed.raise_for_status();p=signed.json()["signedURL"]
    if not p.startswith("/object/sign/"+BUCKET+"/"):raise Blocked("signed_path_invalid")
    return PROJECT_URL+"/storage/v1"+p
def read_nm(token,nm):
    hits=[c for c in catalog(token) if c.get("nmID")==nm]
    if len(hits)!=1:raise Blocked("card_missing_or_ambiguous")
    return hits[0]
def check_after(token,before,oldraw,slide):
    for _ in range(12):
        time.sleep(15)
        after=read_nm(token,before["nmID"])
        if core(after)!=core(before) or after.get("video")!=before.get("video"):raise Blocked("non_media_changed")
        current=get_photos(after)
        if len(current)!=len(oldraw)+1:continue
        st=classify(after,before["vendorCode"],before["nmID"],slide,current)
        if st.get("status")!="already_present" or st.get("position")!=7:continue
        original=current[:6]+current[7:]
        if len(original)==len(oldraw) and all(difference(thumb(a),thumb(b))<=10 for a,b in zip(original,oldraw)):
            return True
    raise Blocked("media_readback_uncertain_no_retry")
def run(approved_sha):
    if os.environ.get("NOEL_MEDIA_WRITE_APPROVED")!=APPROVAL:raise Blocked("owner_approval_missing")
    s=client()
    rr=s.get(PROJECT_URL+"/rest/v1/telegram_api_cache",params={"cache_key":"eq."+RESULT_KEY,"select":"payload"},timeout=40)
    rr.raise_for_status();recs=rr.json()
    if len(recs)!=1:raise Blocked("private_preflight_missing")
    plan=recs[0]["payload"]
    raw=json.dumps(plan,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    if hashlib.sha256(raw).hexdigest()!=approved_sha:raise Blocked("approved_plan_sha_mismatch")
    if plan.get("status")!="checked" or plan.get("mode")!="read_only" or plan.get("blocked")!=0:raise Blocked("preflight_blocked")
    manifest=Path(__file__).with_name("noelbag_media_manifest.csv")
    rows=validate_plan(manifest);token=os.environ["WB_TOKEN_3"]
    headers={"apikey":os.environ["SUPABASE_SECRET_KEY"],"Content-Type":"application/json"}
    if not headers["apikey"].startswith("sb_secret_"):headers["Authorization"]="Bearer "+headers["apikey"]
    assets=get_drive_assets(PROJECT_URL,headers)
    latest={c["nmID"]:c for c in catalog(token)}
    expected={d["nmID"]:(d["status"],d.get("photo_count")) for d in plan["targets"]}
    for r in rows:
        nm=int(r["nmID_WB_China"])
        if nm==EXCLUDED:continue
        before=latest.get(nm)
        if not before:raise Blocked("card_missing_since_preflight")
        check=classify(before,r["vendorCode"],nm,assets[r["image"]],get_photos(before))
        if (check["status"],check["photo_count"])!=expected[nm]:raise Blocked("card_state_changed_since_preflight")
    b=s.get(PROJECT_URL+"/storage/v1/bucket/"+BUCKET,timeout=40)
    b.raise_for_status()
    if b.json().get("public") is not False:raise Blocked("bucket_must_be_private")
    signed={n:slide_url(s,n,blob) for n,blob in assets.items()}
    results=[]
    for r in rows:
        nm=int(r["nmID_WB_China"])
        if nm==EXCLUDED:
            results.append({"nmID":nm,"status":"owner_excluded"});continue
        before=read_nm(token,nm);oldraw=get_photos(before)
        state=classify(before,r["vendorCode"],nm,assets[r["image"]],oldraw)
        if state["status"]=="already_present":
            results.append({"nmID":nm,"status":"already_present"});continue
        if state["status"]!="ready_insert_at_7" or len(oldraw)+1>MAX_MEDIA:raise Blocked("insert_not_safe")
        original_backup(s,nm,oldraw)
        newer=read_nm(token,nm)
        if newer.get("photos")!=before.get("photos") or core(newer)!=core(before) or newer.get("video")!=before.get("video"):
            raise Blocked("concurrent_change")
        old=[allowed_url(p) for p in before["photos"]]
        urls=old[:6]+[signed[r["image"]]]+old[6:]
        resp=requests.post(WB_HOST+"/content/v3/media/save",headers={"Authorization":token},
                           json={"nmId":nm,"data":urls},timeout=90)
        if resp.status_code!=200 or resp.json().get("error") is not False:raise Blocked("media_save_rejected_or_uncertain")
        check_after(token,before,oldraw,assets[r["image"]])
        results.append({"nmID":nm,"status":"readback_verified"})
    return results
if __name__=="__main__":
    try:
        if len(sys.argv)!=2 or len(sys.argv[1])!=64:raise Blocked("approved_sha_argument_required")
        print(json.dumps(run(sys.argv[1])))
    except Exception as e:
        print("STOPPED",str(e) if isinstance(e,Blocked) else type(e).__name__,file=sys.stderr)
        raise SystemExit(2)
