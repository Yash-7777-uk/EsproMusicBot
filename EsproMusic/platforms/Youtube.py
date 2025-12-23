import asyncio
import os
import re
import json
from typing import Union, Optional
import httpx

from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

from EsproMusic.utils.formatters import time_to_seconds
from config import API_KEY

# New API Configuration
API_BASE_URL = "https://sdvyt-dl-53933a861e76.herokuapp.com/api"

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

        # Get video stream URL from API
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                api_url = f"{API_BASE_URL}/vidssave?link={link}"
                response = await client.get(api_url)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == 1:
                        resources = data.get("data", {}).get("resources", [])
                        
                        # Find 720P video first
                        for resource in resources:
                            if resource.get("type") == "video" and resource.get("quality") == "720P":
                                return 1, resource.get("download_url")
                        
                        # If no 720P, find any video
                        for resource in resources:
                            if resource.get("type") == "video":
                                return 1, resource.get("download_url")
                        
                        raise Exception("No video resources found")
                    else:
                        raise Exception(f"API error: Status {data.get('status')}")
                else:
                    raise Exception(f"API returned {response.status_code}")
        except Exception as e:
            print(f"API video error: {e}")
            # Fallback to direct video link
            vid = link.split("v=")[-1].split("&")[0] if "v=" in link else link.split("/")[-1].split("?")[0]
            return 1, f"https://www.youtube.com/watch?v={vid}"

    async def stream_url(self, link: str, videoid: Union[bool, str] = None, video: bool = False) -> Optional[str]:
        """
        Get streaming URL for VC playback (no file download, no size limit).
        
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
                api_url = f"{API_BASE_URL}/vidssave?link={link}"
                response = await client.get(api_url)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == 1:
                        resources = data.get("data", {}).get("resources", [])
                        
                        if video:
                            # Find 720P video first
                            for resource in resources:
                                if resource.get("type") == "video" and resource.get("quality") == "720P":
                                    return resource.get("download_url")
                            
                            # If no 720P, find any video
                            for resource in resources:
                                if resource.get("type") == "video":
                                    return resource.get("download_url")
                        else:
                            # Find best audio (largest size)
                            audio_resources = []
                            for resource in resources:
                                if resource.get("type") == "audio":
                                    audio_resources.append(resource)
                            
                            if audio_resources:
                                # Sort by size (largest first)
                                audio_resources.sort(key=lambda x: x.get("size", 0), reverse=True)
                                return audio_resources[0].get("download_url")
                        
                        raise Exception("No matching resources found")
                    else:
                        raise Exception(f"API error: Status {data.get('status')}")
                else:
                    raise Exception(f"API returned {response.status_code}")
        except Exception as e:
            print(f"API stream_url error: {e}")
            # Fallback
            vid = link.split("v=")[-1].split("&")[0] if "v=" in link else link.split("/")[-1].split("?")[0]
            if video:
                return f"https://www.youtube.com/watch?v={vid}"
            else:
                return f"https://www.youtube.com/watch?v={vid}"

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        """Playlist support - returns list of video IDs"""
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]

        # Extract playlist ID
        playlist_id = link.split("list=")[-1].split("&")[0] if "list=" in link else ""

        # Note: Your API may not support playlists, so we'll use YouTube search as fallback
        try:
            # Try to get playlist using VideosSearch
            search = VideosSearch(link, limit=limit)
            result = await search.next()
            video_ids = []
            for video in result["result"]:
                video_ids.append(video["id"])
            return video_ids
        except Exception as e:
            print(f"Playlist error: {e}")
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
        """Get available formats via API"""
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                api_url = f"{API_BASE_URL}/vidssave?link={link}"
                response = await client.get(api_url)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == 1:
                        resources = data.get("data", {}).get("resources", [])
                        formats_list = []
                        
                        for resource in resources:
                            format_info = {
                                "format": f"{resource.get('quality', '')} {resource.get('format', '')}",
                                "filesize": resource.get("size", 0),
                                "format_id": resource.get("resource_id", ""),
                                "ext": resource.get("format", "").lower(),
                                "format_note": resource.get("quality", ""),
                                "yturl": link,
                                "type": resource.get("type", ""),
                                "download_url": resource.get("download_url", "")
                            }
                            formats_list.append(format_info)
                        
                        return formats_list, link
                    else:
                        return [], link
                else:
                    return [], link
        except Exception as e:
            print(f"API formats error: {e}")
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
        Download audio or video using API.
        
        Returns:
            - For streaming (long videos): Returns streaming URL as string
            - For downloads (short videos): Returns (filepath, True) tuple
        """
        if videoid:
            link = self.base + link

        # Check video duration to decide streaming vs download
        duration_seconds = 0
        try:
            # Get duration from YouTube search
            results = VideosSearch(link, limit=1)
            for result in (await results.next())["result"]:
                duration_str = result.get("duration", "0:0")
                if duration_str and duration_str != "None":
                    duration_seconds = int(time_to_seconds(duration_str))
        except Exception as e:
            print(f"Failed to get duration: {e}")

        # For long videos (>20 min), return streaming URL instead of downloading
        if ENABLE_STREAMING and duration_seconds > STREAM_MODE_DURATION_THRESHOLD:
            # Get streaming URL from API
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                    api_url = f"{API_BASE_URL}/vidssave?link={link}"
                    response = await client.get(api_url)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("status") == 1:
                            resources = data.get("data", {}).get("resources", [])
                            
                            if video:
                                # Find 720P video
                                for resource in resources:
                                    if resource.get("type") == "video" and resource.get("quality") == "720P":
                                        stream_url = resource.get("download_url")
                                        break
                                else:
                                    # If no 720P, find any video
                                    for resource in resources:
                                        if resource.get("type") == "video":
                                            stream_url = resource.get("download_url")
                                            break
                                    else:
                                        stream_url = None
                            else:
                                # Find best audio
                                audio_resources = []
                                for resource in resources:
                                    if resource.get("type") == "audio":
                                        audio_resources.append(resource)
                                
                                if audio_resources:
                                    audio_resources.sort(key=lambda x: x.get("size", 0), reverse=True)
                                    stream_url = audio_resources[0].get("download_url")
                                else:
                                    stream_url = None
                            
                            if stream_url:
                                print(f"Using streaming URL for long video ({duration_seconds}s): {stream_url}")
                                return stream_url
            except Exception as e:
                print(f"API streaming error: {e}")

        # For short videos, download from API
        async def api_download_audio():
            """Download audio using the API"""
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                    api_url = f"{API_BASE_URL}/vidssave?link={link}"
                    response = await client.get(api_url)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("status") == 1:
                            resources = data.get("data", {}).get("resources", [])
                            
                            # Find best audio (largest size)
                            audio_resources = []
                            for resource in resources:
                                if resource.get("type") == "audio":
                                    audio_resources.append(resource)
                            
                            if not audio_resources:
                                raise Exception("No audio resources found")
                            
                            # Sort by size (largest first)
                            audio_resources.sort(key=lambda x: x.get("size", 0), reverse=True)
                            audio_url = audio_resources[0].get("download_url")
                            
                            # Download the audio file
                            os.makedirs("downloads", exist_ok=True)
                            
                            # Get title for filename
                            try:
                                results = VideosSearch(link, limit=1)
                                for result in (await results.next())["result"]:
                                    file_title = result.get("title", "audio")
                            except:
                                file_title = "audio"
                            
                            # Sanitize filename
                            safe_title = re.sub(r'[<>:"/\\|?*]', '', file_title)[:100]
                            filepath = f"downloads/{safe_title}.mp3"
                            
                            # Download file
                            async with client.stream("GET", audio_url) as r:
                                if r.status_code != 200:
                                    raise Exception(f"Download returned {r.status_code}")
                                
                                with open(filepath, "wb") as f:
                                    async for chunk in r.aiter_bytes(chunk_size=1024 * 128):
                                        if chunk:
                                            f.write(chunk)
                            
                            return filepath
                        else:
                            raise Exception(f"API error: Status {data.get('status')}")
                    else:
                        raise Exception(f"API returned {response.status_code}")
            except Exception as e:
                print(f"API audio download failed: {e}")
                return None

        async def api_download_video():
            """Download video using the API"""
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                    api_url = f"{API_BASE_URL}/vidssave?link={link}"
                    response = await client.get(api_url)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("status") == 1:
                            resources = data.get("data", {}).get("resources", [])
                            
                            # Find 720P video first, then any video
                            video_url = None
                            for resource in resources:
                                if resource.get("type") == "video" and resource.get("quality") == "720P":
                                    video_url = resource.get("download_url")
                                    break
                            
                            if not video_url:
                                for resource in resources:
                                    if resource.get("type") == "video":
                                        video_url = resource.get("download_url")
                                        break
                            
                            if not video_url:
                                raise Exception("No video resources found")
                            
                            # Download the video file
                            os.makedirs("downloads", exist_ok=True)
                            
                            # Get title for filename
                            try:
                                results = VideosSearch(link, limit=1)
                                for result in (await results.next())["result"]:
                                    file_title = result.get("title", "video")
                            except:
                                file_title = "video"
                            
                            # Sanitize filename
                            safe_title = re.sub(r'[<>:"/\\|?*]', '', file_title)[:100]
                            filepath = f"downloads/{safe_title}.mp4"
                            
                            # Download file
                            async with client.stream("GET", video_url) as r:
                                if r.status_code != 200:
                                    raise Exception(f"Download returned {r.status_code}")
                                
                                with open(filepath, "wb") as f:
                                    async for chunk in r.aiter_bytes(chunk_size=1024 * 128):
                                        if chunk:
                                            f.write(chunk)
                            
                            return filepath
                        else:
                            raise Exception(f"API error: Status {data.get('status')}")
                    else:
                        raise Exception(f"API returned {response.status_code}")
            except Exception as e:
                print(f"API video download failed: {e}")
                return None

        # Handle special song download cases (custom format_id)
        if songvideo or songaudio:
            # For custom format downloads, fall back to video/audio download
            if songvideo:
                downloaded_file = await api_download_video()
                if downloaded_file:
                    if title:
                        fpath = f"downloads/{title}.mp4"
                        if downloaded_file != fpath and os.path.exists(downloaded_file):
                            os.rename(downloaded_file, fpath)
                        return fpath
                    else:
                        return downloaded_file
            else:  # songaudio
                downloaded_file = await api_download_audio()
                if downloaded_file:
                    if title:
                        fpath = f"downloads/{title}.mp3"
                        if downloaded_file != fpath and os.path.exists(downloaded_file):
                            os.rename(downloaded_file, fpath)
                        return fpath
                    else:
                        return downloaded_file
            return None

        # Standard video or audio download
        if video:
            # Download video
            downloaded_file = await api_download_video()
            if downloaded_file and os.path.exists(downloaded_file):
                return downloaded_file, True
            return None, True
        else:
            # Download audio
            downloaded_file = await api_download_audio()
            if downloaded_file and os.path.exists(downloaded_file):
                return downloaded_file, True
            return None, True