#!/usr/bin/env python3
"""Export the X/Twitter handles of every account a Farcaster FID follows.

Uses the hub-style HTTP API on a Hypersnap node:
  /v1/linksByFid    -> follow targets (paginated by pageToken)
  /v1/userDataByFid -> profile data, incl. USER_DATA_TYPE_TWITTER

The X handle is self-declared by each user in their profile; it is not verified.

Usage: python3 fetch_x_handles.py [FID] [OUT_CSV]
"""
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

NODE = "https://haatz.quilibrium.com"


def get(path, params, retries=5):
    url = f"{NODE}{path}?{urllib.parse.urlencode(params)}"
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.load(r)
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2**attempt)


def following_fids(fid):
    fids, token = [], None
    while True:
        params = {"fid": fid, "link_type": "follow", "pageSize": 1000}
        if token:
            params["pageToken"] = token
        page = get("/v1/linksByFid", params)
        for m in page.get("messages", []):
            body = m["data"].get("linkBody", {})
            if m["data"]["type"] == "MESSAGE_TYPE_LINK_ADD" and body.get("type") == "follow":
                fids.append(body["targetFid"])
        token = page.get("nextPageToken")
        if not token:
            break
    return list(dict.fromkeys(fids))


def profile(fid):
    data = get("/v1/userDataByFid", {"fid": fid})
    fields = {m["data"]["userDataBody"]["type"]: m["data"]["userDataBody"]["value"]
              for m in data.get("messages", [])}
    return {
        "fid": fid,
        "username": fields.get("USER_DATA_TYPE_USERNAME", ""),
        "display_name": fields.get("USER_DATA_TYPE_DISPLAY", ""),
        "x_handle": fields.get("USER_DATA_TYPE_TWITTER", "").strip().lstrip("@"),
    }


def main():
    fid = int(sys.argv[1]) if len(sys.argv) > 1 else 1689
    out = sys.argv[2] if len(sys.argv) > 2 else f"following_x_handles_{fid}.csv"

    fids = following_fids(fid)
    print(f"FID {fid} follows {len(fids)} accounts", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=16) as pool:
        rows = list(pool.map(profile, fids))

    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["fid", "username", "display_name", "x_handle", "x_url"])
        w.writeheader()
        for r in rows:
            r["x_url"] = f"https://x.com/{r['x_handle']}" if r["x_handle"] else ""
            w.writerow(r)

    with_x = sum(1 for r in rows if r["x_handle"])
    print(f"{with_x}/{len(rows)} have an X handle set -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
