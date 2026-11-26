"""Read current WB China media for one exact article using the existing worker."""
import hashlib
import io
import json
import os
import re
import time
import zipfile

import requests
from PIL import Image, ImageChops, ImageStat
from content_photo_drive import Delivery

from content_photo_bridge import Stop, photo_url


def inspect_card(client, vendor_code, expected_nm_id=None):
    if not isinstance(vendor_code, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", vendor_code
    ):
        raise Stop("invalid_vendor_code")

    matches = [
        card for card in client.catalog() if card.get("vendorCode") == vendor_code
    ]
    if len(matches) != 1:
        raise Stop("card_not_found" if not matches else "ambiguous_vendor_code")

    card = matches[0]
    nm_id = card.get("nmID")
    if type(nm_id) is not int or nm_id <= 0:
        raise Stop("invalid_nm_id")
    if expected_nm_id is not None and nm_id != expected_nm_id:
        raise Stop("nm_id_mismatch")

    photos = card.get("photos", [])
    video = card.get("video")
    if not isinstance(photos, list) or not all(
        isinstance(photo, dict) and photo for photo in photos
    ):
        raise Stop("invalid_photo_list")
    if video is not None and not isinstance(video, str):
        raise Stop("unsupported_video_field")

    return {
        "vendorCode": vendor_code,
        "nmID": nm_id,
        "photos": photos,
        "photo_field_present": "photos" in card,
        "video": video,
        "video_field_present": "video" in card,
    }

def load_bundle(client, file_id, checksum, vendor_code):
    if not re.fullmatch(r"[A-Za-z0-9_-]{10,150}", file_id or ""):
        raise Stop("invalid_bundle_id")
    if not re.fullmatch(r"[a-f0-9]{64}", checksum or ""):
        raise Stop("invalid_bundle_checksum")
    credentials = json.loads(client.call(
        client.base + "/rest/v1/rpc/content_photo_drive_credentials", "POST", {}
    ))
    drive = Delivery(credentials, requests.request)
    drive.refresh()
    metadata = drive.metadata(file_id)
    if metadata.get("trashed") or credentials["folder_id"] not in metadata.get("parents", []):
        raise Stop("bundle_folder_mismatch")
    with drive.call("GET", "https://www.googleapis.com/drive/v3/files/" + file_id,
                    params={"alt": "media"}, stream=True) as response:
        if response.status_code != 200:
            raise Stop("bundle_download_failed")
        payload = bytearray()
        for chunk in response.iter_content(64 * 1024):
            payload.extend(chunk)
            if len(payload) > 40 * 1024 * 1024:
                raise Stop("bundle_size_limit")
    if hashlib.sha256(payload).hexdigest() != checksum:
        raise Stop("bundle_checksum_mismatch")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        files = sorted(archive.infolist(), key=lambda entry: entry.filename)
        if not 1 <= len(files) <= 30 or sum(entry.file_size for entry in files) > 40 * 1024 * 1024:
            raise Stop("invalid_bundle_size")
        expected = [f"{vendor_code}_{index:02}.png" for index in range(1, len(files) + 1)]
        if [entry.filename for entry in files] != expected:
            raise Stop("invalid_bundle_order")
        return [archive.read(entry) for entry in files]


def image_signature(raw, png_required=False):
    with Image.open(io.BytesIO(raw)) as image:
        if png_required and (
            image.format != "PNG" or image.width < 700 or image.height < 900
            or image.width * image.height > 25_000_000 or len(raw) > 10 * 1024 * 1024
        ):
            raise Stop("invalid_slide")
        return image.convert("RGB").resize((96, 128), Image.Resampling.LANCZOS)


def same_image(left, right):
    return sum(ImageStat.Stat(ImageChops.difference(left, right)).mean) / 3 <= 3


def append_media(client, request, request_id, mark_write_pending):
    article = request.get("vendorCode")
    current = inspect_card(client, article, request.get("nmID"))
    if current["video"]:
        raise Stop("video_present_needs_verified_preservation")
    files = load_bundle(client, request.get("driveFileId"), request.get("sha256"), article)
    slides = [image_signature(raw, png_required=True) for raw in files]
    if any(same_image(left, right) for i, left in enumerate(slides) for right in slides[i + 1:]):
        raise Stop("duplicate_uploaded_slides")

    def read_signatures(urls):
        return [image_signature(client.call(url, limit=32 * 1024 * 1024, auth=False)) for url in urls]

    old_urls = [photo_url(photo) for photo in current["photos"]]
    old = read_signatures(old_urls)
    if len(old) >= len(slides) and all(
        same_image(left, right) for left, right in zip(old[-len(slides):], slides)
    ) and not any(same_image(slide, earlier) for slide in slides for earlier in old[:-len(slides)]):
        return {"outcome": "already_present", "nmID": current["nmID"], "photo_count": len(old), "wb_writes": 0}
    if any(same_image(slide, photo) for slide in slides for photo in old):
        raise Stop("existing_slide_outside_expected_sequence")
    if len(slides) + len(old) > 30:
        raise Stop("wb_photo_limit")

    staged_urls = []
    for index, raw in enumerate(files, 1):
        path = f"content-photo-bridge/v1/media-inbox/{request_id}/{index:02}.png"
        client.storage_upload(path, raw, "image/png")
        url = client.signed_url(path)
        if client.call(url, auth=False) != raw:
            raise Stop("staged_media_mismatch")
        staged_urls.append(url)
    if inspect_card(client, article, current["nmID"]) != current:
        raise Stop("media_changed_before_write")

    mark_write_pending()
    response = json.loads(client.call(
        "https://content-api.wildberries.cn/content/v3/media/save", "POST",
        {"nmId": current["nmID"], "data": old_urls + staged_urls},
        {"Authorization": os.environ["WB_TOKEN_3"]}, limit=128 * 1024, auth=False,
    ))
    if response.get("error") is not False:
        raise Stop("wb_rejected_media_save")
    expected = old + slides
    for delay in (5, 15, 30, 45, 60):
        time.sleep(delay)
        actual = inspect_card(client, article, current["nmID"])
        if actual["video"] or len(actual["photos"]) != len(expected):
            continue
        observed = read_signatures([photo_url(photo) for photo in actual["photos"]])
        if all(same_image(left, right) for left, right in zip(expected, observed)):
            prior = observed[:len(old)]
            if not any(same_image(slide, photo) for slide in slides for photo in prior):
                return {"outcome": "verified", "nmID": current["nmID"],
                        "photo_count": len(observed), "wb_writes": 1}
    raise Stop("wb_write_sent_readback_unverified")
