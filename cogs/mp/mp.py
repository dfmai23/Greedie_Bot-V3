import discord
from redbot.core import commands, checks
from redbot.core.utils.chat_formatting import *

import os
import subprocess
import threading
import traceback
import logging
import time
import asyncio
import random
import json
import xml.etree.ElementTree as etree
import xml.dom.minidom
import re           #re.compile() and pattern matching
import youtube_dl
import copy
import aiohttp

from tinytag import TinyTag as TTag
from .music_player.downloader import Downloader, music_cache_path, music_local_path
from .music_player.playlist import Playlist, playlist_path, playlist_local_path #, default_playlist
from .music_player.song import Song
from .music_player.paths import *
from .music_player.state import State


class Music_Player(commands.Cog):
    def __init__(self, bot, codec):
        self.bot = bot              #class discord.Client
        self.codec = codec
        self.session = aiohttp.ClientSession()
        self.settings = {}
        self.server_settings = {}   #server specfic settings
        self.playlists = {} #music queues for each server
        self.states = {}    #status of each music player, ie. playing/paused
        self.games = {}
        self.game = None
        self.downloader = Downloader()


    """————————————————————MP Initialization's————————————————————"""
    async def init(self):
        print('[%s]----------MP Initialize--------------------' % self.get_timefmt())
        self.init_settings()
        self.init_playlists()
        self.init_states()
        self.init_games()

        self.bot.add_listener(self.shutdown_watcher, 'on_message')  #watcher no log on init
        self.bot.loop.create_task(self.playlist_scheduler())        #schedule->manager no log on init
        self.bot.loop.create_task(self.voice_channel_watcher())
        print('starting Music Player with codec: ' + self.codec)

    def cog_unload(self):
        self.session.detach()

    def init_settings(self):
        print('loading music player settings')
        self.settings = json.load(open(config_loc, 'r'))
        self.settings["SERVER_SETTINGS"] = {int(key): val for key, val in self.settings["SERVER_SETTINGS"].items()}
        self.settings["AUTOJOIN_CHANNELS"] = [int(channel) for channel in self.settings["AUTOJOIN_CHANNELS"]]
        self.server_settings = self.settings["SERVER_SETTINGS"]
        default_server_cfg = self.settings["DEFAULT_SERVER_SETTINGS"]
        # print("default_server_cfg: " + str(default_server_cfg))

        for server in self.bot.guilds:
            if not server.id in self.server_settings:  # create new default server settings
                print('  server settings for %s %s not found, creating defaults' % (server.id, server.name))
                self.server_settings[server.id] = copy.deepcopy(default_server_cfg)
                self.server_settings[server.id]["server_name"] = server.name
        self.save_config()

    """Initializes playlists by:
        -creating empty queues for each server
        -reading saved "saved playlist"
        -loading playlist    """
    """Initializes autojoining by:
        -autojoining channels from settings file and owner channel
        -loading its last playlist
        -starts playing if channel not empty  """
    def init_playlists(self):
        print('loading Playlists')
        playlists = {}      #map
        for server in self.bot.guilds:
            print(' ', server.id, server.name)
            self.load_pl(server, default_playlist, init=True)

    def init_states(self):
        print('loading default states')
        states = {}
        for server in self.bot.guilds:
            states[server.id] = State.STOPPED
        self.states = states

    def init_games(self):
        for server in self.bot.guilds:
            self.games[server.id] = None

    async def init_autojoin(self):
        print('\nmedia player autojoining Channels')
        # for cid in self.settings["AUTOJOIN_CHANNELS"]:
        #     print("channels: " + cid)
        # print("autojoin: " + str(self.settings["AUTOJOIN"]))
        # states = []
        if self.settings["AUTOJOIN"] is True:
            for c_id in self.settings["AUTOJOIN_CHANNELS"]:
                channel= self.bot.get_channel(c_id) #channel to join
                server = channel.guild
                try:
                    voice_client = channel.connect()
                    print("voice client: " + voice_client.user.name)
                    print('  joining channel:', server.id, server.name, ', ', channel.id, channel.name)
                    #await self.bot.send_message('Hi!~')
                except Exception as e:
                    print("Exception: " + str(e))
                except:
                    print('  already in channel, skipping:', server.id, server.name, ', ', channel.id, channel.name)

                try:    #autoplay
                    self.mp_start(server, self.playlists[server.id].list[0])
                    #self.mp_pause(server)
                except:
                    print('  empty playlist, skipping autoplay')


    """————————————————————Watchers————————————————————"""
    #saves playlists and configs
    async def shutdown_watcher(self, message):  #catch at message before it actually does anything
        prefixes = await self.bot.get_prefix(message)
        if (message.content in [prefix + 'shutdown' for prefix in prefixes] or
        message.content in [prefix + 'restart' for prefix in prefixes]):
            for server in self.bot.guilds:
                try:
                    print('saving music player settings and playlist:', server.id, server.name)
                    pl = self.playlists[server.id]
                    pl.save(default_playlist, server, overwrite=1)
                    try:
                        print('  attempting to stop music player')
                        self.mp_stop(server)
                    except:
                        print('  Music playing already stopped!')
                        pass
                except Exception as e:
                    traceback.print_exc()
                    print('couldn\'t save music player settings:', server.id, server.name)
                    pass
            self.save_config()
            return

    #basically asynchronously polls music player to see if its playing or not
    async def playlist_scheduler(self):
        print('creating playlist scheduler')
        while self == self.bot.get_cog('Music_Player'): #while music player class is alive
            tasks = []
            #playlists = copy.deepcopy(self.playlists)
            for server_id in self.playlists:             #returns the key for each playlist
                if len(self.playlists[server_id].list) == 0:     #do nothing if playlist empty
                    continue        #skip rest of loop
                #full concurrency, creates task for each server
                tasks.append(self.bot.loop.create_task(self.playlist_manager(server_id)))
            completed = [t.done() for t in tasks]
            while not all(completed):
                completed = [t.done() for t in tasks]   #schedule it
                await asyncio.sleep(0.5)
            await asyncio.sleep(3)  #reload every x seconds

    async def playlist_manager(self, server_id):
        server = self.bot.get_guild(server_id)
        mp = server.voice_client

        # pl = self.playlists[server.id]
        # print(mp.is_playing(), self.states[server.id])
        try:
            if not mp.is_playing() and self.states[server.id] != State.STOPPED:    #stopped playing music
                print('[%s]----------WATCHER: playlist manager--------------------' % self.get_timefmt())
                print('audio has stopped, playing next song')
                print(server.id, server.name)
                next_song = await self.get_nxt_song(server)
                if next_song == None:  #repeat off, end of playlist
                    print('repeat is off, next song is NoneType')
                    pass
                else:
                    self.mp_start(server, next_song)
                await self.check_nextnext_song(server)  #last so next song can play first
        except:
            pass

    async def voice_channel_watcher(self):  #stops music when channel is empty
        print('creating voice channel watcher')
        while self == self.bot.get_cog('Music_Player'):
            for vc in self.bot.voice_clients:
                server = vc.guild
                channel = vc.channel
                if len(channel.members) == 1 and self.states[server.id] != State.STOPPED:
                    self.mp_stop(server)
                    print('channel empty, stopping music:', server.name, channel.name)
            await asyncio.sleep(5)


    """————————————————————Generics————————————————————"""
    def mp_play(self, server):
        music_player = self.get_mp(server)
        music_player.resume()
        self.states[server.id] = State.PLAYING

    def mp_pause(self, server):
        music_player = self.get_mp(server)
        if music_player.is_playing():
            music_player.pause()
            self.states[server.id] = State.PAUSED

    def mp_start(self, server, audio):  #audio=song object, joins voice channel by channel id
        media_player = server.voice_client
        # print (server.voice_client.is_connected())
        # print(voice_client)
        ffmpeg_options = '-b:a 64k -bufsize 64k'
        audio_source = discord.FFmpegPCMAudio(audio.path, options=ffmpeg_options)
        media_player.play(audio_source, after=lambda e: print('music player.play done:', e))
        media_player.pause()
        media_player.source = discord.PCMVolumeTransformer(media_player.source)
        media_player.source.volume = self.server_settings[server.id]["VOLUME"]

        self.states[server.id] = State.PLAYING
        self.playlists[server.id].now_playing = audio

        if self.playlists[server.id].cur_i == -1:
            self.playlists[server.id].cur_i = 0    #new playlist
        else:   #update index
            self.playlists[server.id].cur_i = self.playlists[server.id].get_i(audio)   #accounts for skipping and going back
        media_player.resume()
        print('playing:', audio.path)
        # self.bot.loop.create_task(self.set_game(audio))

    def mp_stop(self, server):
        music_player = self.get_mp(server)
        music_player.stop()
        self.states[server.id] = State.STOPPED

    def mp_reload(self, server):
        pl = self.playlists[server.id]

        try:
            self.mp_stop(server)
        except:
            pass

        if len(pl.list) == 0:
            print('playlist empty, skipping playing')
            return

        #if index==None: song = pl.list[pl.cur_i]
        #else: song = pl.list[index]
        song = pl.list[0]
        self.mp_start(server, song)
        self.mp_pause(server)       #restarts music player in a robust fashion to first song in playlist

    def get_mp(self, server):             #get music player of current server
        music_player = server.voice_client
        return music_player

    """Adds a song to the playlist
        -Checks if its a url or local song
        -Will add to playlist
        -Autoplay if only one in playlist """
    async def add_song(self, ctx, song_or_url):
        server = ctx.guild
        pl = self.playlists[server.id]

        is_url = re.compile(r'^(?:http|ftp)s?://' # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
        r'localhost|' #localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
        r'(?::\d+)?' # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)  #sublink (.com/... including /),

        if is_url.match(song_or_url):   #download or find in cache
            url = song_or_url
            info = await self.downloader.extract(self.bot.loop, url, download=False, process=False)    #get info only
            if info['extractor_key'] in ['YoutubePlaylist', 'SoundcloudSet', 'BandcampAlbum']:
                await ctx.send('Please use "add_p" command for URL playlists!')
                return
            info = await self.downloader.extract(self.bot.loop, url)    #get info and download song
            pattern = r'\<|\>|\:|\"|\/|\\|\||\?|\*'
            info['title'] = re.sub(pattern, '_', info['title'])
            print(info['title'])
            song_loc = music_cache_path + '\\' + info['title'] +'-'+ info['extractor'] +'-'+ info['id'] + '.' + info['ext']
            song = Song(info['title'], info['duration'], song_loc, info['webpage_url'])
        else:    #find local file in library
            name = song_or_url
            ftype = r'(m4a|mp3|webm)$'  #regex, $ = match the end of the string
            song_loc = self.find_file(name, music_local_path, ftype)
            if song_loc == None:  #song not in lib
                return 3
            tags = TTag.get(song_loc)
            if tags.title == None:
                pattern = r'\.(mp3|m4a)$'
                tags.title = os.path.basename(song_loc).strip(pattern)
            song = Song(tags.title, tags.duration, song_loc, None, artist=tags.artist)

        song_added = pl.add(song)
        if song_added == 3:
            await ctx.send('Coudn\'t find song in library!~')
        elif song_added == 2:
            await ctx.send('Song already in playlist!')
        else:
            song_display = song.display()
            await ctx.send('Added to playlist!~' + box(song_display))

        if len(pl.list) == 1:    #autoplay
            self.mp_start(server, song)

    async def get_nxt_song(self, server):
        pl = self.playlists[server.id]
        if pl.order[pl.cur_i] == None and pl.repeat == 'one':  #reached end of playlist
            return None

        if pl.repeat == 'one':
            next_song_i = pl.cur_i
        else:
            next_song_i = pl.order[pl.cur_i]
        next_song = pl.list[next_song_i]
        print('cur_i: %d \tnext_i: %d' % (pl.cur_i, next_song_i))
        song_file = os.path.basename(next_song.path)
        base_path = os.path.dirname(next_song.path)
        print('Getting next song:', base_path+'\\'+song_file)
        if pl.get_file(song_file, base_path) == None:   #file not found, skip or check url
            if next_song.url == None:
                pl.cur_i = next_song_i    # to get next next song
                await self.bot.send('File not found, skipping song!~\n' + box(next_song.title + ' - ' + next_song.artist))
                return await self.get_nxt_song(server)
            else:   #url song
                info = await self.downloader.extract(self.bot.loop, next_song.url)  #download song
        return next_song

    async def check_nextnext_song(self, server):  #preloads the next next song after the current song if it is a url song\
        pl = self.playlists[server.id]
        if pl.order[pl.cur_i] == None:  #reached end of playlist
            return None

        next_song_i = pl.order[pl.cur_i]
        nextnext_song_i = pl.order[next_song_i]    #concurrent, cur_i not updated yet
        nextnext_song = pl.list[nextnext_song_i]
        print('Checking next next song:', nextnext_song.path)
        if nextnext_song.url != None:
            info = await self.downloader.extract(self.bot.loop, nextnext_song.url)

    async def set_game(self, song):
        self.game = list(self.bot.servers)[0].me.game
        status = list(self.bot.servers)[0].me.status

        if song.artist == '':
            gamename = song.title
        else:
            gamename = song.title + ' by ' + song.artist

        game = discord.Game(name=gamename)
        await self.bot.change_presence(status=status, game=game)

        """
        if self._old_game is False:
            self._old_game = list(self.bot.servers)[0].me.game
        status = list(self.bot.servers)[0].me.status
        game = discord.Game(name=song.title)
        await self.bot.change_presence(status=status, game=game)
        """

    """Loads a local/saved playlist
        -will create empty Playlist() class
        -if init is on then will search specifically for "saved_playlist.xml" from data/music
        -else will search for playlist with closest name
        -if init is on will also create server playlist path if not found and load the empty playlist
        -processes the playlist """
    def load_pl(self, server, playlist_name, **kwargs):          #** = forces keyword arg in caller
        server_cfg = self.server_settings[server.id]
        print("server_cfg:" + str(server_cfg))
        playlist = Playlist(server.id, server_cfg["REPEAT"], server_cfg["SHUFFLE"])   #create empty playlist
        try:
            self.mp_stop(server)
        except:
            pass
        self.playlists[server.id] = playlist.load(playlist_name, server, **kwargs)

        if self.playlists[server.id] == None:
            return None
        # self.playlists[server.id].view()


    """————————————————————Commands Music Player————————————————————"""
    @commands.command()
    async def play(self, ctx, *, song_or_url=None): # * = positional forced-keyword only varargs (song_or_url in this case)
        """ Plays/resumes current song or plays new song """
        print('[%s]----------MP PLAY--------------------' % self.get_timefmt())
        server = ctx.guild
        cur_state = self.states[server.id]
        pl = self.playlists[server.id]
        mp = self.get_mp(server)

        print("song_or_url: " + 'None' if song_or_url is None else song_or_url)
        if song_or_url is not None:
            tasks = [self.add_song(ctx, song_or_url)]   # running it synchronously,
            await asyncio.wait(tasks)                   #can also do with loop.run_until_complete???

            song = pl.list[-1]
            self.mp_stop(server)
            self.mp_start(server, song)
            song_display = str(len(pl.list)-1) + ". " + song.display()
            await ctx.send('playing song: ' + box(song_display))
            return

        if len(pl.list) == 0:
            await ctx.send('Playlist Empty!~')
            return

        if cur_state == State.PAUSED:
            self.mp_play(server)
            await ctx.send("Playing music!~")
        elif cur_state == State.PLAYING:
            self.mp_pause(server)
            await ctx.send("Pausing music!~")
        elif cur_state == State.STOPPED:        #restart song
            self.mp_start(server, pl.list[pl.cur_i])
            await ctx.send("Playing music!~")

    @commands.command()
    async def pause(self, ctx):
        """Pauses current song """
        server = ctx.guild
        self.mp_pause(server)
        await ctx.send("Pausing music!~")

    @commands.command()
    async def stop(self, ctx):
        """Stops current song"""
        server = ctx.guild
        self.mp_stop(server)
        await ctx.send("Stopping music!~")

    """————————————————————Commands Playlist————————————————————"""


    """————————————————————Commands Server————————————————————"""
    @checks.admin()
    @commands.command()
    async def join_vc(self, ctx):
        """ Joins voice channel user is connected to"""
        print('[%s]----------VC JOIN--------------------' % self.get_timefmt())
        author = ctx.author     #ctx = context
        server = ctx.guild
        channel = author.voice.channel  #channel to join

        voice_client = ctx.guild.voice_client
        if voice_client is not None:    #is_connected wont work?
            if voice_client.channel.id == author.voice.channel.id:
                print('already connected to voice channel')
                await ctx.send("Already connected to your channel!~")
                return
            await voice_client.disconnect()

        print('joining voice channel:', channel.id, channel.name)
        await channel.connect()          #joins owners voice channel only
        self.mp_reload(server)

    @checks.admin()
    @commands.command()
    async def leave_vc(self, ctx):
        """Leave voice channel"""
        print('[%s]----------VC LEAVE--------------------' % self.get_timefmt())
        server = ctx.guild
        print("leaving voice channel: ", server.id, server.name)

        if ctx.guild.voice_client.is_connected():
            voice_client = ctx.guild.voice_client
            await voice_client.disconnect()
        else:
            print("unable to leave voice channel!")

    @checks.admin()
    @commands.command()
    async def rejoin(self, ctx):
        """Rejoins voice channel"""
        server = ctx.guild
        author = ctx.author
        voice_client = ctx.guild.voice_client
        channel = voice_client.channel
        await voice_client.disconnect()
        await channel.connect()
        self.mp_reload(server)

    @checks.admin()
    @commands.command()
    async def pinfo(self, ctx, url):
        """ DEBUG: playlist URL info debug"""
        print('[%s]----------PLAYLIST URL INFO--------------------' % self.get_timefmt())
        server = ctx.guild
        info = await self.downloader.extract(self.bot.loop, url, download=False)
        if info != None:
            for key in info:
                if key == 'formats':
                    print(key, info[key])
                    continue
                """
                if key == 'entries':
                    for entry in info['entries']:
                        for key2 in entry:
                            print(key2, entry[key2])
                """
                print(key, info[key])
                """
                if key == 'formats':
                    ext = info[key][0]['ext']   #multiple m4a links, 0=pull first one
                    url = info[key][0]['url']
                    print(ext, url)
                """
        else:
            print('not able to get playlist info')

    @checks.admin()
    @commands.command()
    async def mpstat(self, ctx):
        """DEBUG: media player info debug"""
        print('[%s]----------MP STAT--------------------' % self.get_timefmt())
        server = ctx.guild
        vc = ctx.guild.voice_client
        channel = vc.channel
        mp = vc
        pl = self.playlists[server.id]
        #print(music_cache_path + '%(extractor)s' + '-' + '%(exts)s')
        #str = music_cache_path + '%(extractor)s' + '-' + '%(exts)s'

        print('server info')
        print('  server :', server.id, server.name)
        print('  channel:', channel.id, channel.name)

        print('playlist info')
        print('  name: ' + pl.title)
        print('  size: ' + str(len(pl.list)))
        print('  now playing: ' + ('none' if len(pl.list)==0 else pl.now_playing.title))
        print('  current index: ' + str(pl.cur_i))
        print('  playlist order: ' + str(pl.order))

        print('music player state')
        state_msg = '  state: '
        if not mp.is_playing() and not mp.is_paused():
            state_msg += "stopped"
        elif mp.is_paused():
            state_msg += "paused"
        elif mp.is_playing():
            state_msg += "playing"
        print(state_msg)
        print('  class:', self.states[server.id].value)

        print('server info')
        for key, val in self.server_settings[server.id].items():
            print(' ', key, val)

    """————————————————————Helper Fn's————————————————————"""
    def save_config(self):      #save config for current server
        config_loc_write = open(config_loc, 'w')
        json.dump(self.settings, config_loc_write, indent=4) #in:self.settings, out:config_file
        print('saving music player config for servers')

    def get_timefmt(self):
        return time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime())
