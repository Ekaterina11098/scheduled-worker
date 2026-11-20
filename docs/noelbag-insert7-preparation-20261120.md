# NoelBag China photo #7 — draft preparation, 20.11.2026

NO EXECUTION AUTHORIZED. No WB media changes, no workflow dispatch, no changes to main or schedules.

The standalone implementation bundle has been produced and offline-tested in the owner's ChatGPT photo conversation as `NoelBag_insert7_preflight_code.zip`. It includes:
- `noelbag_media_insert7.py` (manifest + sha256 checks; offline and read-only preflight)
- `noelbag_media_execute.py` (separately gated writer; NEVER invoked by the draft)
- `test_noelbag_media_insert7.py` (11 passing mock/unit tests)
- `noelbag_media_manifest.csv` and `NoelBag_45_targets_only.csv`
- `noelbag-media-preflight.yml` (manual test-only workflow), README and report.

DO NOT MERGE OR RUN ANY WRITER until all files are reviewed and added to the runner, four owner-approved PNGs are privately staged, a fresh complete-paginated preflight reads all 45 cards, current photos are compared against the expected slide and the owner explicitly approves the live preflight SHA-256.

Target: 45 NoelBag China nmIDs, excluding `0-NoelBag-green` / `1473243891`. Insert exactly one corresponding approved slide after old photo #6, preserve order of every other image, skip already-present gallery slide. Media/save replaces the whole image list, hence include existing image URLs in the intended order. Reread non-media fields, dimensions, characteristics, barcodes, title, description and video before/after; stop on conflicts or ambiguous readback. No card content update endpoint.

This README intentionally does not contain owner artwork or secrets. The scripts are in the handoff ZIP, not yet installed in this draft branch.
