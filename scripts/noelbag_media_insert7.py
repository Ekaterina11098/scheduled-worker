"""NoelBag China insertion at #7: READ-ONLY live preflight.
No WB media update operations or image-generation calls in this module.
Private source PNGs live in the single owner-authorized Drive folder.
"""
import base64, csv, hashlib, io, json, os, re, time
from pathlib import Path
from PIL import Image, ImageChops, ImageOps, ImageStat
import requests
from content_photo_drive import Delivery, FOLDER, DriveError

WB_HOST = "https://content-api.wildberries.cn"
PROJECT_URL = "https://abxgjoqlddhtcmjcjwxw.supabase.co"
RESULT_KEY = "noelbag_media_insert7:v1:live_preflight"
EXCLUDED = 1473243891
MAX_MEDIA = 30
DRIVE_IDS = {
    "1.png": "1amM9fLYhQbT6mMLKQ1rvp4vNGdyKUV--",
    "2(1).png": "1_0Ks3PLZ6hRfiiHlT36KfUy3mvtsrOtj",
    "3.png": "18g6mHdnftWSM_-B_l2Y1gRiUMuKybb3j",
    "4.png": "123BlcRrfJfFT3N0rO84z0hdYrejg5vDo",
}
EXPECTED_SHA = {
    "1.png": "c6ac2d1d5fd7e1037363097f70624ec6bb3260c6707af1289db856fbcd61b1ac",
    "2(1).png": "7481f3dd873f40b6252ff9faac03fde06ab57a104a85bbc10c09bde67f05f294",
    "3.png": "b65188133328a05688681165cb1e406e89c929cb1e9842c114dbfee2b4d3ccf0",
    "4.png": "6455bd8028f59a647ae5cd99bbb6a01e9cd5f22ef1f9c5270f973a10d6cf7a37",
}
class Blocked(Exception): pass
def digest(raw): return hashlib.sha256(raw).hexdigest()
def validate_plan(path):
    with open(path,encoding="utf-8-sig",newline="") as f: rows=list(csv.DictReader(f))
    if len(rows)!=46 or len({int(r["nmID_WB_China"]) for r in rows})!=46: raise Blocked("invalid_46_row_manifest")
    if {r["image"] for r in rows}!=set(DRIVE_IDS): raise Blocked("asset_set_mismatch")
    if any(r["drive_file_id"]!=DRIVE_IDS[r["image"]] for r in rows): raise Blocked("drive_manifest_id_mismatch")
    if any(not r.get("vendorCode") or r.get("drive_file_id") is None for r in rows): raise Blocked("manifest_vendor_or_drive_missing")
    if sum(int(r["nmID_WB_China"])==EXCLUDED for r in rows)!=1: raise Blocked("excluded_id_missing")
    for r in rows:
        n=int(r["nmID_WB_China"]);name=r["image"]
        if r["image_sha256"]!=EXPECTED_SHA[name] or r["target_position"]!="7" or r["insert_after_existing_photo"]!="6":raise Blocked("manifest_mismatch")
        if r["action"]!=("skip" if n==EXCLUDED else "pending_upload"):raise Blocked("wrong_exclusion")
    return rows
def core(card):
    d={k:v for k,v in card.items() if k not in ("photos","video","updatedAt")}
    d["characteristics"]=sorted(d.get("characteristics",[]),key=lambda x:str(x.get("id")))
    return d
def allowed_url(p):
    url=p.get("big") or p.get("c516x688")
    from urllib.parse import urlsplit
    u=urlsplit(url or "")
    if u.scheme!="https" or not re.fullmatch(r"basket-\d+\.(wbbasket\.ru|wbcontent\.net)",u.hostname or ""):
        raise Blocked("unexpected_cdn_host")
    if not re.fullmatch(r"/vol\d+/part\d+/\d+/images/(big|c516x688)/\d+\.(webp|jpg|jpeg|png)",u.path) or u.query or u.fragment:
        raise Blocked("unexpected_cdn_path")
    return url
