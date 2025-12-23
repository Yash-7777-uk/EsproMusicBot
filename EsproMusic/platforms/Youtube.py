import asyncio
import os
import re
import json
from typing import Union
import aiohttp
import yt_dlp
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

import config
from EsproMusic.utils.database import is_on_off
from EsproMusic.utils.formatters import time_to_seconds


async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        if (
            "unavailable videos are hidden"
            in (errorz.decode("utf-8")).lower()
        ):
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
    return out.decode("utf-8")


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(
            r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])"
        )
        self.api_base = "https://sdvyt-dl-53933a861e76.herokuapp.com/api/vidssave?link="

    async def exists(
        self, link: str, videoid: Union[bool, str] = None
    ):
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
                    if entity.type == "url":
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == "text_link":
                        return entity.url
        if offset in (None,):
            return None
        return text[offset : offset + length]

    async def details(
        self, link: str, videoid: Union[bool, str] = None
    ):
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

    async def title(
        self, link: str, videoid: Union[bool, str] = None
    ):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
        return title

    async def duration(
        self, link: str, videoid: Union[bool, str] = None
    ):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            duration = result["duration"]
        return duration

    async def thumbnail(
        self, link: str, videoid: Union[bool, str] = None
    ):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        return thumbnail

    async def video(
        self, link: str, videoid: Union[bool, str] = None
    ):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        # API से video link प्राप्त करें
        try:
            api_url = f"{self.api_base}{link}"
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    if response.status == 200:
                        data = await response.json()

                        # सबसे पहले 720P video ढूंढें
                        for resource in data.get("data", {}).get("resources", []):
                            if resource.get("type") == "video" and resource.get("quality") == "720P":
                                return 1, resource.get("download_url")

                        # अगर 720P नहीं मिला तो कोई भी video return करें
                        for resource in data.get("data", {}).get("resources", []):
                            if resource.get("type") == "video":
                                return 1, resource.get("download_url")

                        # अगर API से video नहीं मिला तो yt-dlp का उपयोग करें
                        proc = await asyncio.create_subprocess_exec(
                            "yt-dlp",
                            "-g",
                            "-f",
                            "best[height<=?720][width<=?1280]",
                            f"{link}",
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        stdout, stderr = await proc.communicate()
                        if stdout:
                            return 1, stdout.decode().split("\n")[0]
                        else:
                            return 0, stderr.decode()
                    else:
                        # API fail होने पर yt-dlp का उपयोग करें
                        proc = await asyncio.create_subprocess_exec(
                            "yt-dlp",
                            "-g",
                            "-f",
                            "best[height<=?720][width<=?1280]",
                            f"{link}",
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        stdout, stderr = await proc.communicate()
                        if stdout:
                            return 1, stdout.decode().split("\n")[0]
                        else:
                            return 0, stderr.decode()
        except Exception as e:
            # किसी error की स्थिति में yt-dlp का उपयोग करें
            proc = await asyncio.create_subprocess_exec(
                "yt-dlp",
                "-g",
                "-f",
                "best[height<=?720][width<=?1280]",
                f"{link}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if stdout:
                return 1, stdout.decode().split("\n")[0]
            else:
                return 0, f"API Error: {str(e)}"

    async def playlist(
        self, link, limit, user_id, videoid: Union[bool, str] = None
    ):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        playlist = await shell_cmd(
            f"yt-dlp -i --get-id --flat-playlist --playlist-end {limit} --skip-download {link}"
        )
        try:
            result = playlist.split("\n")
            for key in result:
                if key == "":
                    result.remove(key)
        except:
            result = []
        return result

    async def track(
        self, link: str, videoid: Union[bool, str] = None
    ):
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

    async def formats(
        self, link: str, videoid: Union[bool, str] = None
    ):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        # API से formats प्राप्त करें
        try:
            api_url = f"{self.api_base}{link}"
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        formats_available = []

                        for resource in data.get("data", {}).get("resources", []):
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
                            formats_available.append(format_info)

                        return formats_available, link
                    else:
                        # API fail होने पर yt-dlp का उपयोग करें
                        ytdl_opts = {"quiet": True}
                        ydl = yt_dlp.YoutubeDL(ytdl_opts)
                        with ydl:
                            formats_available = []
                            r = ydl.extract_info(link, download=False)
                            for format in r["formats"]:
                                try:
                                    str(format["format"])
                                except:
                                    continue
                                if not "dash" in str(format["format"]).lower():
                                    try:
                                        format["format"]
                                        format["filesize"]
                                        format["format_id"]
                                        format["ext"]
                                        format["format_note"]
                                    except:
                                        continue
                                    formats_available.append(
                                        {
                                            "format": format["format"],
                                            "filesize": format["filesize"],
                                            "format_id": format["format_id"],
                                            "ext": format["ext"],
                                            "format_note": format["format_note"],
                                            "yturl": link,
                                            "type": "video" if format.get("vcodec", "none") != "none" else "audio",
                                            "download_url": None
                                        }
                                    )
                        return formats_available, link
        except Exception:
            # किसी error की स्थिति में yt-dlp का उपयोग करें
            ytdl_opts = {"quiet": True}
            ydl = yt_dlp.YoutubeDL(ytdl_opts)
            with ydl:
                formats_available = []
                r = ydl.extract_info(link, download=False)
                for format in r["formats"]:
                    try:
                        str(format["format"])
                    except:
                        continue
                    if not "dash" in str(format["format"]).lower():
                        try:
                            format["format"]
                            format["filesize"]
                            format["format_id"]
                            format["ext"]
                            format["format_note"]
                        except:
                            continue
                        formats_available.append(
                            {
                                "format": format["format"],
                                "filesize": format["filesize"],
                                "format_id": format["format_id"],
                                "ext": format["ext"],
                                "format_note": format["format_note"],
                                "yturl": link,
                                "type": "video" if format.get("vcodec", "none") != "none" else "audio",
                                "download_url": None
                            }
                        )
            return formats_available, link

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
        thumbnail = result[query_type]["thumbnails"][0]["url"].split(
            "?"
        )[0]
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
    ) -> str:
        if videoid:
            link = self.base + link
        loop = asyncio.get_running_loop()

        def api_video_dl():
            try:
                import requests
                api_url = f"https://sdvytdl-3b7624f0b8a9.herokuapp.com/api/vidssave?link={link}"
                response = requests.get(api_url)
                if response.status_code == 200:
                    data = response.json()

                    # सबसे पहले 720P video ढूंढें
                    for resource in data.get("data", {}).get("resources", []):
                        if resource.get("type") == "video" and resource.get("quality") == "720P":
                            return resource.get("download_url")

                    # अगर 720P नहीं मिला तो कोई भी video return करें
                    for resource in data.get("data", {}).get("resources", []):
                        if resource.get("type") == "video":
                            return resource.get("download_url")

                    raise Exception("No video resources found")
                else:
                    raise Exception(f"API returned status code: {response.status_code}")
            except Exception as e:
                raise e

        def api_audio_dl():
            try:
                import requests
                api_url = f"https://sdvytdl-3b7624f0b8a9.herokuapp.com/api/vidssave?link={link}"
                response = requests.get(api_url)
                if response.status_code == 200:
                    data = response.json()

                    # सबसे अच्छा audio quality ढूंढें (best audio)
                    audio_resources = []
                    for resource in data.get("data", {}).get("resources", []):
                        if resource.get("type") == "audio":
                            audio_resources.append(resource)

                    if audio_resources:
                        # सबसे बड़ा size वाला audio return करें (best quality)
                        audio_resources.sort(key=lambda x: x.get("size", 0), reverse=True)
                        return audio_resources[0].get("download_url")
                    else:
                        raise Exception("No audio resources found")
                else:
                    raise Exception(f"API returned status code: {response.status_code}")
            except Exception as e:
                raise e

        def audio_dl():
            ydl_optssx = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, False)
            xyz = os.path.join(
                "downloads", f"{info['id']}.{info['ext']}"
            )
            if os.path.exists(xyz):
                return xyz
            x.download([link])
            return xyz

        def video_dl():
            ydl_optssx = {
                "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, False)
            xyz = os.path.join(
                "downloads", f"{info['id']}.{info['ext']}"
            )
            if os.path.exists(xyz):
                return xyz
            x.download([link])
            return xyz

        def song_video_dl():
            formats = f"{format_id}+140"
            fpath = f"downloads/{title}"
            ydl_optssx = {
                "format": formats,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])

        def song_audio_dl():
            fpath = f"downloads/{title}.%(ext)s"
            ydl_optssx = {
                "format": format_id,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "prefer_ffmpeg": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])

        if songvideo:
            await loop.run_in_executor(None, song_video_dl)
            fpath = f"downloads/{title}.mp4"
            return fpath
        elif songaudio:
            await loop.run_in_executor(None, song_audio_dl)
            fpath = f"downloads/{title}.mp3"
            return fpath
        elif video:
            if await is_on_off(config.YTDOWNLOADER):
                try:
                    # API से direct download link प्राप्त करें (720P preferred)
                    downloaded_file = await loop.run_in_executor(None, api_video_dl)
                    direct = None  # API से direct link है
                    return downloaded_file, direct
                except Exception as e:
                    # API fail होने पर yt-dlp का उपयोग करें
                    downloaded_file = await loop.run_in_executor(None, video_dl)
                    direct = True
                    return downloaded_file, direct
            else:
                proc = await asyncio.create_subprocess_exec(
                    "yt-dlp",
                    "-g",
                    "-f",
                    "best[height<=?720][width<=?1280]",
                    f"{link}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if stdout:
                    downloaded_file = stdout.decode().split("\n")[0]
                    direct = None
                else:
                    return
        else:
            try:
                # API से best audio download link प्राप्त करें
                downloaded_file = await loop.run_in_executor(None, api_audio_dl)
                direct = None  # API से direct link है
                return downloaded_file, direct
            except Exception as e:
                # API fail होने पर yt-dlp का उपयोग करें
                direct = True
                downloaded_file = await loop.run_in_executor(None, audio_dl)
                return downloaded_file, direct