import discord
from redbot.core import commands

import aiohttp
import os
import json
import time
import urllib.request
import re
import pprint
import copy

default_cfg = {
    "SERVER_SETTINGS": {}
}

default_server_cfg = {
    "server_name": "undefined",
    "EMBEDDEDS": {}
}

#format
test = {
    "SERVER_SETTINGS": {
        "server_id": {
            "server_name": "name",
            "EMBEDDEDS": {
                "embed_name": "location"
            }
        }
    }
}
config_path = 'data\gif\\'
config_file = 'config.json'


class GIF(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.settings = {}
        self.server_settings = {}


    """————————————————————GIF Initializations————————————————————"""
    async def init(self):
        print('[%s]----------GIF Initialize--------------------' % self.get_timefmt())
        self.init_settings()
        self.bot.add_listener(self.shutdown_watcher, 'on_message')

    def cog_unload(self):
        self.session.detach()

    def init_settings(self):
        print('init_settings GIF')
        fullpath = config_path + config_file
        if not os.path.isdir(config_path):  # check directory
            print('  config path: \'%s\' not found creating new one' % config_path)
            os.makedirs(config_path)
        if not os.path.isfile(fullpath):  # check file
            file = open(fullpath, 'w')
            file.close()
        if os.path.getsize(fullpath) == 0:  # check if file empty
            print('  config SETTINGS in file: \'%s\' not found creating them' % fullpath)
            file = open(fullpath, 'w')
            self.settings = default_cfg
            file.close()
            self.save_config()

        file = open(fullpath, 'r+')
        self.settings = json.load(file)
        self.server_settings = self.settings["SERVER_SETTINGS"]
        file.close()

        for server in self.bot.guilds:
            # if not os.path.isdir(config_path + server.id): #check server directory for local embedds
            #     print('  Server folder for %s not found, creating default: %s' % (server.name, config_path + server.id))
            #     os.makedirs(config_path + server.id)
            server_id = str(server.id)
            if not server_id in self.server_settings:  # create new default server settings
                print('  Server settings for %s %s not found, creating defaults' % (server_id, server.name))
                self.server_settings[server_id] = copy.deepcopy(default_server_cfg)
                self.server_settings[server_id]["server_name"] = server.name
        self.save_config()


    """————————————————————WATCHERS————————————————————"""
    async def shutdown_watcher(self, message):  # catch at message before it actually does anything
        prefixes = self.bot.settings.prefixes
        if (message.content in [prefix + 'shutdown' for prefix in prefixes] or
                message.content in [prefix + 'restart' for prefix in prefixes]):
            for server in self.bot.guilds:
                print('saving gif bot settings:', str(server.id), server.name)
            self.save_config()
            return


    """————————————————————Helper Fn's————————————————————"""
    def save_config(self):      #save config for current server
        cfg_file = open(config_path + config_file, 'w')
        json.dump(self.settings, cfg_file, indent=4) #in:self.settings, out:file
        print('Saving GIFBot config')

    def get_timefmt(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

