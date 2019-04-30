import discord
import asyncio
import aiohttp
import json

from utils.db import SettingsDB
from time import time
from discord.ext import commands
from utils.watora import globprefix, log

CARBONITEX_API_BOTDATA = 'https://www.carbonitex.net/discord/data/botdata.php'
DISCORD_BOTS_API = 'https://bots.discord.pw/api'
DISCORD_BOTSORG_API = 'https://discordbots.org/api'
BOTSFORDISCORD_API = 'https://botsfordiscord.com/api'
BOTLISTSPACE_API = 'https://botlist.space/api/'
DISCORD_BOTSGROUP_API = 'https://discordbots.group/api'
DIVINEDISCORDBOTS_API = 'https://divinediscordbots.com/'
DISCORDBOAT_API = "https://discord.boats/api"
DISCORDBOTWORLD_API = 'https://discordbot.world/api'
DISCORDBESTBOTS_API = 'https://discordsbestbots.xyz/api'


class Update(commands.Cog):
    """Cog for updating carbonitex.net, bots.discord.pw etc... and change bot status"""
    def __init__(self, bot):
        self.ready = False
        self.bot = bot
        self.timer = time()
        self.votes = []
        timeout = aiohttp.ClientTimeout(total=20)
        self.session = aiohttp.ClientSession(loop=self.bot.loop, timeout=timeout)

    def cog_unload(self):
        asyncio.ensure_future(self.session.close())

    async def update(self, bypass=False):
        await self.bot.wait_until_ready()

        if ((time() - self.timer) < 120) and not bypass:  # max 1 per 120 sec
            return

        self.timer = time()

        guild_count = len(self.bot.guilds)

        if self.bot.user.bot:
            if (guild_count % 3) == 0:
                title = "%shelp | patreon.com/watora" % globprefix
            elif (guild_count % 5) == 0:
                title = "%shelp | %s guilds" % (globprefix, guild_count)
            else:
                settings = await SettingsDB.get_instance().get_glob_settings()
                if 'bar' in settings.donation:
                    pbar = settings.donation['bar']
                    if "," in pbar:
                        pbar = pbar.replace(",", ".")
                    pbar = pbar.split("/")
                    max_value = float(pbar[1])
                    min_value = float(pbar[0])
                    if max_value <= min_value:
                        title = "%shelp | %s guilds" % (globprefix, guild_count)
                    else:
                        title = f"%sdon | Servers cost: {min_value}€/{max_value}€" % (globprefix)
                else:
                    title = "%shelp | %s guilds" % (globprefix, guild_count)

            streamer = "https://www.twitch.tv/monstercat"
            # game = discord.Activity(type=discord.ActivityType.watching, url=streamer, name=title)
            game = discord.Streaming(url=streamer, name=title)
            await self.bot.change_presence(activity=game, status=None, afk=False)

        # CARBON

        # carbon_payload = {
        #     'key': self.bot.tokens["CARBON_KEY"],
        #     'servercount': guild_count
        # }

        # async with self.session.post(CARBONITEX_API_BOTDATA, data=carbon_payload) as resp:
        #     log.debug(f'Carbon statistics returned {resp.status} for {carbon_payload}')

        payload = json.dumps({
            'server_count': guild_count,
            'count':        guild_count,
            'guilds':       guild_count
        })

        # BOTS.DISCORD
        headers = {
            'authorization': self.bot.tokens["BOTS_KEY"],
            'content-type': 'application/json'
        }

        url = f'{DISCORD_BOTS_API}/bots/{self.bot.user.id}/stats'
        async with self.session.post(url, data=payload, headers=headers) as resp:
            log.debug(f'[Web] DBots statistics returned {resp.status} for {payload}')

        # DISCORD BESTBOTS
        headers = {
            'authorization': self.bot.tokens["DISCORDBESTBOTS_KEY"],
            'content-type': 'application/json'
        }

        url = f'{DISCORDBESTBOTS_API}/bots/{self.bot.user.id}'
        async with self.session.post(url, data=payload, headers=headers) as resp:
            log.debug(f'[Web] DBESTBOTS statistics returned {resp.status} for {payload}')

        # DISCORDBOT.ORG
        headers = {
            'authorization': self.bot.tokens["BOTSORG_KEY"],
            'content-type': 'application/json'
        }

        url = f'{DISCORD_BOTSORG_API}/bots/{self.bot.user.id}/stats'
        async with self.session.post(url, data=payload, headers=headers) as resp:
            log.debug(f'[Web] DBotsOrg statistics returned {resp.status} for {payload}')

        url = f'{DISCORD_BOTSORG_API}/bots/220644154177355777/votes'
        async with self.session.get(url, headers=headers) as resp:
            if resp.status == 200:
                self.votes = await resp.json()

        # BOTLIST.SPACE
        headers = {
            'authorization': self.bot.tokens["BOTSPACE_KEY"],
            'content-type': 'application/json'
        }

        url = f'{BOTLISTSPACE_API}/bots/{self.bot.user.id}/'
        async with self.session.post(url, data=payload, headers=headers) as resp:
            log.debug(f'[Web] BLspace statistics returned {resp.status} for {payload}')


        # DISCORDBOTS.GROUP
        headers = {
            'authorization': self.bot.tokens["DISCORDBOTSGROUP_KEY"],
            'content-type': 'application/json'
        }

        url = f'{DISCORD_BOTSGROUP_API}/bot/{self.bot.user.id}/'
        async with self.session.post(url, data=payload, headers=headers) as resp:
            log.debug(f'[Web] DBgroup statistics returned {resp.status} for {payload}')

        # DIVINEDISCORDBOTS.COM
        headers = {
            'authorization': self.bot.tokens["DIVINEDISCORDBOTS_KEY"],
            'content-type': 'application/json'
        }

        url = f'{DIVINEDISCORDBOTS_API}/bot/{self.bot.user.id}/stats'
        async with self.session.post(url, data=payload, headers=headers) as resp:
            log.debug(f'[Web] divinediscordbots statistics returned {resp.status} for {payload}')

        # DISCORDBOAT.XYZ
        headers = {
            'authorization': self.bot.tokens["DISCORDBOAT_KEY"],
            'content-type': 'application/json'
        }

        url = f'{DISCORDBOAT_API}/bot/{self.bot.user.id}'
        async with self.session.post(url, data=payload, headers=headers) as resp:
            log.debug(f'[Web] discordboat statistics returned {resp.status} for {payload}')

        # BOTSFORDISCORD.COM
        headers = {
            'authorization': self.bot.tokens["BOTSFORDISCORD_KEY"],
            'content-type': 'application/json'
        }

        url = f'{BOTSFORDISCORD_API}/bot/{self.bot.user.id}'
        async with self.session.post(url, data=payload, headers=headers) as resp:
            log.debug(f'[Web] BFdiscord statistics returned {resp.status} for {payload}')

        # DISCORDBOT.WORLD
        headers = {
            'authorization': self.bot.tokens["DISCORDBOTWORLD_KEY"],
            'content-type': 'application/json'
        }

        url = f'{DISCORDBOTWORLD_API}/bot/{self.bot.user.id}/stats'
        async with self.session.post(url, data=payload, headers=headers) as resp:
            log.debug(f'[Web] DISCORDBOT WORLD statistics returned {resp.status} for {payload}')

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        log.info(f"[Guild] Joined : {guild.id}/{guild.name} (owner : {guild.owner})")
        await self.update()

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        log.info(f"[Guild] Removed : {guild.id}/{guild.name} (owner : {guild.owner})")
        await self.update()

    @commands.Cog.listener()
    async def on_ready(self):
        self.ready = True
        await self.update(bypass=True)

def setup(bot):
    bot.add_cog(Update(bot))
