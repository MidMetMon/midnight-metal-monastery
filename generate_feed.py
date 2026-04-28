import subprocess

def _parse_duration_value(v):
    if v is None:
        return None
    s = str(v).strip()
    if s == "":
        return None
    s = s.replace(",", "")
    # plain numeric seconds (int or float)
    if re.match(r'^\d+(\.\d+)?$', s):
        return int(float(s))
    # colon formats hh:mm:ss or mm:ss or mm:ss.msec
    parts = s.split(':')
    if all(re.match(r'^\d+(\.\d+)?$', p) for p in parts):
        secs = 0.0
        for p in parts:
            secs = secs * 60 + float(p)
        return int(secs)
    return None

def _size_to_bytes(size):
    if size is None:
        return 0
    if isinstance(size, (int, float)):
        return int(size)
    s = str(size).strip().replace(",", "").upper()
    m = re.match(r'^(\d+(\.\d+)?)([KMGTP])?B?$', s)
    if m:
        val = float(m.group(1))
        unit = m.group(3)
        mul = {'K':1024, 'M':1024**2, 'G':1024**3, 'T':1024**4, 'P':1024**5}.get(unit,1)
        return int(val * mul)
    try:
        return int(float(s))
    except:
        return 0

def _mime_for_filename(name, fmt_hint=None):
    ext = name.split('.')[-1].lower()
    if ext == 'mp3': return 'audio/mpeg'
    if ext in ('m4a','mp4','aac'): return 'audio/mp4'
    if ext == 'ogg': return 'audio/ogg'
    if ext == 'flac': return 'audio/flac'
    if ext == 'wav': return 'audio/wav'
    if fmt_hint and 'mp3' in str(fmt_hint).lower(): return 'audio/mpeg'
    return 'application/octet-stream'

def get_audio_files(item_id, use_ffprobe=False, ffprobe_path='ffprobe'):
    url = f"https://archive.org/metadata/{item_id}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        audio_files = []
        for file_info in data.get("files", []):
            filename = file_info.get("name","")
            if not filename.lower().endswith((".mp3", ".m4a", ".ogg", ".flac", ".wav")):
                continue

            duration_seconds = None
            # check many possible keys
            for key in ("length","playtime","duration","play_length","tracklength","time"):
                if key in file_info:
                    duration_seconds = _parse_duration_value(file_info.get(key))
                    if duration_seconds is not None:
                        break
            # sometimes stored in nested metadata or as string in 'format' (rare)
            if duration_seconds is None and isinstance(file_info.get("format"), str):
                m = re.search(r'(\d+:\d{2}(?::\d{2})?)', file_info["format"])
                if m:
                    duration_seconds = _parse_duration_value(m.group(1))

            # normalize size to bytes
            raw_size = file_info.get("size") or file_info.get("filesize") or file_info.get("original") 
            size_bytes = _size_to_bytes(raw_size)

            # optional ffprobe fallback (remote URL reading)
            if duration_seconds is None and use_ffprobe:
                download_url = f"https://archive.org/download/{item_id}/{quote(filename, safe='')}"
                try:
                    out = subprocess.check_output([
                        ffprobe_path, '-v', 'error',
                        '-show_entries', 'format=duration',
                        '-of', 'default=noprint_wrappers=1:nokey=1',
                        download_url
                    ], stderr=subprocess.DEVNULL, timeout=30)
                    s = out.decode().strip()
                    if s:
                        duration_seconds = int(float(s))
                except Exception:
                    pass

            audio_files.append({
                "name": filename,
                "size": size_bytes,
                "format": file_info.get("format",""),
                "duration": duration_seconds,
                "mime": _mime_for_filename(filename, file_info.get("format"))
            })
        return audio_files
    except Exception as e:
        print(f"Error fetching files for {item_id}: {e}")
        return []
