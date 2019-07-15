import discord
from redbot.core import commands, checks
from redbot.core.utils.chat_formatting import *

import aiohttp
import traceback
import asyncio
import os
import json
import sqlite3
import pprint
import copy

from apscheduler.schedulers.asyncio import AsyncIOScheduler
import time
import datetime

default_server_cfg = {
    "server_name": "undefined",
    "CHANNEL": "undefined",     #channel to post to
    "CHANNEL_NAME": "undefined",
    "TIME_POST": "12:00",       #default time to post wp everyday
    "CATEGORIES": []
}

default_cfg = {
    "SERVER_SETTINGS": {}
}

config_path = 'data\wallpaper\\'
config_file = 'config.json'
# dbread_path = 'data\wallpaper\\'
dbread_path = 'D:\Windows\AppData\Roaming\WallpaperMasterPro\\'
dbread_file = 'WallpaperMaster.db3'
dbwrite_path = 'data\Wallpaper\\'
dbwrite_file = 'WallpaperBot.db3'

class Wallpaper(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.settings = {}
        self.server_settings = {}

    """————————————————————WP Initializations————————————————————"""
    async def init(self):
        print('[%s]----------Wallpaper Initialization--------------------' % self.get_timefmt())
        self.init_settings()
        # self.bot.loop.create_task(self.init_scheduler())
        self.bot.add_listener(self.shutdown_watcher, 'on_message')

    def cog_unload(self):
        self.session.detach()

    def init_settings(self):
        print('loading WallpaperBot settings')
        fullpath = config_path + config_file
        if not os.path.isdir(config_path):  # check directory
            print('config path: \'%s\' not found creating new one' % config_path)
            os.makedirs(config_path)
        if not os.path.isfile(fullpath):  # check file
            file = open(fullpath, 'w')
            file.close()
        if os.path.getsize(fullpath) == 0:  # check if file empty
            print('config SETTINGS in file: \'%s\' not found creating them' % fullpath)
            file = open(fullpath, 'w')
            self.settings = default_cfg
            file.close()
            self.save_config()

        file = open(fullpath, 'r+')
        self.settings = json.load(file)
        # lines above: convert json server and channel key str to int
        self.settings["SERVER_SETTINGS"] = {int(key): val for key, val in self.settings["SERVER_SETTINGS"].items()}
        for server, values in self.settings["SERVER_SETTINGS"].items():
            try:
                self.settings["SERVER_SETTINGS"][server]["CHANNEL"] = int(self.settings["SERVER_SETTINGS"][server]["CHANNEL"])
            except:
                print('undefined channel found, skipping conversion')
                pass
        self.server_settings = self.settings["SERVER_SETTINGS"]
        file.close()

        for server in self.bot.guilds:
            if not server.id in self.server_settings:  # create new default server settings
                print(' Server settings for %s %s not found, creating defaults' % (server.id, server.name))
                self.server_settings[server.id] = copy.deepcopy(default_server_cfg)
                self.server_settings[server.id]["server_name"] = server.name
        self.save_config()

    async def init_scheduler(self):
        print('\ninitializing wallpaper scheduler')
        scheduler = AsyncIOScheduler()
        for server in self.bot.guilds:
            print("scheduling server: %s %s" % (server.id, server.name))
            post_time = self.server_settings[server.id]["TIME_POST"]
            time = datetime.datetime.strptime(post_time, '%H:%M')  # strip using datetime
            # scheduler.add_job(self.post_auto, 'cron', [server], hour=time.hour, minute=time.minute)
            scheduler.add_job(self.wpstat, 'interval', [server], seconds=60) #for testing
        scheduler.start()


    """————————————————————Watchers————————————————————"""
    async def shutdown_watcher(self, message):  # catch at message before it actually does anything
        prefixes = await self.bot.get_prefix(message)
        if (message.content in [prefix + 'shutdown' for prefix in prefixes] or
                message.content in [prefix + 'restart' for prefix in prefixes]):
            for server in self.bot.guilds:
                print('saving wallpaper settings and categories:', server.id, server.name)
            self.save_config()
            return

    """————————————————————Helper Fn's————————————————————"""
    def save_config(self):  # save config for current server
        cfg_file = open(config_path + config_file, 'w')
        json.dump(self.settings, cfg_file, indent=4)
        print('Saving WallpaperBot config')

    def get_timefmt(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


    """————————————————————Commands————————————————————"""
    @checks.admin()
    @commands.command()
    async def set_wpchannel(self, ctx, channel_id):
        """ Set the channel to schedule posts to """
        server = ctx.message.server
        channel = server.get_channel(channel_id)
        print("channel: %s  type: %s " % (channel.id, str(type(channel.id))))

        self.server_settings[server.id]["CHANNEL"] = channel.id
        self.server_settings[server.id]["CHANNEL_NAME"] = channel.name
        self.save_config()
        await self.bot.say("Assigned channel: %s to post daily wallpapers!~" % channel.name)

    # @commands.command()
    async def wpstat(self, ctx):
        """ DEBUG, show settings """
        print('[%s]----------WP STAT--------------------' % self.get_timefmt())
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(self.settings)
