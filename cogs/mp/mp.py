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
            if not mp.is_playing() and \
                    self.states[server.id] != State.STOPPED and self.states[server.id] != State.PAUSED:    #stopped playing music
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
        self.mp_start(server, song)     #restarts music player in a robust fashion to first song in playlist
        # self.mp_pause(server)         #testing

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
            # print(info)
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
        print("  server_cfg:" + str(server_cfg))
        playlist = Playlist(server.id, server_cfg["REPEAT"], server_cfg["SHUFFLE"])   #create empty playlist
        try:
            self.mp_stop(server)
        except:
            pass
        self.playlists[server.id] = playlist.load(playlist_name, server, **kwargs)

        if self.playlists[server.id] == None:
            return None
        # self.playlists[server.id].view()
        return self.playlists[server.id]

    async def load_url_pl(self, server, info, playlist):     #returns a list of Songs
        url_playlist = []
        base_url = info['webpage_url'].split('playlist?list=')[0]
        for entry in info['entries']:
            if entry:       #check deleted vids
                try:        #check blocked vids
                    if info['extractor_key'] == 'YoutubePlaylist':
                        song_url = base_url + 'watch?v=%s' % entry['id']
                    else:   #'SoundcloudSet', 'BandcampAlbum'
                        song_url = entry['url']
                    print('PROCESS DOWNLOAD')
                    info = await self.downloader.extract(self.bot.loop, song_url, download=True)
                    if info == None:
                        continue
                    #print(song_url)
                    pattern = r'\<|\>|\:|\"|\/|\\|\||\?|\*'
                    info['title'] = re.sub(pattern, '_', info['title'])
                    song_loc = music_cache_path + '\\' + info['title'] +'-'+ info['extractor'] +'-'+ info['id'] + '.' + info['ext']
                    song = Song(info['title'], info['duration'], song_loc, info['webpage_url'])
                    url_playlist.append(song)
                except:
                    pass
        return url_playlist


    """————————————————————Commands Music Player————————————————————"""
    @commands.command()
    async def play(self, ctx, *, song_or_url=None): # * = positional forced-keyword only varargs (song_or_url in this case)
        """ Plays/resumes current song or plays new song """
        print('[%s]----------MP PLAY--------------------' % self.get_timefmt())
        server = ctx.guild
        cur_state = self.states[server.id]
        pl = self.playlists[server.id]
        mp = self.get_mp(server)

        print("input song_or_url: " + 'None, attempting to play/resume' if song_or_url is None else song_or_url)
        if song_or_url is not None:
            tasks = [self.add_song(ctx, song_or_url)]   # running it synchronously,
            await asyncio.wait(tasks)                   #can also do with loop.run_until_complete???

            song = pl.list[-1]
            self.mp_stop(server)
            self.mp_start(server, song)
            song_display = str(len(pl.list)-1) + ". " + song.display()
            await ctx.send('Playing song~: ' + box(song_display))
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

    @commands.command()
    async def skip(self, ctx):
        """ Skips current song """
        server = ctx.guild
        mp = self.get_mp(server)
        pl = self.playlists[server.id]
        self.mp_stop(server)

        #get next song in playlist
        next_song = await self.get_nxt_song(server)
        if next_song == None:  #reached end of playlist
            await ctx.send("Reached end of Playlist!~")
            return
        nxt_song_display = next_song.display()
        self.mp_start(server, next_song)
        await ctx.send('Playing next song!~\n' + box(nxt_song_display))
        await self.check_nextnext_song(server)

    @commands.command()
    async def prev(self, ctx):
        """Plays previous song"""
        server = ctx.guild
        mp = self.get_mp(server)
        pl = self.playlists[server.id]
        self.mp_stop(server)

        prev_i = pl.order.index(pl.cur_i)
        prev_song = pl.list[prev_i]
        self.mp_start(server, prev_song)

    @commands.command()
    async def replay(self, ctx):
        """Restarts current song"""
        server = ctx.guild
        mp = self.get_mp(server)
        pl = self.playlists[server.id]
        self.mp_stop(server)
        self.mp_start(server, pl.list[pl.cur_i])

    @commands.command()
    async def volume(self, ctx, decimal=None):    #keyword decimal to display on help
        """Set/Display volume between 0.0 and 1.0"""
        server = ctx.guild
        voice_client = ctx.guild.voice_client
        mp = voice_client

        if decimal==None:
            await ctx.send("Volume is at " + str(mp.source.volume))
            return

        val = float(decimal)
        if val > 1.0 or val < 0.0:
            await ctx.send("Volume must be between 0 and 1.0!~")
            return

        if not voice_client.is_connected():
            await ctx.send("Voice client not connected yet! Please join a voice channel and play music!~")
            return
        # from v2 bot
        # if not hasattr(voice_client, 'music_player'):
        #     await ctx.send("Please play some music!")
        #     return

        mp.source.volume = val
        self.server_settings[server.id]["VOLUME"] = val
        await ctx.send("Music player volume set to:  " + str(val) + '~')

    @commands.command()
    async def status(self, ctx):
        """Displays music player status"""
        server = ctx.guild
        state = self.states[server.id]
        await ctx.send("Music Player is currently: " + state.value + '~')

    @commands.command()
    async def songinfo(self, ctx):
        """ Displays current playing song info """
        server = ctx.guild
        pl = self.playlists[server.id]
        song = pl.now_playing
        songinfo = song.info()
        await ctx.send(box(songinfo))


    """————————————————————Commands Playlist————————————————————"""
    @commands.command()
    async def add(self, ctx, *, song_or_url):   #*, = positional args as single str
        """ Add a song (local or URL) to the playlist """
        print('[%s]----------MP ADD--------------------' % self.get_timefmt())
        await self.add_song(ctx, song_or_url)

    """Adds a url playlist to the playlist
        -if current playlist is empty, will load it as a new playlist  """
    @commands.command()
    async def add_playlist(self, ctx, url):
        """Adds a url playlist to the playlist """
        print('[%s]----------MP ADD_PLAYLIST--------------------' % self.get_timefmt())
        server = ctx.guild
        pl = self.playlists[server.id]

        is_url = re.compile(r'^(?:http|ftp)s?://' # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
        r'localhost|' #localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
        r'(?::\d+)?' # port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)  # sub-path

        if is_url.match(url):   #download or find in cache
            print('PROCESS INFO ONLY')
            info = await self.downloader.extract(self.bot.loop, url, download=False, process=False) #process=F less info, alot faster
            if info['extractor_key'] in ['YoutubePlaylist', 'SoundcloudSet', 'BandcampAlbum']:
                await ctx.send('Adding a playlist!~')
                url_pl = await self.load_url_pl(server, info, pl)
                for song in url_pl:
                    pl.add(song)
                await ctx.send('Playlist added!~')
        else:
            await ctx.send('Not a URL playlist!~')
            return

    @commands.command()
    #@checks.mod_or_permissions(administrator=True)
    async def remove(self, ctx, name_or_index):     #removes a song from playlist
        """Removes song from playlist by index/searching song name"""
        print('[%s]----------MP REMOVE--------------------' % self.get_timefmt())
        server = ctx.guild
        pl = self.playlists[server.id]
        mp = self.get_mp(server)

        result, song = pl.remove(name_or_index)
        if result == 4:
            await ctx.send("Couldn't find song in playlist!~")
        elif result == 3:
            await ctx.send("Playlist index not in range!~")
        elif result == 2:
            await ctx.send("Playlist now empty!")
            mp.stop()
        elif result == 1:
            await ctx.send("Removed currently playing song! Playing next song~")
            mp.stop()
            mp.start(server, pl.cur_i)
        else:
            song_display = song.display()
            await ctx.send("Removed from playlist!~\n" + box(song_display))

    @commands.command()
    async def search(self, ctx, *, searchterm):
        """Searches a song on youtube and gets top result """
        print('[%s]----------MP SEARCH--------------------' % self.get_timefmt())

        server = ctx.guild
        channel = ctx.channel
        pl = self.playlists[server.id]

        info = await self.downloader.extract(self.bot.loop, searchterm, download=False, process=False)
        if info.get('url', '').startswith('ytsearch'):  # ytdl options allow us to use search strings as input urls
            info = await self.downloader.extract(self.bot.loop, searchterm, download=False,process=True)
            if not all(info.get('entries', [])):
                await ctx.send('Couldnt find a song!~')
                return
            url = info['entries'][0]['webpage_url']    # TODO: handle 'webpage_url' being 'ytsearch:...' or extractor type
            await self.add_song(ctx, url)
        else:
            await ctx.send('Couldn\'t search!~')    # *, = positional args as single str

    @commands.command()
    async def skipto(self, ctx, name_or_index):
        """Skip playlist to index/song name"""
        print('[%s]----------MP SKIPTO--------------------' % self.get_timefmt())
        server = ctx.guild
        pl = self.playlists[server.id]
        mp = self.get_mp(server)

        if name_or_index.isnumeric():
            i = int(name_or_index) - 1
            if (i + 1) > len(pl.list):
                await ctx.send('Index out of range!~')
                return
        else:
            searchterm = name_or_index
            song = pl.search_song(searchterm)
            if song is None:
                await ctx.send("Song not found!~")
                return
            i = pl.get_i(song)

        song = pl.list[i]
        self.mp_stop(server)
        self.mp_start(server, song)
        song_display = str(i+1) + ". " + song.display()
        await ctx.send('Jumping to song: ' + box(song_display))

    @checks.admin()
    @commands.command()
    async def clear(self, ctx):
        """Clears current playlist"""
        server = ctx.guild
        mp = self.get_mp(server)
        pl = self.playlists[server.id]
        self.mp_stop(server)
        pl.clear()
        await ctx.send("Cleared playlist!~")

    @commands.command()
    async def view(self, ctx):              #View current playlist
        """Views current playlist"""
        print('[%s]----------MP VIEW--------------------' % self.get_timefmt())
        server = ctx.guild
        pl = self.playlists[server.id]

        if len(pl.list) == 0:
            await ctx.send("Empty Playlist!~")
            return
        else:
            cur_song, playlist, settings = pl.view()
            settings = 'State: ' + self.states[server.id].value + '\t' + settings
            await ctx.send( "Settings~\n" + box(settings) + '\n' +
                                "Current Song~\n" + box(cur_song) + '\n' +
                                "Current Playlist:\t%s\n" % italics(pl.title),
                                delete_after=60)
            for pl_section in playlist:
                await ctx.send(box(pl_section))

    @commands.command()
    async def view_playlists(self, ctx, local=None):
        """Views cached or local playlists """
        server = ctx.guild
        server_pl_path = playlist_path + '\\' + server.id
        pl_cached = ''
        pl_local = ''
        pattern = r'\.(xml|wpl)$'

        if local is None:
            for root, dirs, files in os.walk(server_pl_path):
                for name in files:
                    pl_cached += re.split(pattern, name)[0] + '\n'
            await ctx.send('Cached playlists:\n' + box(pl_cached))
        elif local == 'local':
            for root, dirs, files in os.walk(playlist_local_path):
                for name in files:
                    pl_local += re.split(pattern, name)[0] + '\n'
            await ctx.send('Local playlists:\n' + box(pl_local))
        else:
            await ctx.send('Use "local" parameter to view local playlists!~')

    @commands.command()
    async def repeat(self, ctx, repeat_state=None):
        """Set/display repeat"""
        server = ctx.guild
        pl = self.playlists[server.id]
        repeat_display = None;
        if not (repeat_state in {'on', 'off', '0', '1', 'one', None}):
            await ctx.send('Parameter must be "on" or "off"!~')
            return
        elif repeat_state == 'on' or repeat_state == '1':
            pl.repeat = True
            repeat_display = 'on'
        elif repeat_state == 'off'or repeat_state == '0':
            pl.repeat = False
            repeat_display = 'off'
        elif repeat_state == 'one' :
            pl.repeat = 'one'
            repeat_display = 'repeating current song'
        else: #display repeat status no params in command
            #await ctx.send('Repeat is ' + ('on' if pl.repeat==True else 'off'))
            await ctx.send('Repeat is ' + repeat_display)
            return
        pl.set_repeat()
        await ctx.send("Repeat set to %s!~" % repeat_display)

    @commands.command()
    async def shuffle(self, ctx, onoff=None):
        """Set/Display shuffle"""
        server = ctx.guild
        pl = self.playlists[server.id]
        if not (onoff in {'on', 'off', None}):
            await ctx.send('Parameter must be "on" or "off"!~')
            return
        elif onoff == 'on':
            pl.shuffle = True
        elif onoff == 'off':
            pl.shuffle = False
        else: #display shuffle status
            await ctx.send('Shuffle is ' + ('on' if pl.shuffle==True else 'off'))
            return
        pl.set_shuffle()
        await ctx.send("Shuffle set to %s!~" % onoff)

    @commands.command()
    async def save_playlist(self, ctx, *, playlist_name):       #builds own xml
        """Saves current playlist to cache"""
        print('[%s]----------MP SAVE PLAYLIST--------------------' % self.get_timefmt())
        author = ctx.author
        server = ctx.guild
        pl = self.playlists[server.id]

        pl_saved = pl.save(playlist_name, server, author.name)
        if pl_saved == 1:
            await ctx.send("Already have a playlist with same name! Overwrite? Y/N~")
            reply = await self.bot.wait_for_message(author=author, channel=ctx.message.channel, check=self.check_reply)
            if reply.content in ['yes', 'y', 'Y']:
                pl_saved = pl.save(playlist_name, server, author.name, overwrite=1)
            elif reply.content in ['no', 'n', 'N']:   #reply=0
                await ctx.send('Playlist not saved!~')
                return
        await ctx.send("Saved playlist: %s!~" % playlist_name)

    @commands.command()
    async def load_playlist(self, ctx, pl):
        """Loads the specified playlist"""
        print('[%s]----------MP LOAD PLAYLIST--------------------' % self.get_timefmt())
        server = ctx.guild
        await ctx.send("Loading playlist please wait!~")
        pl_loaded = self.load_pl(server, pl)
        if pl_loaded == None:
            await ctx.send("Can't find playlist to load!~")
            return
        #self.mp_reload(server)
        self.mp_stop(server)
        self.mp_start(server, self.playlists[server.id].list[0])    #autoplay

    @commands.command()
    async def delete_playlist(self, ctx, *, pl_name):        #deletes by playlist filename bar ext
        """Deletes the specified playlist"""
        print('[%s]----------MP DELETE PLAYLIST--------------------' % self.get_timefmt())
        server = ctx.guild
        pl_path = playlist_path + '\\' + server.id

        ftype = 'xml'
        pl_loc = self.get_file(pl_name, pl_path, ftype)
        if pl_loc == None:
            await ctx.send ("Can't find playlist to delete!~")
        else:
            os.remove(pl_loc)
            await ctx.send ("Deleted playlist: %s!~" % pl_name)

    @checks.admin()
    @commands.command()
    async def save_mp(self, ctx):
        """ Save config and playlists for current server """
        print('[%s]----------MP SAVE--------------------' % self.get_timefmt())
        server = ctx.guild
        print('saving music player settings and playlist:', server.id, server.name)
        pl = self.playlists[server.id]
        pl.save(default_playlist, server, overwrite=1)
        self.save_config()


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
    async def psinfo(self, ctx, url):
        """ DEBUG: playlist URL or song info debug"""
        print('[%s]----------PLAYLIST URL INFO--------------------' % self.get_timefmt())
        server = ctx.guild
        info = await self.downloader.extract(self.bot.loop, url, download=False)
        print(info)
        if info != None:
            for key in info:
                # if key == 'formats':
                #     print(key, info[key])
                #     continue
                """
                if key == 'entries':
                    for entry in info['entries']:
                        for key2 in entry:
                            print(key2, entry[key2])
                """
                # print(key, ':', info[key])
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

        print('server settings')
        for key, val in self.server_settings[server.id].items():
            print(' ', key, val)

    """————————————————————Helper Fn's————————————————————"""
    def save_config(self):      #save config for current server
        config_loc_write = open(config_loc, 'w')
        json.dump(self.settings, config_loc_write, indent=4) #in:self.settings, out:config_file
        print('saving music player config for servers')

    def get_timefmt(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
