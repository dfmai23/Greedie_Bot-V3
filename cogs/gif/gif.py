import discord
from redbot.core import commands, checks
from redbot.core.utils.chat_formatting import *

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
        print('init_settings')
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
        self.settings["SERVER_SETTINGS"] = {int(key): val for key, val in self.settings["SERVER_SETTINGS"].items()}
        self.server_settings = self.settings["SERVER_SETTINGS"]  #line above: convert json server key str to int
        file.close()

        for server in self.bot.guilds:
            # if not os.path.isdir(config_path + server.id): #check server directory for local embedds
            #     print('  Server folder for %s not found, creating default: %s' % (server.name, config_path + server.id))
            #     os.makedirs(config_path + server.id)
            if not server.id in self.server_settings:  # create new default server settings
                print('  Server settings for %s %s not found, creating defaults' % (server.id, server.name))
                self.server_settings[server.id] = copy.deepcopy(default_server_cfg)
                self.server_settings[server.id]["server_name"] = server.name
        self.save_config()


    """————————————————————Watchers————————————————————"""
    async def shutdown_watcher(self, message):  # catch at message before it actually does anything
        prefixes = await self.bot.get_prefix(message)
        if (message.content in [prefix + 'shutdown' for prefix in prefixes] or
                message.content in [prefix + 'restart' for prefix in prefixes]):
            print('[%s]----------GIF shutdown watcher--------------------' % self.get_timefmt())
            print('prefixes: ', prefixes)
            for server in self.bot.guilds:
                print('saving GIFBot settings for :', str(server.id), server.name)
            self.save_config()
            return


    """————————————————————Helper Fn's————————————————————"""
    def save_config(self):      #save config for current server
        cfg_file = open(config_path + config_file, 'w')
        json.dump(self.settings, cfg_file, indent=4) #in:self.settings, out:file
        print('saving GIFBot config')   #auto converts int to str in json.dump

    def get_timefmt(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


    """————————————————————Commands————————————————————"""
    @commands.command(pass_context=True)
    async def add_gif(self, ctx, gifname, link):
        """ Add an embedded gif to server """
        server = ctx.guild
        gifs = self.server_settings[server.id]["EMBEDDEDS"]

        print('[%s]----------ADD GIF--------------------' % self.get_timefmt())
        is_url = re.compile(r'^(?:http)s?://' # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?))' #domain
        r'(?:/?(.*\.(gif|webm)?))$', re.IGNORECASE)  #gif sub path
        # r'(?:/?|[/?]\S+)$', re.IGNORECASE)  # any sub-path
        # sub_pattern = r'(webm|gifv)$'
        sub_pattern = re.compile(r'(webm)$')

        match = re.match(is_url, link)
        if match is None:
            print('could not find a valid link: ' + link)
            await ctx.send('Could not find a valid link. Try Again!~')
            return

        if gifname not in gifs:
            #will download the link locally
            newlink=link
            if match.group(2) != 'gif': #convert webm formats to gif
                print('link not given in gif format, attempting to convert')
                newlink = re.sub(sub_pattern, 'gif', link)
                match = re.match(is_url, newlink)
                print('oldlink: %s\nnewlink: %s' % (link, newlink))
            # filename = match.group(1)  # get gif file, https://regex101.com/r/6uKlDz/2/
            # location = config_path + server.id + '\\' + filename

            location = match.string
            # file, headers = urllib.request.urlretrieve(link, location)
            gifs[gifname] = location
            print('added gif, gifname: %s   link: %s' % (gifname, newlink))
            # print('added gif, gifname: %s   link: %s\npath: %s' % (gifname, link, location))    #for local files
            # print('headers: ' + str(headers)) #html headers
            await ctx.send('Saved the gif %s!~' % gifname)
        else:
            print('key already found: ' + gifname)
            print(gifs[gifname])
            await ctx.send('GIF already saved! Use a different name!~')

    @commands.command()
    async def remove_gif(self, ctx, gifname):
        """ Removes gif from server """
        print('[%s]----------REMOVE GIF--------------------' % self.get_timefmt())
        server = ctx.guild

        gifs = self.server_settings[server.id]["EMBEDDEDS"]
        if gifname not in gifs:
            print('key not found: ' + gifname)
            await ctx.send('GIF not found!~')
        else:
            print('removed gif: %s %s' %(gifname, str(gifs[gifname])))
            gifs.pop(gifname)
            await ctx.send('GIF successfully removed!~')

    @commands.command()
    async def gif(self, ctx, gifname):
        """ Use the embedded gif """
        server = ctx.guild
        channel = ctx.channel

        gifs = self.server_settings[server.id]["EMBEDDEDS"]
        if gifname not in gifs:
            await ctx.send('Could not find gif!~')
            return
        link = gifs[gifname]
        embed = discord.Embed()
        embed.set_image(url=link)
        await channel.send(embed=embed)
        # await self.bot.send_message(channel, embed=embed)
        # await self.bot.send_file(channel, gif_loc)

        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(self.settings)

    @commands.command()
    async def view_gifs(self, ctx):
        """ List the embedded gifs """
        print('[%s]----------VIEW GIFS--------------------' % self.get_timefmt())
        server = ctx.guild

        gifs = self.server_settings[server.id]["EMBEDDEDS"]
        gifs_display = []
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(gifs)
        for gifname, giflink in gifs.items():
            gifs_display.append(gifname)
        await ctx.send('The current gifs are: ' + box('') if len(gifs) == 0 else box(', '.join(gifs_display)),
                           delete_after=60)

    @checks.admin()
    @commands.command()
    async def save_gifs(self, ctx):
        """ Save the current embedded gifs """
        print('[%s]----------SAVE GIFS--------------------' % self.get_timefmt())
        self.save_config()
        await ctx.send('Saved gif bot settings!')

    @checks.admin()
    @commands.command()
    async def ginfo(self, ctx, link):
        """ DEBUG: post given gif info """
        print("[%s]------------GIF INFO--------------------" % self.get_timefmt())
        server = ctx.guild
        channel = ctx.channel

        print('link: ' + link)
        embed = discord.Embed()
        embed.set_image(url=link)
        print('title: ' + str(embed.title))
        print('type: ' + str(embed.type))
        print('url: ' + str(embed.url))
        print('descr: ' + str(embed.description))
        print('image: ' + str(embed.image))
        print('image.url: ' + str(embed.image.url))
        print('proxy.url: ' + str(embed.image.proxy_url))
        print('dim: %s x %s' % (str(embed.image.height), str(embed.image.width)))
        print('thumbnail.url: ' + str(embed.thumbnail.url))
        print('video: ' + str(embed.video))
        message = await self.channel.send(embed=embed)
        # message = await self.bot.send_message(channel, content=link)
        # message = await self.bot.get_message(channel, link)

        print('\ntimestamp: ' + str(message.timestamp))
        print('content: ' + message.content)
        print('embeds: ')
        for emb in message.embeds:
            for field in emb.items():
                print('  ' + str(field))

    @checks.admin()
    @commands.command()
    async def gstat(self, ctx):
        """ DEBUG: show settings """
        print('[%s]----------GIF STAT--------------------' % self.get_timefmt())
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(self.settings)
        pp.pprint(self.server_settings)