def thumb(raw):
    with Image.open(io.BytesIO(raw)) as im:
        im.load()
        return ImageOps.fit(im.convert("RGB"),(96,128),method=Image.Resampling.LANCZOS)
def difference(a,b):
    return sum(ImageStat.Stat(ImageChops.difference(a,b)).mean)/3
def classify(card,article,nm,slide,raw_images):
    if card.get("nmID")!=nm or card.get("vendorCode","").casefold()!=article.casefold():raise Blocked("card_identity_mismatch")
    if card.get("video"):raise Blocked("video_requires_review")
    photos=card.get("photos")
    if not isinstance(photos,list) or len(photos)<6 or len(photos)!=len(raw_images):raise Blocked("invalid_existing_photo_count")
    score=[difference(thumb(slide),thumb(b)) for b in raw_images]
    matches=[i+1 for i,d in enumerate(score) if d<=10]
    if len(matches)>1:raise Blocked("multiple_existing_slides")
    if len(matches)==1:
        return {"status":"already_present","position":matches[0],"photo_count":len(photos)}
    if score and min(score)<15:raise Blocked("ambiguous_duplicate")
    if len(photos)>=MAX_MEDIA:raise Blocked("photo_limit")
    return {"status":"ready_insert_at_7","photo_count":len(photos),"expected_count":len(photos)+1,"first_six_preserved":True,"tail_preserved":True}
def get_drive_assets(supa,headers):
    """Import uploaded approved PNG bytes from private Supabase cache chunks.
    This avoids widening the existing drive.file OAuth scope, and never
    exposes images in public GitHub or passes WB credentials to file hosts.
    """
    outputs={}
    expected_sizes={"1.png":2845650,"2(1).png":2846589,
                    "3.png":2708000,"4.png":2701248}
    for number,name in enumerate(("1.png","2(1).png","3.png","4.png"),1):
        prefix=f"noelbag_media_insert7:v1:asset:{number}:"
        response=requests.get(PROJECT_URL+"/rest/v1/telegram_api_cache",
            headers=headers,params={"cache_key":"like."+prefix+"*",
                "select":"cache_key,payload","order":"cache_key.asc","limit":20},timeout=100)
        response.raise_for_status()
        rows=response.json()
        if len(rows)!=10:raise Blocked("private_asset_chunks_missing_"+name)
        parts=[]
        for i,row in enumerate(rows):
            if row.get("cache_key")!=prefix+str(i).zfill(3):
                raise Blocked("private_asset_chunk_order_invalid_"+name)
            data=row.get("payload",{})
            if data.get("index")!=i or data.get("total")!=10 or data.get("sha256")!=EXPECTED_SHA[name]:
                raise Blocked("private_asset_chunk_metadata_invalid_"+name)
            parts.append(data["b64"])
        raw=base64.b64decode("".join(parts),validate=True)
        if len(raw)!=expected_sizes[name] or digest(raw)!=EXPECTED_SHA[name]:
            raise Blocked("private_asset_hash_invalid_"+name)
        with Image.open(io.BytesIO(raw)) as image:
            if image.format!="PNG" or image.size!=(1086,1448):
                raise Blocked("private_asset_dimensions_invalid_"+name)
            image.verify()
        outputs[name]=raw
    return outputs
def catalog(token):
    session=requests.Session();session.headers.update({"Authorization":token})
    cur={"limit":100};out=[];seen=set()
    for _ in range(40):
        response=session.post(WB_HOST+"/content/v2/get/cards/list",json={"settings":{"sort":{"ascending":True},"cursor":cur,"filter":{"withPhoto":-1}}},timeout=90)
        if response.status_code==429:raise Blocked("wb_rate_limited")
        response.raise_for_status()
        val=response.json();val=val.get("data",val) if "cards" not in val else val
        page=val["cards"];out.extend(page)
        if len(page)<100:return out
        k=(val["cursor"]["updatedAt"],val["cursor"]["nmID"])
        if k in seen:raise Blocked("pagination_loop")
        seen.add(k);cur={"limit":100,"updatedAt":k[0],"nmID":k[1]}
        time.sleep(1)
    raise Blocked("pagination_limit")
