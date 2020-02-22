import os
import sys
import aiohttp
import asyncio
import inspect
import discord
import traceback
import psutil
import platform
import logging
import time

from io import BytesIO
from utils.watora import _list_cogs, bytes2human, owner_id, get_str, def_v, log
from utils.chat_formatting import pagify, box
from datetime import datetime, timedelta
from discord.ext import commands
from utils.db import SettingsDB


class Owner(commands.Cog):
    """Owner commands, don't unload them."""

    def __init__(self, bot):
        self.bot = bot
        self.temp = None
        self.log_handlers = {}

    async def unload_all_cogs(self):
        cogs = _list_cogs()
        for c in cogs:
            self.bot.unload_extension("cogs." + c)

    @commands.command()
    @commands.is_owner()
    async def debug(self, ctx):
        """
            {command_prefix}debug

        Enable or disable the debug mode.
        """
        if self.bot.debug_mode == ctx.message.guild.id:
            self.bot.debug_mode = ""
            await ctx.send("The debug mode is now disabled on this server.")
        else:
            self.bot.debug_mode = ctx.message.guild.id
            await ctx.send("The debug mode is now enabled on this server.")

    @commands.command()
    @commands.is_owner()
    async def shutdown(self, ctx, force=None):
        """
            {command_prefix}shutdown (force)

        Shut me down.
        """
        await ctx.message.channel.send("See you!")

        await self.unload_all_cogs()

        await self.bot.session.close()

        await self.bot.logout()

        if force:
            os._exit(0)

    @commands.command()
    @commands.is_owner()
    async def load(self, ctx, extension_name: str):
        """
            {command_prefix}load [extension]

        Loads an extension.
        """
        try:
            self.bot.load_extension("cogs." + extension_name.lower())
        except Exception as e:
            return await ctx.send("```py\n{}: {}\n```".format(type(e).__name__, str(e)))
        await ctx.send(":heavy_check_mark: {} loaded !".format(extension_name.lower()))

    @commands.command()
    @commands.is_owner()
    async def unload(self, ctx, extension_name: str):
        """
            {command_prefix}unload [extension]

        Unloads an extension.
        """
        if extension_name.lower() not in _list_cogs():
            return await ctx.send("This cog is not loaded.")
        if extension_name.lower() == self.__class__.__name__.lower():
            return await ctx.send("This cog cannot be unloaded.")
        self.bot.unload_extension("cogs." + extension_name.lower())
        await ctx.send(":heavy_check_mark: {} unloaded !".format(extension_name.lower()))

    @commands.command()
    @commands.is_owner()
    async def reload(self, ctx, extension_name: str):
        """
            {command_prefix}reload [extension]

        Reloads an extension.
        """
        loaded = [c.__module__.split(".")[1] for c in self.bot.cogs.values()]
        unloaded = [c for c in _list_cogs()
                    if c not in loaded]
        if extension_name.lower() not in _list_cogs():
            return await ctx.send("This cog does not exist.")
        if extension_name.lower() not in unloaded:
            self.bot.unload_extension("cogs." + extension_name)
        try:
            self.bot.load_extension("cogs." + extension_name)
        except Exception as e:
            return await ctx.send(":x: {} have not been reloaded...```py\n{}: {}\n```".format(extension_name, type(e).__name__, str(e)))
        return await ctx.send(":heavy_check_mark: {} reloaded !".format(extension_name))

    @commands.command()
    @commands.is_owner()
    async def reloadall(self, ctx):
        """
            {command_prefix}reloadall

        Reloads every extensions.
        """
        msg = ""
        loaded = [c.__module__.split(".")[1] for c in self.bot.cogs.values()]
        unloaded = [c for c in _list_cogs()
                    if c not in loaded]
        cogs = _list_cogs()
        for c in cogs:
            if c not in unloaded:
                self.bot.unload_extension("cogs." + c)
            try:
                self.bot.load_extension("cogs." + c)
            except Exception as e:
                msg += (":x: **{}** have not been loaded... ``{}: {}``\n".format(c,
                                                                                 type(e).__name__, e))
                continue
            msg += (":heavy_check_mark: **{}** has been reloaded !\n".format(c))
        return await ctx.send(msg)

    @commands.command()
    @commands.is_owner()
    async def unloadall(self, ctx):
        """
            {command_prefix}unloadall

        Unloads every extensions.
        """
        msg = ""
        cogs = _list_cogs()

        for c in cogs:
            self.bot.unload_extension("cogs." + c)
            msg += (":heavy_check_mark: **{}** has been unloaded !\n".format(c))
        return await ctx.send(msg)

    @commands.command()
    @commands.is_owner()
    async def eval(self, ctx, *, stmt):
        """
            {command_prefix}eval [smt]

        Evals something.
        """
        try:
            result = eval(stmt)
            if inspect.isawaitable(result):
                result = await result
        except Exception:
            exc = traceback.format_exc().splitlines()
            result = exc[-1]
        self.temp = result
        return await ctx.channel.send("```py\n--- In ---\n{}\n--- Out ---\n{}\n```".format(stmt, result))

    @commands.is_owner()
    @commands.command(aliases=['space', 'du', 'df'])
    async def disk(self, ctx):
        """
            {command_prefix}disk

        Displays the remaining space.
        """
        embed = discord.Embed()
        if not ctx.guild:
            embed.color = 0x71368a
        else:
            embed.color = ctx.me.color
        embed.add_field(
            name="Disk", value=f"{bytes2human(psutil.disk_usage('/').used)}/{bytes2human(psutil.disk_usage('/').total)} ({psutil.disk_usage('/').percent}%)", inline=False)
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            return await ctx.send(get_str(ctx, "need-embed-permission"), delete_after=20)

    @commands.is_owner()
    @commands.command(aliases=['processor'])
    async def cpu(self, ctx):
        """
            {command_prefix}disk

        Displays my cpu usage.
        """
        embed = discord.Embed()
        if not ctx.guild:
            embed.color = 0x71368a
        else:
            embed.color = ctx.me.color
        embed.add_field(name="CPU", value=str(
            f"{psutil.cpu_percent()}%"), inline=False)
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            return await ctx.send(get_str(ctx, "need-embed-permission"), delete_after=20)

    @commands.is_owner()
    @commands.command(aliases=['ram'])
    async def memory(self, ctx):
        """
            {command_prefix}memory

        Displays the remaining memory.
        """
        embed = discord.Embed()
        if not ctx.guild:
            embed.color = 0x71368a
        else:
            embed.color = ctx.me.color
        embed.add_field(
            name="Memory", value=f"{bytes2human(psutil.virtual_memory().used)}/{bytes2human(psutil.virtual_memory().total)} ({psutil.virtual_memory().percent}%)", inline=False)
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            return await ctx.send(get_str(ctx, "need-embed-permission"), delete_after=20)

    @commands.is_owner()
    @commands.command(aliases=['debian'])
    async def linux(self, ctx):
        """
            {command_prefix}linux

        Displays some cool informations.
        """
        embed = discord.Embed()
        embed.set_author(name=self.bot.user.name,
                         icon_url=self.bot.user.avatar_url)
        if not ctx.guild:
            embed.color = 0x71368a
        else:
            embed.color = ctx.me.color
        embed.add_field(name="Platform", value=str(
            platform.platform()), inline=False)
        embed.add_field(name="CPU", value=str(
            f"{psutil.cpu_percent()}%"), inline=False)
        embed.add_field(
            name="Memory", value=f"{bytes2human(psutil.virtual_memory().used)}/{bytes2human(psutil.virtual_memory().total)} ({psutil.virtual_memory().percent}%)", inline=False)
        embed.add_field(
            name="Swap", value=f"{bytes2human(psutil.swap_memory().used)}/{bytes2human(psutil.swap_memory().total)} ({psutil.swap_memory().percent}%)", inline=False)
        embed.add_field(
            name="Disk", value=f"{bytes2human(psutil.disk_usage('/').used)}/{bytes2human(psutil.disk_usage('/').total)} ({psutil.disk_usage('/').percent}%)", inline=False)
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            return await ctx.send(get_str(ctx, "need-embed-permission"), delete_after=20)

    @commands.command(aliases=['node'])
    @commands.is_owner()
    async def nodes(self, ctx):
        """
            {command_prefix}nodes

        Displays information about my nodes.
        """
        embed = discord.Embed(description="")
        for n in self.bot.lavalink.node_manager.nodes:
            if n.available:
                region = n.region
                if n.stats:
                    cpu = round(n.stats.system_load * 100, 2)
                    cpull = round(n.stats.lavalink_load * 100, 2)
                    node_uptime = str(
                        timedelta(milliseconds=n.stats.uptime)).split(".")[0]
                    core = n.stats.cpu_cores
                    llp = n.stats.players
                    llpp = n.stats.playing_players
                else:
                    cpu = cpull = node_uptime = 'No data'
                    core = llp = llpp = 0
                player = llp or len(n.players)
                playing = llpp or len([x for x in n.players if x.is_playing])
                description = (f"```fix\nNode {n.name}```\n*Region: {region}*\n*Uptime: {node_uptime}*\n\n**Cpu :**\nCore{'s' if core > 1 else ''} : {core}\n"
                               f"System Load : {cpu}% (lavalink {cpull}%)\n\n"
                               f"**Shard Players :**\nCreated: {player}\nPlaying : {playing}\n\n")
            else:
                description = (
                    f"```fix\nNode {n.name}```\n*{n.region}*\n\n**NOT AVAILABLE!**")
            embed.description += description

        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            return await ctx.send(get_str(ctx, "need-embed-permission"), delete_after=20)

    @commands.command(aliases=["gérant", "géran", "proprietaire", "botowner"])
    @commands.cooldown(rate=1, per=1.0, type=commands.BucketType.user)
    async def owner(self, ctx):
        """
            {command_prefix}owner

        Displays who is my owner.
        """
        owner = await self.bot.safe_fetch('user', owner_id) or str(owner_id)
        await ctx.send(f"My owner is `{owner}`.")

    @commands.command(name="cogs")
    @commands.is_owner()
    async def _show_cogs(self, ctx):
        """
            {command_prefix}cogs

        Shows loaded/unloaded cogs.
        """
        loaded = [c.__module__.split(".")[1] for c in self.bot.cogs.values()]
        unloaded = [c for c in _list_cogs()
                    if c not in loaded]

        if not unloaded:
            unloaded = ["None"]

        msg = ("+ Loaded\n"
               "{}\n\n"
               "- Unloaded\n"
               "{}"
               "".format(", ".join(sorted(loaded)),
                         ", ".join(sorted(unloaded)))
               )
        for page in pagify(msg, [" "], shorten_by=16):
            await ctx.send(box(page.lstrip(" "), lang="diff"))

    @commands.is_owner()
    @commands.command()
    async def active(self, ctx):
        """
            {command_prefix}active

        {help}
        """
        players = self.bot.lavalink.players
        embed = discord.Embed()

        connected = len(players.find_all(lambda p: p.is_connected))
        paused = len(players.find_all(lambda p: p.paused))
        playing = len(players.find_all(
            lambda p: p.is_playing and not p.paused))
        voice = len([g for g in self.bot.guilds if g.me and g.me.voice])
        volume = len(self.bot.lavalink.players.find_all(
            lambda p: p.volume != def_v))
        defeq = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        equalizer = len(self.bot.lavalink.players.find_all(
            lambda p: any(p.equalizer)))

        embed.add_field(name="Players", value=len(players), inline=False)
        embed.add_field(name="Custom Volume", value=volume, inline=False)
        embed.add_field(name="Custom Equalizer", value=equalizer, inline=False)
        embed.add_field(name="Voice", value=voice, inline=False)
        embed.add_field(name="Connected", value=connected, inline=False)
        embed.add_field(name="Playing", value=playing, inline=False)
        embed.add_field(name="Paused", value=paused, inline=False)
        embed.add_field(name="Stopped", value=connected -
                        playing - paused, inline=False)

        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"), delete_after=20)

    @commands.is_owner()
    @commands.command(aliases=["activesend", "notifplayers"])
    async def sendactive(self, ctx, *, texts):
        """
            {command_prefix}sendactive [text]

        Sends a text to all my current voice users.
        @users will notify every members in the voice channel.
        """
        playing = self.bot.lavalink.players.find_all(lambda p: p.is_playing)

        for p in playing:
            channel = self.bot.get_channel(p.channel)
            if channel:
                log.info(
                    f"Send to {channel.guild} members in voice : {[g.name for g in p.connected_channel.members]}")
                try:
                    if "@users" in texts:
                        msg = texts.replace("@users", ' '.join(
                            [m.mention for m in p.connected_channel.members if not m.bot]))
                        await channel.send(msg)
                    elif "@user" in texts:
                        msg = texts.replace("@user", ' '.join(
                            [m.mention for m in p.connected_channel.members if not m.bot]))
                        await channel.send(msg)
                    else:
                        await channel.send(texts)
                except discord.Forbidden:
                    pass
                except discord.HTTPException:
                    pass

    @commands.is_owner()
    @commands.command(aliases=['cp'])
    async def cleanupplayers(self, ctx, confirm: str = None):
        """
            {command_prefix}cp

        Cleans player if there is no voice connected to the guild.
        """
        to_remove = []
        for p in self.bot.lavalink.players.players:
            guild = self.bot.get_guild(p)
            if not guild or not guild.me.voice:
                to_remove.append(p)

        if not confirm:
            return await ctx.send(str(to_remove)[:1800])

        for id in to_remove:
            self.bot.lavalink.players.remove(id)

    @commands.command()
    @commands.is_owner()
    async def goodserv(self, ctx):
        """find a good serv"""
        serv_fr = [g for g in self.bot.guilds if g.id in self.bot.languages_map and self.bot.languages_map[g.id]
                   == "french" and len(g.members) > 50]
        serv_fr.sort(key=lambda x: len(x.members), reverse=True)
        msg = [
            f"{g.name} - **{g.id}** ({len(g.members)} members)\n" for g in serv_fr]
        to_send = ""
        for line in msg:
            if len(to_send) + len(line) > 1980:  # TODO find a better way to do this
                await ctx.send(to_send)          # This is ugly
                to_send = ""
            to_send += line

        if to_send:
            await ctx.send(to_send)

    @commands.command(aliases=['changeavatar'])
    @commands.is_owner()
    async def changepic(self, ctx, *, url: str):
        async with aiohttp.request("get", url) as res:
            await self.bot.user.edit(avatar=BytesIO(await res.read()))

    @commands.command(aliases=['csi', 'csid'])
    @commands.is_owner()
    async def calcshardid(self, ctx, guild_id: int):
        result = await self.bot.safe_fetch('guild', guild_id)
        if result:
            await ctx.send(f'`{result.name} ({result.id})` shard id: `{result.shard_id}`')
        else:
            await ctx.send('Guild not found')

    @commands.command(aliases=['log'])
    @commands.is_owner()
    async def logger(self, ctx, *, name_logger=None):

        if not name_logger:
            for name in ['launcher', 'discord', 'lavalink', 'listenmoe']:
                logger = logging.getLogger(name)
                logger.disabled = not logger.disabled

            await ctx.send("Loggers are now " + ['enabled', 'disabled'][logger.disabled])
        else:
            if name_logger.lower() in ['true', 'false']:
                for name in ['launcher', 'discord', 'lavalink', 'listenmoe']:
                    logger = logging.getLogger(name)
                    logger.disabled = (name_logger.lower() == 'true')
                await ctx.send("Loggers are now " + ['enabled', 'disabled'][logger.disabled])
            else:
                logger = logging.getLogger(name_logger)
                logger.disabled = not logger.disabled
                await ctx.send("{} logger is now ".format(name_logger[0].upper() + name_logger[1:]) + ['enabled', 'disabled'][logger.disabled])


def setup(bot):
    bot.add_cog(Owner(bot))
