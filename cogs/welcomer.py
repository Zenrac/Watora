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
        
    @commands.group(aliases=["welcomeauto", "welcomemessage", "welcomemsg"])
    @commands.guild_only()
    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.user)
    @checks.has_permissions(manage_guild=True)
    async def welcome(self, ctx, *, args=None):
        """
            {command_prefix}welcome [text]
            {command_prefix}welcome [random_msg1] | [random_msg2] | ...
            {command_prefix}welcome off

        {help}
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)

        if settings.welcomes:
            if str(ctx.channel.id) in settings.welcomes and not args:
                return await ctx.send(get_str(ctx, "cmd-welcome-current") + " :\n\n{}".format(settings.welcomes[str(ctx.channel.id)]))
            elif not args:
                return await ctx.send(get_str(ctx, "cmd-welcome-no-welcome-now").format("`{}welcome [text]`".format(get_server_prefixes(ctx.bot, ctx.guild))))
        else:
            if not args:
                return await ctx.send(get_str(ctx, "cmd-welcome-no-welcome-now").format("`{}welcome [text]`".format(get_server_prefixes(ctx.bot, ctx.guild))))

        if args.lower() in ["now", "current", "view", "display"]:
            await ctx.invoke(self.bot.get_command("welcome"))

        elif args.lower() in ["stop", "off", "empty", "nothing", "end", "disable", "remove", "reset", " "]:
            await ctx.invoke(self.bot.get_command("welcome off"))

        else:
            settings.welcomes[str(ctx.channel.id)] = args
            await SettingsDB.get_instance().set_guild_settings(settings)
            await ctx.send(get_str(ctx, "cmd-welcome-enabled") + f" :\n\n{args}")

    @welcome.command(aliases=["stop", "off", "empty", "nothing", "end", "disable", "remove", " "])
    async def welcome_off(self, ctx):
        """
            {command_prefix}welcome off

        {help}
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)

        if settings.welcomes and str(ctx.channel.id) in settings.welcomes:
            settings.welcomes.pop(str(ctx.channel.id), None)
            await ctx.send(get_str(ctx, "cmd-welcome-off-success"))
            await SettingsDB.get_instance().set_guild_settings(settings)
        else:
            await ctx.send(get_str(ctx, "cmd-welcome-off-already"))

    @commands.group(aliases=["goodbyeauto", "goodbyemessage", "goodbyemsg", "bbmsg", "byebye"])
    @commands.guild_only()
    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.user)
    @checks.has_permissions(manage_guild=True)
    async def goodbye(self, ctx, *, args=None):
        """
            {command_prefix}goodbye [text]
            {command_prefix}goodbye [random_msg1] | [random_msg2] | ...
            {command_prefix}goodbye off

        {help}
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)

        if settings.goodbyes:
            if str(ctx.channel.id) in settings.goodbyes and not args:
                return await ctx.send(get_str(ctx, "cmd-goodbye-current") + " :\n\n{}".format(settings.goodbyes[str(ctx.channel.id)]))
            elif not args:
                return await ctx.send(get_str(ctx, "cmd-goodbye-no-goodbye-now").format("`{}goodbye [text]`".format(get_server_prefixes(ctx.bot, ctx.guild))))
        else:
            if not args:
                return await ctx.send(get_str(ctx, "cmd-goodbye-no-goodbye-now").format("`{}goodbye [text]`".format(get_server_prefixes(ctx.bot, ctx.guild))))

        if args.lower() in ["now", "current", "view", "display"]:
            await ctx.invoke(self.bot.get_command("goodbye"))

        elif args.lower() in ["stop", "off", "empty", "nothing", "end", "disable", "remove", "reset", " "]:
            await ctx.invoke(self.bot.get_command("goodbye off"))

        else:
            settings.goodbyes[str(ctx.channel.id)] = args
            await SettingsDB.get_instance().set_guild_settings(settings)
            await ctx.send(get_str(ctx, "cmd-goodbye-enabled") + f" :\n\n{args}")

    @goodbye.command(aliases=["stop", "off", "empty", "nothing", "end", "disable", "remove", " "])
    async def goodbye_off(self, ctx):
        """
            {command_prefix}goodbye off

        {help}
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)

        if settings.goodbyes and str(ctx.channel.id) in settings.goodbyes:
            settings.goodbyes.pop(str(ctx.channel.id), None)
            await ctx.send(get_str(ctx, "cmd-goodbye-off-success"))
            await SettingsDB.get_instance().set_guild_settings(settings)
        else:
            await ctx.send(get_str(ctx, "cmd-goodbye-off-already"))


def setup(bot):
    bot.add_cog(Welcomer(bot))
