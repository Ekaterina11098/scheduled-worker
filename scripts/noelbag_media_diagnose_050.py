"""Read-only diagnostic of partially executed 50-NoelBag-yellow."""
import os,json,time,hashlib
import requests
from urllib.parse import quote
from noelbag_media_insert7 import (PROJECT_URL,WB_HOST,EXPECTED_SHA,get_drive_assets,get_photos,
 thumb,difference,core,allowed_url)
from noelbag_media_execute import client
NM=1473243824
PREFIX="noelbag-insert7-approved/v1/backup/1473243824/"
BUCKET="owner-media-recovery"
REPORT_KEY="noelbag_media_insert7:v2:diagnose_050"

def direct_card(token):
    for attempt in range(5):
        req={"settings":{"sort":{"ascending":False},"cursor":{"limit":100},
                           "filter":{"withPhoto":-1,"textSearch":str(NM)}}}
        response=requests.post(WB_HOST+"/content/v2/get/cards/list",
              headers={"Authorization":token},json=req,timeout=90)
        response.raise_for_status();data=response.json()
        pages=data.get("cards") or data.get("data",{}).get("cards") or []
        matches=[c for c in pages if c.get("nmID")==NM]
        if len(matches)==1:return matches[0]
        time.sleep(10)
    raise RuntimeError("specific_card_not_available_after_five_reads")

def get_backup(s):
    q=s.post(PROJECT_URL+"/storage/v1/object/list/"+BUCKET,
       json={"prefix":PREFIX,"limit":100,"offset":0},timeout=60)
    q.raise_for_status()
    entries=sorted(q.json(),key=lambda x:x["name"])
    if len(entries)!=15:raise RuntimeError("expected_15_backups_missing")
    out=[]
    for i,x in enumerate(entries,1):
        name=x["name"]
        if not name.startswith(f"{i:02d}-"):raise RuntimeError("backup_order_invalid")
        path=quote(BUCKET+"/"+PREFIX+name,safe="/")
        resp=s.get(PROJECT_URL+"/storage/v1/object/authenticated/"+path,timeout=60)
        resp.raise_for_status()
        if hashlib.sha256(resp.content).hexdigest()!=name.split("-",1)[1].split(".")[0]:
            raise RuntimeError("backup_digest_invalid")
        out.append(resp.content)
    return out

def save(s,obj):
    k=os.environ["SUPABASE_SECRET_KEY"]
    h={"apikey":k,"Prefer":"resolution=merge-duplicates","Content-Type":"application/json"}
    if not k.startswith("sb_secret_"):h["Authorization"]="Bearer "+k
    import datetime as dt
    now=dt.datetime.now(dt.timezone.utc)
    b={"cache_key":REPORT_KEY,"payload":obj,"updated_at":now.isoformat(),
       "expires_at":(now+dt.timedelta(days=10)).isoformat()}
    res=s.post(PROJECT_URL+"/rest/v1/telegram_api_cache?on_conflict=cache_key",headers=h,json=b,timeout=50)
    res.raise_for_status()

def main():
    s=client()
    assets=get_drive_assets(PROJECT_URL,{"apikey":os.environ["SUPABASE_SECRET_KEY"]})
    before=get_backup(s)
    c=direct_card(os.environ["WB_TOKEN_3"])
    if c.get("vendorCode","").casefold()!="50-noelbag-yellow" or c.get("video"):
        raise RuntimeError("identity_or_video_mismatch")
    live=get_photos(c)
    score=[difference(thumb(assets["1.png"]),thumb(p)) for p in live]
    matches=[i+1 for i,v in enumerate(score) if v<=10]
    retained=([i for i in range(len(live)) if (i+1) not in matches])
    after=[live[i] for i in retained]
    old_match=len(after)==15 and all(difference(thumb(x),thumb(y))<=10 for x,y in zip(before,after))
    result={"nmID":NM,"article":c["vendorCode"],"photos":len(live),
       "slide_match_positions":matches,"old_18_order_and_pixels_retained":old_match,
       "score_min":round(min(score),3),"video_present":bool(c.get("video")),
       "safe_to_resume":len(matches)==1 and old_match and len(live)==16}
    save(s,result)
    print("READONLY_DIAG_050",json.dumps(result),flush=True)
if __name__=="__main__":main()