def get_photos(card):
    out=[]
    for photo in card["photos"]:
        url=allowed_url(photo)
        resp=requests.get(url,timeout=60,allow_redirects=False)
        if resp.status_code!=200:raise Blocked("image_cdn_download_failed")
        thumb(resp.content)
        out.append(resp.content)
    return out
def save_report(report):
    key=os.environ["SUPABASE_SECRET_KEY"]
    head={"apikey":key,"Content-Type":"application/json","Prefer":"resolution=merge-duplicates,return=representation"}
    if not key.startswith("sb_secret_"):head["Authorization"]="Bearer "+key
    import datetime as dt
    now=dt.datetime.now(dt.timezone.utc)
    body={"cache_key":RESULT_KEY,"payload":report,"updated_at":now.isoformat(),
          "expires_at":(now+dt.timedelta(days=30)).isoformat()}
    r=requests.post(PROJECT_URL+"/rest/v1/telegram_api_cache?on_conflict=cache_key",headers=head,json=body,timeout=50)
    r.raise_for_status()
    rb=requests.get(PROJECT_URL+"/rest/v1/telegram_api_cache",headers=head,params={"cache_key":"eq."+RESULT_KEY,"select":"payload"},timeout=30)
    rb.raise_for_status()
    if rb.json()[0]["payload"]!=report:raise Blocked("private_result_readback_failed")
def preflight(rows,assets,cards,photo_fetcher):
    byid={}
    for c in cards:
        n=c.get("nmID")
        if n in byid:raise Blocked("duplicate_nmID_in_catalog")
        byid[n]=c
    targets=[];excluded=[]
    for row in rows:
        n=int(row["nmID_WB_China"])
        if n==EXCLUDED:
            excluded.append(n);continue
        card=byid.get(n)
        if not card:
            targets.append({"nmID":n,"status":"blocked","reason":"missing_card"});continue
        try:
            original=photo_fetcher(card)
            state=classify(card,row["vendorCode"],n,assets[row["image"]],original)
            targets.append({"nmID":n,"article":card["vendorCode"],"slide":row["image"],**state})
        except Exception as e:
            targets.append({"nmID":n,"article":card.get("vendorCode"),"slide":row["image"],
                            "status":"blocked","reason":str(e) if isinstance(e,Blocked) else type(e).__name__})
    return {"status":"checked","mode":"read_only","wb_writes":0,"scanned_cards":len(cards),
            "targets":targets,"excluded":excluded,
            "ready":sum(x["status"]=="ready_insert_at_7" for x in targets),
            "already_present":sum(x["status"]=="already_present" for x in targets),
            "blocked":sum(x["status"]=="blocked" for x in targets)}
def main():
    assert os.environ.get("GITHUB_REPOSITORY")=="Ekaterina11098/scheduled-worker","wrong_runner"
    rows=validate_plan(Path(__file__).with_name("noelbag_media_manifest.csv"))
    if not os.environ.get("WB_TOKEN_3"):raise Blocked("wb_token_not_available")
    key=os.environ["SUPABASE_SECRET_KEY"]
    h={"apikey":key,"Content-Type":"application/json"}
    if not key.startswith("sb_secret_"):h["Authorization"]="Bearer "+key
    assets=get_drive_assets(PROJECT_URL,h)
    report=preflight(rows,assets,catalog(os.environ["WB_TOKEN_3"]),get_photos)
    report["assets"]={n:{"sha256":digest(b),"bytes":len(b)} for n,b in assets.items()}
    save_report(report)
    print("READ_ONLY_NOEL_PREFLIGHT",json.dumps({k:v for k,v in report.items() if k!="targets"},ensure_ascii=False))
    print("PER_CARD",json.dumps(report["targets"],ensure_ascii=False))
if __name__=="__main__":
    try:main()
    except Exception as e:
        code=str(e) if isinstance(e,(Blocked,DriveError)) else type(e).__name__
        print("READ_ONLY_NOEL_PREFLIGHT_BLOCKED",re.sub(r"[^a-zA-Z0-9_-]","",code)[:100])
        raise SystemExit(2)
