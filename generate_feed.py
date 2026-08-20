#!/usr/bin/env python3
import json
import requests
import re
from datetime import datetime, timezone
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
from urllib.parse import quote

# ===== CONFIGURATION SECTION =====
# These are the main settings you need to customize for your podcast
# Replace these values with your own information before running the script

# Archive.org collection ID - this identifies which collection to pull episodes from
COLLECTION_ID = "midnight-metal-monastery"  # Replace with your Archive.org collection ID

# Podcast metadata - this information appears in podcast directories
PODCAST_TITLE = "Midnight Metal Monastery"
PODCAST_DESCRIPTION = "We are the Warrior Monks of Christian Rock—slamming the jams that worship the Lamb, servants of the Almighty God. A Christian Rock and Metal Podcast."
PODCAST_ITUNES_SUMMARY = (
    "Midnight Metal Monastery is where faith meets fury. A sanctuary for listeners seeking spiritual depth and heavy riffs. We lift high the name of Jesus Christ through powerful music and Scripture. We are the Warrior Monks of Christian Rock, slamming the jams that worship the Lamb and serving the Almighty God. Slay the Beast and live!"
)
PODCAST_AUTHOR = "David Larry Carroll, Abbot and Andrew C. Schlett, First Prior"
PODCAST_IMAGE_URL = "https://midmetmon.github.io/midnight-metal-monastery/images/midnight-metal-monastery_itemimage_upscayl_4x.jpg"
PODCAST_LINK = "https://midnightmetalmonastery.com/"
PODCAST_EMAIL = "contact@midnightmetalmonastery.com"  # Replace with your contact email
PODCAST_SUBTITLE = "Christian Rock and Metal Podcast"
PODCAST_COPYRIGHT = "© 2026 Midnight Metal Monastery"

# Template for generating episode descriptions
# {episode_number} will be replaced with the actual episode number
EPISODE_SUMMARY_TEMPLATE = (
    "The bells ring, the amps roar, and the Warrior Monks gather again for episode {episode_number}. Enter the Midnight Metal Monastery and hear the thunder that shakes the gates of Hell!"
)

# ===== FUNCTION DEFINITIONS =====

