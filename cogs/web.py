import discord
import asyncio
import aiohttp
import json

from utils.db import SettingsDB
from time import time
from discord.ext import commands
from utils.watora import globprefix, log

DISCORD_BOTS_API = 'https://bots.discord.pw/api/bots/{}/stats'
DISCORD_BOTSORG_API = 'https://discordbots.org/api/bots/{}/stats'
BOTSFORDISCORD_API = 'https://botsfordiscord.com/api/bot/{}'
BOTLISTSPACE_API = 'https://api.botlist.space/v1/bots/{}'
DISCORD_BOTSGROUP_API = 'https://api.discordbots.group/v1/bot/{}'
DIVINEDISCORDBOTS_API = 'https://divinediscordbots.com/bot/{}/stats'
DISCORDBOAT_API = 'https://discord.boats/api/bot/{}'
DISCORDBOTWORLD_API = 'https://discordbot.world/api/bot/{}/stats'
DISCORDBESTBOTS_API = 'https://discordsbestbots.xyz/api/bots/{}/stats'
DISCORDFRENCH_API = 'https://api.wonderbotlist.com/v1/bot/{}'
ARCANEBOTCENTER_API = 'https://arcane-botcenter.xyz/api/{}/stats'

ALL_APIS = {
    # DISCORD_BOTS_API : 'BOTS_KEY',
    DISCORD_BOTSORG_API: 'BOTSORG_KEY',
    BOTSFORDISCORD_API: 'BOTSFORDISCORD_KEY',
    BOTLISTSPACE_API: 'BOTSPACE_KEY',
    DISCORD_BOTSGROUP_API: 'DISCORDBOTSGROUP_KEY',
    DIVINEDISCORDBOTS_API: 'DIVINEDISCORDBOTS_KEY',
    DISCORDBOAT_API: 'DISCORDBOAT_KEY',
    DISCORDBOTWORLD_API: 'DISCORDBOTWORLD_KEY',
    DISCORDBESTBOTS_API: 'DISCORDBESTBOTS_KEY',
    # DISCORDFRENCH_API : 'BOTSFRENCH_KEY',
    # ARCANEBOTCENTER_API : 'ARCANEBOTCENTER_KEY'
}


class Update(commands.Cog):
    """Cog for updating carbonitex.net, bots.discord.pw etc... and change bot status"""

    def __init__(self, bot):
        self.bot = bot
        self.timer = time()
        self.status_timer = time()
        self.votes = []
        timeout = aiohttp.ClientTimeout(total=20)
        self.session = aiohttp.ClientSession(
            loop=self.bot.loop, timeout=timeout)
        asyncio.ensure_future(self.message_status(
            bypass=True))

    def cog_unload(self):
        asyncio.ensure_future(self.session.close())

    async def message_status(self, bypass=False, update=True):
        await self.bot.wait_until_ready()

        if ((time() - self.status_timer) < 10) and not bypass:
            return

        if update:
            await self.update_guild_count()

        self.status_timer = time()

        guild_count = self.bot.guild_count

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
                        title = "%shelp | %s guilds" % (
                            globprefix, guild_count)
                    else:
                        title = f"%sdon | Servers cost: {min_value}€/{max_value}€" % (
                            globprefix)
                else:
                    title = "%shelp | %s guilds" % (globprefix, guild_count)

            streamer = "https://www.twitch.tv/monstercat"
            game = discord.Streaming(url=streamer, name=title)
            await self.bot.change_presence(activity=game, status=None, afk=False)

    async def update(self, bypass=False):

        guild_count = self.bot.guild_count
        shard_count = self.bot.shard_count

        if self.bot.is_main_process and ((time() - self.timer) > 60) or bypass:  # max 1 per 60 sec
            self.timer = time()

            payload = json.dumps({
                'server_count':  guild_count,
                'servers_count': guild_count,
                'count':         guild_count,
                'guilds':        guild_count,
                'guild':         guild_count,
                'serveurs':      guild_count,
                'serveur':       guild_count
            })

            for k, v in ALL_APIS.items():
                try:
                    await self.post_stats(url=k.format(self.bot.user.id), token=v, payload=payload)
                    await asyncio.sleep(0.5)
                except (asyncio.TimeoutError, aiohttp.ClientError):
                    pass

            await self.get_votes()

    async def get_votes(self):
        headers = {
            'authorization': self.bot.tokens["BOTSORG_KEY"],
            'content-type': 'application/json'
        }

        url = f'https://discordbots.org/api/bots/220644154177355777/votes'
        async with self.session.get(url, headers=headers) as resp:
            if resp.status == 200:
                self.votes = await resp.json()
            await resp.release()

    async def post_stats(self, url, token, payload):
        headers = {
            'authorization': self.bot.tokens[token],
            'content-type': 'application/json'
        }
        async with self.session.post(url, data=payload, headers=headers) as resp:
            await resp.release()
            log.debug(f'[Web] {resp.url} returned {resp.status} for {payload}')

    async def update_guild_count(self):
        settings = await SettingsDB.get_instance().get_glob_settings()

        for m in self.bot.shards.keys():
            settings.server_count[str(m)] = len(
                [g for g in self.bot.guilds if g.shard_id == m])

        await SettingsDB.get_instance().set_glob_settings(settings)
        self.bot.config = settings

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        log.debug(
            f"[Guild] Joined : {guild.id}/{guild.name} (owner : {guild.owner})")
        await self.message_status()
        await self.update()

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        log.debug(
            f"[Guild] Removed : {guild.id}/{guild.name} (owner : {guild.owner})")
        await self.message_status()
        await self.update()


def setup(bot):
    bot.add_cog(Update(bot))
