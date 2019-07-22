

setup for cogs
—————————————————————————————————————————————————————————————————————————————
venv
————————————————————————————————————
py -3.7 -m venv D:\Documents\Code\python\venv
//activate venv
D:\Documents\Code\python\venv\Scripts\activate.bat


prod install
————————————————————————————————————
py -3.7 -m pip install -U Red-DiscordBot
redbot-setup
redbot [bot_name]
redbot-launcher


dev install
————————————————————————————————————
py -3.7 -m pip install -U git+https://github.com/Cog-Creators/Red-DiscordBot@V3/develop#egg=redbot[test]
redbot-setup
redbot [bot_name] --dev


setup/settings
————————————————————————————————————
use official RedBot package seperately from my cog repo
//mycogs location
!installpath D:\Documents\Code\python\Greedie_Bot-V3\cogs






v3 docs
————————————————————————————————————————————————————————————————————————————————————————————————————
https://discordpy.readthedocs.io/en/v1.2.3/index.html
https://github.com/Rapptz/discord.py/tree/master
https://red-discordbot.readthedocs.io/en/v3-develop/index.html


music player
————————————————————————————————————————————————————————————————————————————————————————————————————
https://github.com/rcbyron/hey-athena-client
https://ffmpeg.org/ffmpeg.html
https://github.com/rg3/youtube-dl/blob/master/README.md#readme



wallpaper
————————————————————————————————————————————————————————————————————————————————————————————————————
https://apscheduler.readthedocs.io/en/v3.6.0/faq.html
https://stackoverflow.com/questions/51530012/how-can-i-run-an-async-function-using-the-schedule-library
https://stackoverflow.com/questions/11523918/python-start-a-function-at-given-time

https://docs.python.org/3.6/library/sqlite3.html
https://www.pythoncentral.io/introduction-to-sqlite-in-python/
http://www.sqlitetutorial.net/sqlite-inner-join/

to init
create the Posted table from the commands in the unittest.txt file

uses two databases to track images
	one created by WallpaperMaster that is read from and images are pulled from
	one that is created by the bot to write which images have already been posted to
to remove posted images in a cat go to the write DB and manually remove

add_post [channel id] [postname] [content]

once in server
do
set_wpchannel [channel_id]
add_cats	[cats]
set_time optional

chatterbot
————————————————————————————————————————————————————————————————————————————————————————————————————
https://github.com/gunthercox/ChatterBot
https://chatterbot.readthedocs.io/en/stable/utils.html



changes from v2
————————————————————————————————————————————————————————————————————————————————————————————————————
ctx.message.server
ctx.guild

ctx.message.channel
ctx.channel

ctx.message.author
ctx.author

author.voice_channel
author.voice.channel

FFMPEG_FILES
FFMPEG_BUILDS_URL

@commands.command(pass_context=True)
@commands.command(

no need for import asyncio anymore


class Class(commands.Cog):
self.session = aiohttp.ClientSession() on class init
def cog_unload(self):
    self.session.detach()

server.id, channel.id changed to int
guild = server
@commands.command doesnrt require pass context
new decorators
all sends -> send

self.bot.say
ctx.send
channel.send

https://discordpy.readthedocs.io/en/v1.2.3/migrating.html#voice-changes
self.bot.join_voice_channel
channel.connect

ctx.voice_client shorthand for ctx.guild.voice_client

if self.bot.is_voice_connected(server):
if ctx.guild.voice_client is not None:
if voice_client.is_connected():

self.bot.voice_client_in(server)
ctx.guild.voice_client

channel.voice_members
channel.members

create_ffmpeg_player -> FFmpegPCMAudio

not more mp.is_done and is_paused() added

voice_client.music_player.volume
media_player.source = discord.PCMVolumeTransformer(media_player.source)
media_player.source.volume = self.server_settings[server.id]["VOLUME"]

https://stackoverflow.com/questions/56718658/how-to-check-if-bot-is-connected-to-a-channel-discord-py