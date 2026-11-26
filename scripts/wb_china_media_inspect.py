"""Read current WB China media for one exact article using the existing worker."""
import re

from content_photo_bridge import Stop


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