def get_collection_items():
    """
    Fetch items from Archive.org collection via API

    This function queries the Archive.org advanced search API to retrieve all items
    in the specified collection. It returns a list of dictionaries containing metadata
    about each item (identifier, title, description, etc.).

    Returns:
        list: A list of item dictionaries from the collection
    """
    url = "https://archive.org/advancedsearch.php"
    params = {
        "q": f"collection:{COLLECTION_ID}",  # Search for items in our collection
        "fl": "identifier,title,description,date,creator,licenseurl",  # Fields to return
        "output": "json",  # Request JSON format
        "rows": 200,  # Maximum number of results to return
        "sort": "date desc"  # Sort by date, newest first
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()  # Raise an exception for HTTP errors
        data = response.json()
        return data.get("response", {}).get("docs", [])
    except Exception as e:
        print(f"Error fetching collection: {e}")
        return []

def get_item_image_url(item_id):
    """
    Get image URL for an Archive.org item.

    This function attempts to retrieve a thumbnail image specific to an Archive.org item.
    If that fails, it falls back to using the podcast's main image.

    Args:
        item_id (str): The Archive.org identifier for the item

    Returns:
        str: URL to an image for the item
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

def _parse_duration_value(v):
    """
    Parse duration value from various formats (string seconds, HH:MM:SS, MM:SS, etc.)

    This helper function converts different duration formats into seconds.
    It handles plain numbers (like "300" for 5 minutes), and time formats like "5:30" or "1:05:30".

    Args:
        v: The duration value to parse (can be string, number, or None)

    Returns:
        int or None: Duration in seconds, or None if parsing fails
    """
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
    """
    Get audio files for an item (including size and possible duration metadata)

    This function queries Archive.org's metadata API to find all audio files
    associated with a specific item. It returns information about each audio file
    including filename, size, format, and duration.

    Args:
        item_id (str): The Archive.org identifier for the item

    Returns:
        list: A list of dictionaries containing audio file information
    """
    url = f"https://archive.org/metadata/{item_id}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        audio_files = []
        for file_info in data.get("files", []):
            filename = file_info.get("name", "")
            # Only process audio files (based on common extensions)
            if filename.lower().endswith((".mp3", ".m4a", ".ogg", ".flac", ".wav")):
                duration_seconds = None
                # Check many possible keys for duration information
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
    """
    Parse Archive.org date format to RFC 2822

    Archive.org provides dates in YYYY-MM-DD format, but RSS feeds require
    dates in RFC 2822 format (e.g., "Mon, 01 Jan 2023 00:00:00 +0000").

    Args:
        date_str (str): Date string in Archive.org format

    Returns:
        str: Date string in RFC 2822 format
    """
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return dt.strftime("%a, %d %b %Y 00:00:00 +0000")
    except:
        # Fallback to current date if parsing fails
        return datetime.now().strftime("%a, %d %b %Y 00:00:00 +0000")

def format_duration(seconds):
    """
    Format seconds to H:MM:SS or M:SS as Apple expects

    This function converts a duration in seconds to a format suitable for
    podcast directories, particularly Apple Podcasts.

    Args:
        seconds (int): Duration in seconds

    Returns:
        str or None: Formatted duration string, or None if input is invalid
    """
    if not seconds or seconds <= 0:
        return None
    hours, rem = divmod(int(seconds), 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"

def generate_rss_feed():
    """
    Generate the complete RSS feed for the podcast

    This is the main function that orchestrates the creation of the RSS feed.
    It fetches items from Archive.org, processes each one to extract audio files,
    and constructs the XML structure for the RSS feed.

    Returns:
        str or None: The formatted XML string of the RSS feed, or None if generation fails
    """
    # Get all items from the Archive.org collection
    items = get_collection_items()
    if not items:
        print("No items found in collection!")
        return None

    # Create the root RSS element with required namespaces
    rss = Element("rss")
    rss.set("version", "2.0")
    rss.set("xmlns:itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
    rss.set("xmlns:content", "http://purl.org/rss/1.0/modules/content/")

    # Create the channel element which contains all podcast metadata and episodes
    channel = SubElement(rss, "channel")

    # ===== CHANNEL METADATA =====
    # Basic RSS channel metadata
    SubElement(channel, "title").text = PODCAST_TITLE
    SubElement(channel, "link").text = PODCAST_LINK
    SubElement(channel, "description").text = PODCAST_DESCRIPTION
    SubElement(channel, "language").text = "en-us"

    # Set the last build date to 5 minutes ago to avoid caching issues
    from datetime import datetime, timezone, timedelta
    safe_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    SubElement(channel, "lastBuildDate").text = safe_time.strftime("%a, %d %b %Y %H:%M:%S +0000")
    SubElement(channel, "ttl").text = "3600"  # Time to live in minutes

    # ===== iTUNES-SPECIFIC METADATA =====
    # These elements are specific to Apple Podcasts and other podcast directories

    # Author information
    itunes_author = SubElement(channel, "itunes:author")
    itunes_author.text = PODCAST_AUTHOR

    # Subtitle for the podcast
    itunes_subtitle = SubElement(channel, "itunes:subtitle")
    itunes_subtitle.text = PODCAST_SUBTITLE

    # Main summary/description for podcast directories
    itunes_summary = SubElement(channel, "itunes:summary")
    itunes_summary.text = PODCAST_ITUNES_SUMMARY

    # Owner information (required by Apple)
    itunes_owner = SubElement(channel, "itunes:owner")
    owner_name = SubElement(itunes_owner, "itunes:name")
    owner_name.text = PODCAST_AUTHOR
    owner_email = SubElement(itunes_owner, "itunes:email")
    owner_email.text = PODCAST_EMAIL

    # Podcast artwork
    itunes_image = SubElement(channel, "itunes:image")
    itunes_image.set("href", PODCAST_IMAGE_URL)

    # Standard RSS image element (some directories use this instead)
    image = SubElement(channel, "image")
    SubElement(image, "url").text = PODCAST_IMAGE_URL
    SubElement(image, "title").text = PODCAST_TITLE
    SubElement(image, "link").text = PODCAST_LINK

    # Category information (required by Apple)
    itunes_cat_parent = SubElement(channel, "itunes:category")
    itunes_cat_parent.set("text", "Religion & Spirituality")
    itunes_cat_child = SubElement(itunes_cat_parent, "itunes:category")
    itunes_cat_child.set("text", "Christianity")

    # Explicit content flag
    itunes_explicit = SubElement(channel, "itunes:explicit")
    itunes_explicit.text = "no"

    # Podcast type (episodic means episodes aren't part of a season)
    itunes_type = SubElement(channel, "itunes:type")
    itunes_type.text = "episodic"

    # Copyright information
    SubElement(channel, "copyright").text = PODCAST_COPYRIGHT

    # ===== EPISODE PROCESSING =====
    # Process each item in the collection to create episode entries

    episode_count = 0
    episode_counter = 1  # fallback counter if no number parsed from title

    for item in items:
        item_id = item.get("identifier", "")
        title = item.get("title", "Unknown")
        description = PODCAST_DESCRIPTION
        pub_date = item.get("date", "")
        creator = PODCAST_AUTHOR

        # Get all audio files for this item
        audio_files = get_audio_files(item_id)
        for audio_file in audio_files:
            filename = audio_file["name"]
            file_size = audio_file["size"]
            duration_seconds = audio_file.get("duration")

            # Create the download URL for the audio file
            download_url = f"https://archive.org/download/{item_id}/{quote(filename, safe='')}"

            # Create the item (episode) element
            item_elem = SubElement(channel, "item")

            # Basic RSS item metadata
            SubElement(item_elem, "title").text = title
            SubElement(item_elem, "link").text = f"https://archive.org/details/{item_id}"
            SubElement(item_elem, "description").text = description or title
            SubElement(item_elem, "pubDate").text = parse_date(pub_date)
            SubElement(item_elem, "guid").text = download_url  # Unique identifier for the episode

            # ===== iTUNES-SPECIFIC EPISODE METADATA =====

            # Author for this specific episode
            itunes_author_item = SubElement(item_elem, "itunes:author")
            itunes_author_item.text = creator

            # Parse episode number from title (looking for format like "#123")
            m = re.search(r"#\s*(\d+)", title)
            if m:
                episode_num = m.group(1)
            else:
                episode_num = str(episode_counter)

            # Episode number (required by Apple)
            ep = SubElement(item_elem, "itunes:episode")
            ep.text = str(episode_num)
            ep_type = SubElement(item_elem, "itunes:episodeType")
            ep_type.text = "full"  # "full" means a complete episode

            # Generate dynamic episode summary using the template
            episode_summary = EPISODE_SUMMARY_TEMPLATE.format(episode_number=episode_num)
            itunes_summary_item = SubElement(item_elem, "itunes:summary")
            itunes_summary_item.text = episode_summary

            # Add duration if available (formatted as H:MM:SS or M:SS)
            dur_text = format_duration(duration_seconds)
            if dur_text:
                itunes_duration = SubElement(item_elem, "itunes:duration")
                itunes_duration.text = dur_text

            # Add episode-specific artwork
            episode_image_url = get_item_image_url(item_id)
            itunes_image_item = SubElement(item_elem, "itunes:image")
            itunes_image_item.set("href", episode_image_url)

            # ===== AUDIO ENCLOSURE =====
            # This is the actual audio file that podcast apps will download

            enclosure = SubElement(item_elem, "enclosure")
            enclosure.set("url", download_url)
            enclosure.set("type", "audio/mpeg")  # MIME type for MP3 files
            enclosure.set("length", str(file_size))  # File size in bytes

            episode_count += 1
            if not m:
                episode_counter += 1  # Increment our fallback counter

    print(f"Generated {episode_count} episodes from {len(items)} items")

    # Convert the XML tree to a nicely formatted string
    rough_string = tostring(rss, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

def main():
    """
    Main function that runs when the script is executed

    This function calls generate_rss_feed() and saves the result to a file.
    """
    print("Generating podcast RSS feed...")
    feed_xml = generate_rss_feed()
    if feed_xml:
        with open("podcast.rss", "w", encoding="utf-8") as f:
            f.write(feed_xml)
        print("✓ Feed saved to podcast.rss")
    else:
        print("✗ Failed to generate feed")

# This ensures the script only runs when executed directly (not when imported)
if __name__ == "__main__":
    main()
