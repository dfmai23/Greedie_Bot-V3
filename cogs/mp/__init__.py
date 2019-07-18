from .mp import Music_Player
from .music_player import startup

import traceback
import time

async def setup(bot):
    tm = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print('[%s]----------MP Startup--------------------' % tm)
    codec = startup.check_codec()
    startup.check_ytdl()
    startup.check_cfg()

    music_player = Music_Player(bot, codec=codec)

    try:
        await music_player.init()
        bot.add_cog(music_player)
    except Exception as e:
        traceback.print_exc()
        print("[%s] Exception: %s" % (music_player.get_timefmt(), (str(e))))
