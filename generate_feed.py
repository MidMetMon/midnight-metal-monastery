#!/usr/bin/env python3
import json
import requests
import re
from datetime import datetime, timezone
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
from urllib.parse import quote

# Configuration - EDIT THESE
COLLECTION_ID = "midnight-metal-monastery"  # Replace with your Archive.org collection ID
PODCAST_TITLE = "Midnight Metal Monastery"
PODCAST_DESCRIPTION = "We are the Warrior Monks of Christian Rock—slamming the jams that worship the Lamb, servants of the Almighty God. A Christian Rock and Metal Podcast."
PODCAST_ITUNES_SUMMARY = (
    "Midnight Metal Monastery is where faith meets fury. A sanctuary for listeners seeking spiritual depth and heavy riffs. We lift high the name of Jesus Christ through powerful music and Scripture. We are the Warrior Monks of Christian Rock, slamming the jams that worship the Lamb and serving the Almighty God. Slay the Beast and live!"
)
PODCAST_AUTHOR = "David Larry Carroll, Abbot and Andrew C. Schlett, First Prior"
PODCAST_IMAGE_URL = "https://midmetmon.github.io/midnight-metal-monastery/images/midnight-metal-monastery_itemimage_upscayl_4x.jpg"
PODCAST_LINK = "https://www.midnightmetalmonastery.com"
PODCAST_EMAIL = "contact@midnightmetalmonastery.com"  # Replace with your contact email
PODCAST_SUBTITLE = "Christian Rock and Metal Podcast"
PODCAST_COPYRIGHT = "© 2026 Midnight Metal Monastery"

# Episode summary template - customize as you like
EPISODE_SUMMARY_TEMPLATE = (
    "The bells ring, the amps roar, and the Warrior Monks gather again for episode {episode_number}. Enter the Midnight Metal Monastery and hear the thunder that shakes the gates of Hell!"
)

