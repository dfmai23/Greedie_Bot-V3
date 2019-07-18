import discord
import os
import sys
import platform
import subprocess
import shutil
import time

import requests
import hashlib
import zipfile as z
import json
import youtube_dl

from .paths import *

IS_WINDOWS = os.name == "nt"
IS_MAC = sys.platform == "darwin"
IS_64BIT = platform.machine().endswith("64")

#https://ffmpeg.zeranoe.com/builds/win64/static/ffmpeg-20190715-af5f770-win64-static.zip
#https://ffmpeg.zeranoe.com/builds/macos64/static/ffmpeg-20190715-af5f770-macos64-static.zip
FFMPEG_BUILDS_URL = 'https://ffmpeg.zeranoe.com/builds/'
FFMPEG_BUILD_DATE = 'ffmpeg-20190715-af5f770-'
FFMPEG_BUILD_ZIP = '-static.zip'
FFMPEG_FILES = {
    "ffmpeg.exe"  : "e0d60f7c0d27ad9d7472ddf13e78dc89",
    "ffplay.exe"  : "d100abe8281cbcc3e6aebe550c675e09",
    "ffprobe.exe" : "0e84b782c0346a98434ed476e937764f"
}


def check_codec():
    try:
        subprocess.call(["ffmpeg", "-version"], stdout=subprocess.DEVNULL)
    except FileNotFoundError:   #try fails, catch it
        player = False
    else:                       #try succeeds
        player = "ffmpeg"
        print('found ffmpeg player')

    if not player:
        if os.name == "nt":
            msg = "ffmpeg isn't installed, installing"
            download_ffmpeg('win64' if IS_64BIT else 'win32')
        else:   #macOS
            msg = "Neither ffmpeg nor avconv are installed, installing ffmpeg"
            download_ffmpeg('macos64' if IS_64BIT else 'macos32')
    return player

def download_ffmpeg(osver):

    redl = False;
    for filename in FFMPEG_FILES:   #check 3 exe files
        if os.path.isfile(filename):
            print("{} already present. Verifying integrity.".format(filename), end="")
            _hash = calculate_md5(filename)
            if _hash == FFMPEG_FILES[filename]:
                print(filename, _hash)
                continue
            else:
                print(filename, "Hash mismatch. Redownloading ffmpeg.")
                redl = True
                break
        else:
            redl = True
            break

    if redl is True:
        zipfile = FFMPEG_BUILD_DATE + osver + FFMPEG_BUILD_ZIP
        download_link = FFMPEG_BUILDS_URL + osver + '/static/' + zipfile
        print('download link:\n' + download_link)
        print("Downloading ffmpeg. Please wait.")

        r = requests.get(download_link)
        with open(zipfile, 'wb') as f:
            f.write(r.content)
            f.close()

        with z.ZipFile(zipfile, 'r') as zipObj: # Create a ZipFile Object and load zip into it
            files = zipObj.namelist()   # Get a list of all archived file names
            for file in files:          # Iterate over the file names
                filename = file.split('/')[-1]
                if filename in FFMPEG_FILES:
                    zipObj.extract(file)
                    shutil.move(file, './')
        os.remove(zipfile)
        shutil.rmtree(zipfile.replace('.zip', '/'))

    print("\nAll ffmpeg files have been downloaded.")

def calculate_md5(filename):
    hash_md5 = hashlib.md5()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def check_ytdl():
    try:
        if not discord.opus.is_loaded():
            discord.opus.load_opus('libopus-0.dll')
    except OSError:  # Incorrect bitness
        opus = False
    except:  # Missing opus
        opus = None
    else:
        opus = True

    if youtube_dl is None:
        raise RuntimeError("You need to run `pip3 install youtube_dl`")
    if opus is False:
        raise RuntimeError(
            "Your opus library's bitness must match your python installation's"
            " bitness. They both must be either 32bit or 64bit.")
    elif opus is None:
        raise RuntimeError(
            "You need to install ffmpeg and opus. See \"https://github.com/"
            "Twentysix26/Red-DiscordBot/wiki/Requirements\"")

def check_cfg():
    if not os.path.isdir(config_path):  # check directory
        print('config path: \'%s\' not found creating new one' % config_path)
        os.makedirs(config_path)
    if not os.path.isfile(config_loc):         #check file
        print("creating default music player config.json")
        config_loc_write = open(config_loc, 'w')
        json.dump(default_cfg, config_loc_write, indent=4)
        print("saved default config to JSON")
    if not os.path.isdir(music_cache_path):
        print('creating music cache folder')
        os.makedirs(music_cache_path)
    if not os.path.isdir(playlist_path):
        print('creating /playlists folder')
        os.makedirs(playlist_path)
