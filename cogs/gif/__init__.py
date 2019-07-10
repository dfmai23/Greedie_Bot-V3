from .gif import GIF

import traceback

async def setup(bot):
    gif = GIF(bot)

    try:
        await gif.init()
        bot.add_cog(gif)
    except Exception as e:
        traceback.print_exc()
        print("[%s] Exception: %s" % (gif.get_timefmt(), (str(e))))