def get_collection_items():
    """Fetch items from Archive.org collection via API"""
    url = "https://archive.org/advancedsearch.php"
    params = {
        "q": f"collection:{COLLECTION_ID}",
        "fl": "identifier,title,description,date,creator,licenseurl",
        "output": "json",
        "rows": 200,
        "sort": "date desc"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("response", {}).get("docs", [])
    except Exception as e:
        print(f"Error fetching collection: {e}")
        return []

# ===== ADDITION: NEW FUNCTION TO GET EPISODE IMAGE =====
def get_item_image_url(item_id):
    """
    Get image URL for an Archive.org item.
    Returns Archive.org thumbnail URL, or falls back to podcast image.
    """
    try:
        # Archive.org provides item thumbnails via this standard URL pattern
        image_url = f"https://archive.org/services/img/{item_id}"
        # Quick validation - make a HEAD request to verify the image exists
        response = requests.head(image_url, timeout=5)
        if response.status_code == 200:
            return image_url
    except Exception as e:
        print(f"Warning: Could not fetch image for {item_id}: {e}")

    # Fall back to podcast-level image if item image unavailable
    return PODCAST_IMAGE_URL
# ===== END ADDITION =====

def _parse_duration_value(v):
    """Parse duration value from various formats (string seconds, HH:MM:SS, MM:SS, etc.)"""
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

def get_audio_files(item_id):
    """Get audio files for an item (including size and possible duration metadata)"""
    url = f"https://archive.org/metadata/{item_id}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        audio_files = []
        for file_info in data.get("files", []):
            filename = file_info.get("name", "")
            if filename.lower().endswith((".mp3", ".m4a", ".ogg", ".flac", ".wav")):
                duration_seconds = None
                # check many possible keys
                for key in ("length", "playtime", "duration", "play_length", "tracklength", "time"):
                    if key in file_info:
                        duration_seconds = _parse_duration_value(file_info.get(key))
                        if duration_seconds is not None:
                            break

                audio_files.append({
                    "name": filename,
                    "size": file_info.get("size", 0),
                    "format": file_info.get("format", ""),
                    "duration": duration_seconds
                })
        return audio_files
    except Exception as e:
        print(f"Error fetching files for {item_id}: {e}")
        return []

def parse_date(date_str):
    """Parse Archive.org date format to RFC 2822"""
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return dt.strftime("%a, %d %b %Y 00:00:00 +0000")
    except:
        return datetime.now().strftime("%a, %d %b %Y 00:00:00 +0000")

def format_duration(seconds):
    """Format seconds to H:MM:SS or M:SS as Apple expects"""
    if not seconds or seconds <= 0:
        return None
    hours, rem = divmod(int(seconds), 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"

def generate_rss_feed():
    items = get_collection_items()
    if not items:
        print("No items found in collection!")
        return None

    rss = Element("rss")
    rss.set("version", "2.0")
    rss.set("xmlns:itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
    rss.set("xmlns:content", "http://purl.org/rss/1.0/modules/content/")

    channel = SubElement(rss, "channel")

    # Channel metadata
    SubElement(channel, "title").text = PODCAST_TITLE
    SubElement(channel, "link").text = PODCAST_LINK
    SubElement(channel, "description").text = PODCAST_DESCRIPTION
    SubElement(channel, "language").text = "en-us"
    from datetime import datetime, timezone, timedelta
    safe_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    SubElement(channel, "lastBuildDate").text = safe_time.strftime("%a, %d %b %Y %H:%M:%S +0000")
    SubElement(channel, "ttl").text = "3600"

    # iTunes-specific metadata
    itunes_author = SubElement(channel, "itunes:author")
    itunes_author.text = PODCAST_AUTHOR

    itunes_subtitle = SubElement(channel, "itunes:subtitle")
    itunes_subtitle.text = PODCAST_SUBTITLE

    # Add itunes:summary (channel level)
    itunes_summary = SubElement(channel, "itunes:summary")
    itunes_summary.text = PODCAST_ITUNES_SUMMARY

    itunes_owner = SubElement(channel, "itunes:owner")
    owner_name = SubElement(itunes_owner, "itunes:name")
    owner_name.text = PODCAST_AUTHOR
    owner_email = SubElement(itunes_owner, "itunes:email")
    owner_email.text = PODCAST_EMAIL

    itunes_image = SubElement(channel, "itunes:image")
    itunes_image.set("href", PODCAST_IMAGE_URL)

    image = SubElement(channel, "image")
    SubElement(image, "url").text = PODCAST_IMAGE_URL
    SubElement(image, "title").text = PODCAST_TITLE
    SubElement(image, "link").text = PODCAST_LINK

    itunes_cat_parent = SubElement(channel, "itunes:category")
    itunes_cat_parent.set("text", "Religion & Spirituality")
    itunes_cat_child = SubElement(itunes_cat_parent, "itunes:category")
    itunes_cat_child.set("text", "Christianity")

    itunes_explicit = SubElement(channel, "itunes:explicit")
    itunes_explicit.text = "no"

    itunes_type = SubElement(channel, "itunes:type")
    itunes_type.text = "episodic"

    SubElement(channel, "copyright").text = PODCAST_COPYRIGHT

    # Episodes
    episode_count = 0
    episode_counter = 1  # fallback counter if no number parsed from title

    for item in items:
        item_id = item.get("identifier", "")
        title = item.get("title", "Unknown")
        description = PODCAST_DESCRIPTION
        pub_date = item.get("date", "")
        creator = PODCAST_AUTHOR

        audio_files = get_audio_files(item_id)
        for audio_file in audio_files:
            filename = audio_file["name"]
            file_size = audio_file["size"]
            duration_seconds = audio_file.get("duration")

            download_url = f"https://archive.org/download/{item_id}/{quote(filename, safe='')}"

            item_elem = SubElement(channel, "item")
            SubElement(item_elem, "title").text = title
            SubElement(item_elem, "link").text = f"https://archive.org/details/{item_id}"
            SubElement(item_elem, "description").text = description or title
            SubElement(item_elem, "pubDate").text = parse_date(pub_date)
            SubElement(item_elem, "guid").text = download_url

            # iTunes metadata
            itunes_author_item = SubElement(item_elem, "itunes:author")
            itunes_author_item.text = creator

            # Episode number parsing (#123) with fallback
            m = re.search(r"#\s*(\d+)", title)
            if m:
                episode_num = m.group(1)
            else:
                episode_num = str(episode_counter)

            ep = SubElement(item_elem, "itunes:episode")
            ep.text = str(episode_num)
            ep_type = SubElement(item_elem, "itunes:episodeType")
            ep_type.text = "full"

            # Generate dynamic episode summary
            episode_summary = EPISODE_SUMMARY_TEMPLATE.format(episode_number=episode_num)
            itunes_summary_item = SubElement(item_elem, "itunes:summary")
            itunes_summary_item.text = episode_summary

            # Add itunes:duration if available (format H:MM:SS or M:SS)
            dur_text = format_duration(duration_seconds)
            if dur_text:
                itunes_duration = SubElement(item_elem, "itunes:duration")
                itunes_duration.text = dur_text

            # ===== ADDITION: ADD EPISODE ARTWORK =====
            episode_image_url = get_item_image_url(item_id)
            itunes_image_item = SubElement(item_elem, "itunes:image")
            itunes_image_item.set("href", episode_image_url)
            # ===== END ADDITION =====

            # Audio enclosure
            enclosure = SubElement(item_elem, "enclosure")
            enclosure.set("url", download_url)
            enclosure.set("type", "audio/mpeg")
            enclosure.set("length", str(file_size))

            episode_count += 1
            if not m:
                episode_counter += 1

    print(f"Generated {episode_count} episodes from {len(items)} items")

    rough_string = tostring(rss, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

def main():
    print("Generating podcast RSS feed...")
    feed_xml = generate_rss_feed()
    if feed_xml:
        with open("podcast.rss", "w", encoding="utf-8") as f:
            f.write(feed_xml)
        print("✓ Feed saved to podcast.rss")
    else:
        print("✗ Failed to generate feed")

if __name__ == "__main__":
    main()
