import aiohttp
import asyncio
import listenmoe

# from monstercatFM import monstercat
from utils.watora import log
from discord.ext import commands


class Radio(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tasks = []
        self.session = aiohttp.ClientSession(loop=self.bot.loop)
        asyncio.ensure_future(self.start())

    def cog_unload(self):
        for task in self.tasks:
            task.cancel()
        asyncio.ensure_future(self.session.close())

    async def players_update(self, kpop=False, mc=False):
        if 'Music' in self.bot.cogs:  # auto-np radio songs, sweet.
            music = self.bot.cogs['Music']
            if not mc:
                try:
                    await music.update_all_listen_moe_players(kpop)
                except Exception as e:
                    log.warning(
                        f"[LISTEN.moe] Updating {'K-POP' if kpop else 'J-POP'} players failed with error : {e}")
            else:
                try:
                    await music.update_all_mc_players()
                except Exception as e:
                    log.warning(
                        f"[MonsterCat] Updating players failed with error : {e}")

    async def hand(self, msg):
        before = self.bot.now

        if msg.type == listenmoe.message.SONG_INFO:
            self.bot.now = msg
        else:
            self.bot.now = msg.raw

        if before != self.bot.now:  # avoid the first useless updates when starting the bot / loading the cog
            await self.players_update()

    async def handkpop(self, msg):
        before = self.bot.nowkpop

        if msg.type == listenmoe.message.SONG_INFO:
            self.bot.nowkpop = msg
        else:
            self.bot.nowkpop = msg.raw

        if before != self.bot.nowkpop:  # avoid the first useless updates when starting the bot / loading the cog
            await self.players_update(kpop=True)

    async def mchand(self, msg):
        before = self.bot.mcnow
        self.bot.mcnow = msg

        if msg != before:
            await self.players_update(mc=True)

    async def start(self):
        await self.bot.wait_until_ready()

        kp = listenmoe.client.Client(loop=self.bot.loop, kpop=True)
        kp.register_handler(self.handkpop)
        task = asyncio.ensure_future(kp.start())
        self.tasks.append(task)

        cl = listenmoe.client.Client(loop=self.bot.loop)
        cl.register_handler(self.hand)
        task = asyncio.ensure_future(cl.start())
        self.tasks.append(task)

        # Monstercat disabled since a while..
        # mc = monstercat.Client(loop=self.bot.loop, aiosession=self.session)
        # mc.register_handler(self.mchand)
        # task = asyncio.ensure_future(mc.start())
        # self.tasks.append(task)


def setup(bot):
    bot.add_cog(Radio(bot))
