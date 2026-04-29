#!/usr/bin/env python3
import requests, re
def _parse_duration_value(v):
    if v is None: return None
    s = str(v).strip().replace(",", "")
    if s == "": return None
    if re.match(r'^\d+(\.\d+)?$', s): return int(float(s))
    parts = s.split(':')
    if all(re.match(r'^\d+(\.\d+)?$', p) for p in parts):
        secs = 0.0
        for p in parts:
            secs = secs*60 + float(p)
        return int(secs)
    return None

r = requests.get("https://archive.org/metadata/mmm-251", timeout=10)
r.raise_for_status()
data = r.json()
for f in data.get("files", []):
    name = f.get("name")
    if not name or not name.lower().endswith((".mp3",".m4a",".ogg",".flac",".wav")):
        continue
    print("=== FILE ===")
    print("name:", name)
    print("raw size:", f.get("size"))
    print("raw format:", f.get("format"))
    print("raw length/playtime/duration keys:")
    for k in ("length","playtime","duration","play_length","tracklength","time"):
        if k in f:
            print(f"  {k} -> {f[k]!r}")
    # test parser on each possible key
    for k in ("length","playtime","duration","play_length","tracklength","time"):
        v = f.get(k)
        if v is not None:
            print(f" parsed from {k}: {_parse_duration_value(v)} seconds")
    # also try format string
    fmt = f.get("format","")
    m = re.search(r'(\d+:\d{2}(?::\d{2})?)', str(fmt))
    if m:
        print(" parsed from format:", _parse_duration_value(m.group(1)))
    print()
