import discord
from redbot.core import commands
import asyncio
import aiohttp
import os
import copy
import re
import time

from chatterbot import ChatBot
from chatterbot.trainers import ChatterBotCorpusTrainer

chatbot = commands.Bot(command_prefix='@Bot')

chat_path = 'data\chat\\'
chat_file = 'chat.txt'  #global chat file for manual messages


class Chat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot  #discord.Client()
        self.session = aiohttp.ClientSession()
        self.chatbot = None
        self.messages = {}

    """————————————————————Initializations————————————————————"""
    async def init(self):
        print('[%s]----------Chat Bot Initialize Cog--------------------' % self.get_timefmt())
        self.bot.loop.create_task(self.init_chatbot())
        self.init_messages()
        self.bot.loop.create_task(self.init_training())
        self.bot.add_listener(self.my_on_message, 'on_message') #when on_message fires so will my_on_message

    def cog_unload(self):
        self.session.detach()

    def init_chat(self):
        print('initializing chat')
        f = open(chat_path + chat_file, 'r')
        messages = {}
        messages_list = []
        messages_list = f.readlines()

        for line in messages_list:
            # print(line)
            line = line.replace('\n', '')
            line = line.split('|')
            messages[line[0].lower()] = line[1]
            # print(line[0] + ' | ' + messages[line[0].lower()])
        f.close()
        return messages

    def init_messages(self):
        print('initializing messages')
        if not os.path.isdir(chat_path):  # root chat dir
            os.mkdir(chat_path)
        global_chat_loc = chat_path + chat_file
        if not os.path.isfile(global_chat_loc):
            f = open(global_chat_loc, 'w')
            f.close()
        global_msgs = self.init_chat()

        for server in self.bot.guilds:  #LEGACY bot.servers = bot.guilds
            server_id = str(server.id)
            self.messages[server_id] = {}
            self.messages[server_id] = copy.deepcopy(global_msgs)  # copy global messages to each server

            server_chat_path = chat_path + server_id + '\\'
            if not os.path.isdir(server_chat_path):
                os.mkdir(server_chat_path)
            server_chat_loc = server_chat_path + chat_file
            if not os.path.isfile(server_chat_loc):
                f = open(server_chat_loc, 'w')
                f.close()

            # print(server_chat_loc)
            f = open(server_chat_loc, 'r')
            svr_msgs = {}
            msgs_list = []
            msgs_list = f.readlines()

            for line in msgs_list:
                line = line.replace('\n', '')
                line = line.split('|')
                self.messages[server_id][line[0].lower()] = line[1]
            f.close()

    async def init_chatbot(self):
        print('init_chatbot')
        # database_fullpath = chat_path + 'chatdb.sqlite3'
        # print('  setting chatbot database as: ' + database_fullpath)
        self.chatbot = ChatBot(
            'Greedie_Bot',
            # storage_adapter='chatterbot.storage.SQLStorageAdapter',  # sql is default
            # database = database_fullpath,
            logic_adapters=["chatterbot.logic.BestMatch"])

    async def init_training(self):
        trained = self.check_trained()
        if not trained:
            print('training')
            trainer = ChatterBotCorpusTrainer(self.chatbot)
            trainer.train('chatterbot.corpus.english')
            print('training done')


    """————————————————————Helper Fn's————————————————————"""
    def check_trained(self):
        trained = False
        chat_train_loc = chat_path + 'trained.txt'
        if not os.path.isfile(chat_train_loc):
            f = open(chat_train_loc, 'w')
            f.write('1')
            trained = False
            print('trained.txt not found creating it and training chatbot')
        else:
            f = open(chat_train_loc, 'r+')
            line = f.readline()
            if line == '1':
                print('trained.txt read: %s, not training chatbot' % line)
                trained = True
            else:
                print('trained.txt read: %s, training chatbot' % line)
                f = open(chat_train_loc, 'w')
                f.write('1')
                trained = False
        f.close()
        return trained

    def get_timefmt(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    """————————————————————Commands————————————————————"""
    async def my_on_message(self, message):
        if self.bot.user.mentioned_in(message):
            reply = self.parse(message)
            try:
                await self.bot.send_message(message.channel, content=reply)
            except discord.HTTPException:
                pass

    @commands.command()
    async def cstat(self, ctx):
        print('[%s]----------Chatbot STAT--------------------' % self.get_timefmt())
        for key in self.messages:
            print('messages for:', key, self.bot.get_guild(int(key)).name)
            for key2 in self.messages[key]:
                print(' ', key2, self.messages[key][key2])

    def parse(self, message):
        print('[%s]----------Chatbot Message--------------------' % self.get_timefmt())
        if '@everyone' in message.content:
            print('contains @everyone, skipping message')
            return

        pattern = re.compile(r'^(<@\d*>|@everyone)')
        content = re.sub(pattern, '', message.content)  # remove the ping @bot from message before parse
        reply = self.chatbot.get_response(content)

        print('message content: ' + message.content)
        print('editted content: ' + content)
        print('REPLY', message.content, '|', reply)
        return reply

    def parse2(self, server, message):  #from txt file
        server_id = str(server.id)
        msg = ''
        msg = message.content   #str
        msg = msg.strip(self.bot.user.mention + ' ')
        msg = msg.lower()
        if msg in self.messages[server_id]:
            return self.messages[server_id][msg]