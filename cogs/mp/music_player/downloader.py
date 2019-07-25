
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
import asyncio
import functools
import youtube_dl
#from config import *

from .paths import music_cache_path, music_local_path


class Logger(object):
    def debug(self, msg):
        print(msg)
    def warning(self, msg):
        pass
    def error(self, msg):
        print(msg)


ydl_options = {
    'source_address': '0.0.0.0',
    'format': '140/bestaudio/best', #priority 140=lightweight m4a
    'extractaudio': True,
    #'audioformat': "mp3",
    #'restrictfilenames': True,
    #'noplaylist': True,
    'nocheckcertificate': True,
	#'ignoreerrors': False,
    'ignoreerrors': True,
	#'logtostderr': False,
    'logger': Logger(),
    'quiet': True,
    'no_warnings': True,
    #'outtmpl': "data/audio/cache/%(id)s",
    'outtmpl': music_cache_path + '\\' + '%(title)s-%(extractor)s-%(id)s.%(ext)s',
    'default_search': 'auto'
}


class Downloader:
    def __init__(self):
        self.threadpool = ThreadPoolExecutor(max_workers=2)
        self.ydl = youtube_dl.YoutubeDL(ydl_options)

    async def extract(self, loop, url, **kwargs):
        #functools creates a callable
        return await loop.run_in_executor(self.threadpool,
            functools.partial(self.ydl.extract_info, url, **kwargs))    #ret callable dict

