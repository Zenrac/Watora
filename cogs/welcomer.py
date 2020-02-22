import discord
import asyncio
import random
import re

from datetime import date
from discord.ext import commands
from utils.watora import get_image_from_url, format_mentions, get_str
from utils.db import SettingsDB


class Welcomer(commands.Cog):
    """Cog for welcoming and goodbyeing users."""

    def __init__(self, bot):
        self.bot = bot

    async def welcomer(self, member, settings, goodbye=False):
        await self.bot.wait_until_ready()
        channels = [channel for channel in member.guild.channels if isinstance(
            channel, discord.TextChannel)]
        if goodbye:
            dict = settings.goodbyes
        else:
            dict = settings.welcomes
        for channel in channels:
            if str(channel.id) in dict:
                text = dict[str(channel.id)]
                if "|" in text:
                    choices = [o for o in text.split("|") if o.strip()]
                    if choices:
                        text = random.choice(choices)
                        text = text.lstrip()
                text = text.replace('@mention', '<@%s>' % member.id)
                text = text.replace('@serv', member.guild.name)
                if 'discord.gg' in member.name.lower():
                    text = text.replace('@name', '[Removed Invite]')
                text = text.replace('@name', member.name)
                text = text.replace('@id', str(member.id))
                text = text.replace('@number', str(len(member.guild.members)))
                text = await self.format_cc(member, channel, text)
                pic = get_image_from_url(text)
                if pic:
                    e = discord.Embed()
                    e.set_image(url=pic)
                    text = text.replace(pic, '')
                    try:
                        await channel.send(embed=e, content=text)
                    except discord.Forbidden:
                        try:
                            if goodbye:
                                await channel.send(get_str("need-embed-permission-for-goodbye", bot=self.bot))
                            else:
                                await channel.send(get_str("need-embed-permission-for-welcome", bot=self.bot))
                        except discord.Forbidden:
                            pass
                else:
                    try:
                        await channel.send(text)
                    except discord.Forbidden:
                        pass

    async def format_cc(self, member, channel, command):
        results = re.findall("\{([^}]+)\}", command)  # noqa: W605
        for result in results:
            param = await self.bot.transform_parameter(result=result, message=channel, member=member)
            if 'discord.gg' in param.lower():
                param = '[Removed Invite]'
            command = command.replace("{" + result + "}", param)
        command = format_mentions(command)
        if len(command) > 2000:
            command = command[:1990] + "..."
        if len(command) == 0:
            command = "..."
        return command

    async def auto_role_new_users(self, member, settings):
        if not settings.autoroles:
            return
        if settings.autoroles:
            for role_id in settings.autoroles:
                role = member.guild.get_role(int(role_id))
                if role:
                    try:
                        await member.add_roles(role)
                    except discord.HTTPException:
                        pass
                await asyncio.sleep(0.5)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        settings = await SettingsDB.get_instance().get_guild_settings(member.guild.id)
        await self.welcomer(member, settings, False)
        await self.auto_role_new_users(member, settings)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        settings = await SettingsDB.get_instance().get_guild_settings(member.guild.id)
        await self.welcomer(member, settings, True)


def setup(bot):
    bot.add_cog(Welcomer(bot))
