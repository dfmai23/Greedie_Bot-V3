from .chat import Chat

import traceback


async def setup(bot):
    chat_bot = Chat(bot)

    try:
        await chat_bot.init()
        bot.add_cog(chat_bot)
    except Exception as e:
        traceback.print_exc()
        print("[%s] Exception: %s" % (chat_bot.get_timefmt(), (str(e))))
