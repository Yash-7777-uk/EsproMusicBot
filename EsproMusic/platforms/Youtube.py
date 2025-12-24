import asyncio
import os
import re
from typing import Union, Optional
import httpx

from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

from EsproMusic.utils.formatters import time_to_seconds
from config import API_KEY

# New API Configuration
NEW_API_BASE_URL = "https://sdvyt-dl-53933a861e76.herokuapp.com/api"
OLD_API_BASE_URL = "https://youtubify.me"

# Choose which API to use
USE_NEW_API = True  # Set to True to use the new API
API_BASE_URL = NEW_API_BASE_URL if USE_NEW_API else OLD_API_BASE_URL

# Streaming configuration
ENABLE_STREAMING = True  # Enable streaming URLs for VC (no file size limit)
MAX_DOWNLOAD_SIZE_MB = 48  # Only download files smaller than this (for direct uploads)
STREAM_MODE_DURATION_THRESHOLD = 1200  # 20 minutes - files longer than this will use streaming URLs


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if re.search(self.regex, link):
            return True
        else:
            return False

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        if offset in (None,):
            return None
        return text[offset : offset + length]

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            if str(duration_min) == "None":
                duration_sec = 0
            else:
                duration_sec = int(time_to_seconds(duration_min))
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
        return title

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            duration = result["duration"]
        return duration

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        return thumbnail

    async def video(self, link: str, videoid: Union[bool, str] = None):
        """Get video stream URL via API"""
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        # Extract video ID
        vid = link.split("v=")[-1].split("&")[0] if "v=" in link else link.split("/")[-1].split("?")[0]

        # Get video info from new API
        video_url = None
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                # Get video info from new API
                if USE_NEW_API:
                    api_url = f"{NEW_API_BASE_URL}/vidssave"
                    params = {"link": link}
                    response = await client.get(api_url, params=params)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("status") == 1:
                            resources = data.get("data", {}).get("resources", [])
                            # Find 720p video
                            for resource in resources:
                                if (resource.get("type") == "video" and 
                                    resource.get("quality") == "720P"):
                                    video_url = resource.get("download_url")
                                    break
                else:
                    # Fallback to old API
                    video_url = f"{OLD_API_BASE_URL}/download/video?video_id={vid}&mode=stream&max_res=720&api_key={API_KEY}"
        except Exception as e:
            print(f"Error getting video URL: {e}")
        
        return 1, video_url if video_url else link

    async def stream_url(self, link: str, videoid: Union[bool, str] = None, video: bool = False) -> Optional[str]:
        """
        Get streaming URL for VC playback using new API.
        
        Args:
            link: YouTube URL or video ID
            videoid: If True, link is just the video ID
            video: If True, return video stream; if False, return audio stream
        
        Returns:
            Streaming URL string that can be used directly by FFmpeg/Telegram VC
        """
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                if USE_NEW_API:
                    # Use new API
                    api_url = f"{NEW_API_BASE_URL}/vidssave"
                    params = {"link": link}
                    response = await client.get(api_url, params=params)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("status") == 1:
                            resources = data.get("data", {}).get("resources", [])
                            
                            if video:
                                # Find best video quality (prefer 720P, then 360P)
                                video_resources = [r for r in resources if r.get("type") == "video"]
                                # Sort by quality (720P first)
                                for quality in ["720P", "360P", "240P", "144P"]:
                                    for resource in video_resources:
                                        if resource.get("quality") == quality:
                                            return resource.get("download_url")
                            else:
                                # Find best audio quality (prefer 256KBPS, then 128KBPS)
                                audio_resources = [r for r in resources if r.get("type") == "audio"]
                                for quality in ["256KBPS", "128KBPS", "48KBPS", "LOW"]:
                                    for resource in audio_resources:
                                        if resource.get("quality") == quality:
                                            return resource.get("download_url")
                else:
                    # Fallback to old API
                    vid = link.split("v=")[-1].split("&")[0] if "v=" in link else link.split("/")[-1].split("?")[0]
                    if video:
                        return f"{OLD_API_BASE_URL}/download/video?video_id={vid}&max_res=720&api_key={API_KEY}"
                    else:
                        return f"{OLD_API_BASE_URL}/download/audio?video_id={vid}&api_key={API_KEY}"
                        
        except Exception as e:
            print(f"Error getting stream URL from API: {e}")
        
        return None

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        """Playlist support - returns list of video IDs"""
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]

        # Extract playlist ID
        playlist_id = link.split("list=")[-1].split("&")[0] if "list=" in link else ""

        try:
            if USE_NEW_API:
                # New API doesn't have playlist support, fallback to search
                async with httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=15.0)) as client:
                    # Try to use YouTube search for playlist items
                    search_url = f"https://www.youtube.com/playlist?list={playlist_id}"
                    # This is a simplified approach - in production you'd need proper playlist parsing
                    return [playlist_id]  # Simplified
            else:
                async with httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=15.0)) as client:
                    url = f"{OLD_API_BASE_URL}/playlist"
                    params = {"playlist_id": playlist_id, "limit": limit, "api_key": API_KEY}
                    r = await client.get(url, params=params)
                    if r.status_code == 200:
                        data = r.json()
                        return data.get("video_ids", [])
        except Exception:
            pass

        return []

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            vidid = result["id"]
            yturl = result["link"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        """Get available formats via new API"""
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=10.0)) as client:
                if USE_NEW_API:
                    api_url = f"{NEW_API_BASE_URL}/vidssave"
                    params = {"link": link}
                    response = await client.get(api_url, params=params)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("status") == 1:
                            resources = data.get("data", {}).get("resources", [])
                            
                            # Convert to format list
                            formats_list = []
                            for resource in resources:
                                format_info = {
                                    "format_id": resource.get("resource_id", ""),
                                    "ext": resource.get("format", "").lower(),
                                    "resolution": resource.get("quality", ""),
                                    "filesize": resource.get("size", 0),
                                    "type": resource.get("type", ""),
                                    "url": resource.get("download_url", "")
                                }
                                formats_list.append(format_info)
                            
                            return formats_list, link
                else:
                    # Fallback to old API
                    vid = link.split("v=")[-1].split("&")[0] if "v=" in link else link.split("/")[-1].split("?")[0]
                    url = f"{OLD_API_BASE_URL}/formats"
                    params = {"video_id": vid, "api_key": API_KEY}
                    r = await client.get(url, params=params)
                    if r.status_code == 200:
                        data = r.json()
                        return data.get("formats", []), link
        except Exception as e:
            print(f"Error getting formats: {e}")
            pass

        return [], link

    async def slider(
        self,
        link: str,
        query_type: int,
        videoid: Union[bool, str] = None,
    ):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> Union[str, tuple]:
        """
        Download audio or video using new API.
        
        Returns:
            - For streaming (long videos): Returns streaming URL as string
            - For downloads (short videos): Returns (filepath, True) tuple
        """
        if videoid:
            link = self.base + link

        # Get video info from new API
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                api_url = f"{NEW_API_BASE_URL}/vidssave"
                params = {"link": link}
                response = await client.get(api_url, params=params)
                
                if response.status_code != 200:
                    raise Exception(f"API returned {response.status_code}")
                
                data = response.json()
                if data.get("status") != 1:
                    raise Exception("API returned error status")
                
                video_info = data.get("data", {})
                resources = video_info.get("resources", [])
                video_title = video_info.get("title", "Unknown")
                
                # Get duration
                duration_seconds = video_info.get("duration", 0)
                
        except Exception as e:
            print(f"Failed to get video info from API: {e}")
            # Fallback to old method for duration
            duration_seconds = 0
            video_title = "Unknown"
            resources = []

        # For long videos (>20 min), return streaming URL instead of downloading
        if ENABLE_STREAMING and duration_seconds > STREAM_MODE_DURATION_THRESHOLD:
            # Return streaming URL for VC playback
            stream_url = await self.stream_url(link, videoid, video)
            if stream_url:
                print(f"Using streaming URL for long video ({duration_seconds}s): {stream_url}")
                return stream_url
            else:
                # Fallback to direct download
                print("Stream URL not available, falling back to download")

        # For short videos, download directly
        async def download_from_api():
            """Download file using direct URL from API"""
            try:
                # Find the appropriate resource
                download_url = None
                resource_type = "video" if video else "audio"
                
                if resource_type == "video":
                    # Prefer 720P, then 360P for video
                    for quality in ["720P", "360P", "240P", "144P"]:
                        for resource in resources:
                            if (resource.get("type") == "video" and 
                                resource.get("quality") == quality):
                                download_url = resource.get("download_url")
                                file_ext = resource.get("format", "mp4").lower()
                                break
                        if download_url:
                            break
                else:
                    # Prefer 256KBPS, then 128KBPS for audio
                    for quality in ["256KBPS", "128KBPS", "48KBPS", "LOW"]:
                        for resource in resources:
                            if (resource.get("type") == "audio" and 
                                resource.get("quality") == quality):
                                download_url = resource.get("download_url")
                                file_ext = resource.get("format", "mp3").lower()
                                if file_ext == "opus":
                                    file_ext = "opus"
                                elif file_ext == "m4a":
                                    file_ext = "m4a"
                                else:
                                    file_ext = "mp3"
                                break
                        if download_url:
                            break
                
                if not download_url:
                    raise Exception(f"No {resource_type} resource found")
                
                # Sanitize filename
                safe_title = re.sub(r'[<>:"/\\|?*]', '', video_title)[:100]
                if songvideo or songaudio:
                    safe_title = title if title else safe_title
                
                # Set file extension
                if songvideo:
                    file_ext = "mp4"
                elif songaudio:
                    file_ext = "mp3"
                elif video:
                    file_ext = "mp4"
                else:
                    file_ext = "mp3"
                
                filepath = f"downloads/{safe_title}.{file_ext}"
                
                # Download file
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(connect=10.0, read=600.0, write=600.0, pool=10.0),
                    follow_redirects=True
                ) as client:
                    
                    os.makedirs("downloads", exist_ok=True)
                    
                    async with client.stream("GET", download_url) as r:
                        if r.status_code != 200:
                            raise Exception(f"Download failed with status {r.status_code}")
                        
                        with open(filepath, "wb") as f:
                            async for chunk in r.aiter_bytes(chunk_size=1024 * 128):
                                if chunk:
                                    f.write(chunk)
                    
                    return filepath
                    
            except Exception as e:
                print(f"Download failed: {e}")
                return None

        # Handle special song download cases
        if songvideo or songaudio:
            downloaded_file = await download_from_api()
            if downloaded_file:
                # Ensure correct file extension
                if songvideo and not downloaded_file.endswith('.mp4'):
                    new_path = downloaded_file.rsplit('.', 1)[0] + '.mp4'
                    os.rename(downloaded_file, new_path)
                    return new_path
                elif songaudio and not downloaded_file.endswith('.mp3'):
                    new_path = downloaded_file.rsplit('.', 1)[0] + '.mp3'
                    os.rename(downloaded_file, new_path)
                    return new_path
                return downloaded_file
            return None

        # Standard video or audio download
        downloaded_file = await download_from_api()
        if downloaded_file and os.path.exists(downloaded_file):
            return downloaded_file, True
        
        return None, True