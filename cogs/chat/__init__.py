from .chat import Chat


async def setup(bot):
    chat_bot = Chat(bot)
    await chat_bot.init()
    bot.add_cog(chat_bot)
