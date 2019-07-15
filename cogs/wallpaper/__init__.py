from .wallpaper import Wallpaper

import traceback

async def setup(bot):
    wp = Wallpaper(bot)

    try:
        await wp.init()
        bot.add_cog(wp)
    except Exception as e:
        traceback.print_exc()
        print("[%s] Exception: %s" % (wp.get_timefmt(), (str(e))))
