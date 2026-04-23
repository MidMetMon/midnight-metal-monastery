#!/usr/bin/env python3
import json
import requests
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

# Configuration - EDIT THESE
COLLECTION_ID = "midnight-metal-monastery"  # Replace with your Archive.org collection ID
PODCAST_TITLE = "Midnight Metal Monastery"
PODCAST_DESCRIPTION = "Christian Rock and Metal Podcast"
PODCAST_AUTHOR = "inspired by the Holy Spirit"
PODCAST_IMAGE_URL = "https://github.com/MidMetMon/midnight-metal-monastery/blob/main/images/midnight-metal-monastery_itemimage.jpg"  # URL to a square image (3000x3000 or smaller)
PODCAST_LINK = "https://MidMetMon.github.io/midnight-metal-monastery"  # Link to your promotion website

def get_collection_items():
    """Fetch items from Archive.org collection via API"""
    url = f"https://archive.org/advancedsearch.php"
    params = {
        "q": f"collection:{COLLECTION_ID}",
        "fl": "identifier,title,description,date,creator,licenseurl",
        "output": "json",
        "rows": 200,  # Get up to 200 items
        "sort": "date desc"  # Newest first
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("response", {}).get("docs", [])
    except Exception as e:
        print(f"Error fetching collection: {e}")
        return []

def get_audio_files(item_id):
    """Get audio files for an item"""
    url = f"https://archive.org/metadata/{item_id}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        audio_files = []
        for file_info in data.get("files", []):
            filename = file_info.get("name", "")
            # Look for common audio formats
            if filename.lower().endswith((".mp3", ".m4a", ".ogg", ".flac", ".wav")):
                audio_files.append({
                    "name": filename,
                    "size": file_info.get("size", 0),
                    "format": file_info.get("format", "")
                })
        
        return audio_files
    except Exception as e:
        print(f"Error fetching files for {item_id}: {e}")
        return []

def parse_date(date_str):
    """Parse Archive.org date format to RFC 2822"""
    try:
        # Archive.org typically uses YYYY-MM-DD format
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        # Return in RSS date format
        return dt.strftime("%a, %d %b %Y 00:00:00 +0000")
    except:
        return datetime.now().strftime("%a, %d %b %Y 00:00:00 +0000")

def generate_rss_feed():
    """Generate the RSS feed XML"""
    
    items = get_collection_items()
    
    if not items:
        print("No items found in collection!")
        return None
    
    # Create RSS root element
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
    SubElement(channel, "lastBuildDate").text = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")
    SubElement(channel, "ttl").text = "3600"  # Update every hour
    
    # iTunes-specific metadata
    itunes_author = SubElement(channel, "itunes:author")
    itunes_author.text = PODCAST_AUTHOR
    
    itunes_owner = SubElement(channel, "itunes:owner")
    owner_name = SubElement(itunes_owner, "itunes:name")
    owner_name.text = PODCAST_AUTHOR
    
    itunes_image = SubElement(channel, "itunes:image")
    itunes_image.set("href", PODCAST_IMAGE_URL)
    
    image = SubElement(channel, "image")
    SubElement(image, "url").text = PODCAST_IMAGE_URL
    SubElement(image, "title").text = PODCAST_TITLE
    SubElement(image, "link").text = PODCAST_LINK
    
    # Add items (episodes)
    episode_count = 0
    for item in items:
        item_id = item.get("identifier", "")
        title = item.get("title", "Unknown")
        description = item.get("description", "")
        pub_date = item.get("date", "")
        creator = item.get("creator", PODCAST_AUTHOR)
        
        # Get audio files for this item
        audio_files = get_audio_files(item_id)
        
        # Create an episode for each audio file
        for audio_file in audio_files:
            filename = audio_file["name"]
            file_size = audio_file["size"]
            
            # Construct download URL
            download_url = f"https://archive.org/download/{item_id}/{filename}"
            
            # Create item (episode)
            item_elem = SubElement(channel, "item")
            SubElement(item_elem, "title").text = f"{title} - {filename}"
            SubElement(item_elem, "link").text = f"https://archive.org/details/{item_id}"
            SubElement(item_elem, "description").text = description or title
            SubElement(item_elem, "pubDate").text = parse_date(pub_date)
            SubElement(item_elem, "guid").text = download_url
            
            # iTunes metadata
            itunes_author_item = SubElement(item_elem, "itunes:author")
            itunes_author_item.text = creator
            
            # Audio enclosure
            enclosure = SubElement(item_elem, "enclosure")
            enclosure.set("url", download_url)
            enclosure.set("type", "audio/mpeg")  # Adjust if needed
            enclosure.set("length", str(file_size))
            
            episode_count += 1
    
    print(f"Generated {episode_count} episodes from {len(items)} items")
    
    # Pretty print and return
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
