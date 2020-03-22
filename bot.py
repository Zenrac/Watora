import re
import sys
import random
import discord
import aiohttp
import unidecode
import asyncio
import traceback
import logging

from datetime import date
from textwrap import dedent

from discord.ext import commands

from utils.chat_formatting import shlex_ignore_single_quote
from utils.dataIO import dataIO
from utils.watora import token, globprefix, owner_id, log, get_str, is_patron, is_lover, _list_cogs, get_server_prefixes, is_admin, get_image_from_url, format_mentions, NoVoiceChannel
from utils.db import SettingsDB


def _prefix_callable(bot, msg):
    prefixes = set()
    if not msg.guild:
        prefixes.add(globprefix)
    else:
        prefixes.add(bot.prefixes_map.get(msg.guild.id, globprefix))

    return commands.when_mentioned_or(*prefixes)(bot, msg)


def start_bot(shard_count=None, shard_ids=None, send=None):
    Watora(shard_count=shard_count, shard_ids=shard_ids, send=send).run()


class Watora(commands.AutoShardedBot):

    def __init__(self, shard_count=None, shard_ids=None, send=None):
        title = "%shelp | patreon.com/watora" % globprefix
        streamer = "https://www.twitch.tv/monstercat"
        game = discord.Streaming(url=streamer, name=title)

        super().__init__(
            command_prefix=_prefix_callable,
            case_insensitive=True,
            description='',
            shard_ids=shard_ids,
            shard_count=shard_count,
            activity=game,
            fetch_offline_members=False,
            max_messages=None
        )

        self.pipe = send
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.debug_mode = ""
        self.remove_command('help')
        self.init_ok = False
        self.tokens = dataIO.load_json("config/tokens.json")
        self.config = None
        self.now = None
        self.nowkpop = None
        self.mcnow = None
        self.prefixes_map = {}
        self.languages_map = {}
        self.owo_map = {}
        self.autosongs_map = {}
        self.loaded_languages = {}

        # Spotify Integration
        self.spotify = None

    @property
    def server_count(self):
        return self.guild_count

    @property
    def guild_count(self):
        return sum(self.config.server_count.values())

    @property
    def is_main_process(self):
        return 0 in self.shards

    async def server_is_claimed(self, guild_id, settings=None):
        """Checks if a server is claimed or not"""
        if not settings:
            settings = await SettingsDB.get_instance().get_glob_settings()
        for k, m in settings.claim.items():
            if str(guild_id) in m.keys():
                fetched_member = await is_patron(self, int(k), fetch=True)
                if fetched_member:
                    max_claim = 2
                    if await is_lover(self, int(k), resp=fetched_member):
                        max_claim = 5
                    if int(k) == owner_id:
                        max_claim = 9e40
                    if len(settings.claim[k]) > max_claim:
                        return False
                    return (k, settings.claim[k])
        return False

    def get_role(self, ctx, name):
        name = str(name)
        role = [r for r in ctx.guild.roles if r.name.lower() == name.lower()]
        if not role:
            try:
                role = ctx.guild.get_role(
                    int(name.replace('<@&', '').replace('>', '')))
            except ValueError:
                role = None
        else:
            role = role[0]

        return role

    async def safe_fetch(self, target, id, guild=None):
        if target not in ['member', 'user', 'guild', 'channel']:
            raise Exception(
                f'{target} is not a supported target. Please use either channel, member, user or guild.')

        result = None

        if guild:
            if target in ['member', 'channel', 'user']:
                if target == 'user':
                    target = 'member'
                if isinstance(guild, discord.Guild) or str(guild).isdigit():
                    if str(guild).isdigit():
                        guild = await self.safe_fetch('guild', guild)
                    if guild:
                        result = getattr(guild, f'get_{target}')(id)
                if target == 'member':
                    target = 'user'

        if not result:
            result = getattr(self, f'get_{target}')(id)
            if not result:
                try:
                    coro = getattr(self, f'fetch_{target}')
                    result = await coro(id)
                except discord.HTTPException:
                    pass

        return result

    async def format_cc(self, command, message):
        results = re.findall("\{([^}]+)\}", command)  # noqa: W605
        for result in results:
            param = await self.transform_parameter(result, message)
            command = command.replace("{" + result + "}", param)
        command = format_mentions(command)
        if len(command) > 2000:
            command = command[:1990] + "..."
        if len(command) == 0:
            command = "..."
        return command

    async def transform_parameter(self, result, message, member=None):
        """
        For security reasons only some objects are allowed
        """
        raw_result = "{" + result + "}"

        if isinstance(message, discord.Message):
            objects = {
                "message": message,
                "author":  message.author,
                "member":  message.author,
                "user":    message.author,
                "user":    message.author,
                "channel": message.channel,
                "server":  message.guild,
                "guild":   message.guild,
                "day":     date.today().day,
                "month":   date.today().month,
                "year":    date.today().year
            }

            if message.guild:

                guild_only = {
                    "random_member":  random.choice(message.guild.members),
                    "server_members": len(message.guild.members),
                    "server_member_count": len(message.guild.members)
                }

                objects = {**objects, **guild_only}

                if message.guild.id in self.lavalink.players.players:
                    player = self.lavalink.players.players[message.guild.id]

                    player_only = {
                        "current": player.current,
                    }

                    objects = {**objects, **player_only}

            prefixes = _prefix_callable(self, message)
            for prefix in prefixes:
                if message.content.startswith(prefix):
                    cmd_prefix = prefix  # Get the used prefix
                    break

            str_rest = ' '.join(
                message.content[len(cmd_prefix):].split(" ")[1:])

        else:  # From Welcomer
            objects = {
                "author":         member,
                "member":         member,
                "user":           member,
                "channel":        message,
                "server":         member.guild,
                "guild":          member.guild,
                "day":            date.today().day,
                "month":          date.today().month,
                "year":           date.today().year
            }

            if member.guild:  # Should be always True, but who knows ?

                guild_only = {
                    "random_member":  random.choice(member.guild.members),
                    "server_members": len(member.guild.members),
                    "server_member_count": len(member.guild.members)
                }

                objects = {**objects, **guild_only}

                if member.guild.id in self.lavalink.players.players:
                    player = self.lavalink.players.players[member.guild.id]

                    player_only = {
                        "current": player.current,
                    }

                    objects = {**objects, **player_only}

            str_rest = result

        occ = [r for r in str_rest.split() if r == '"']

        if (len(occ) % 2) == 0:  # Avoid ValueError not closing quote...
            rest = shlex_ignore_single_quote(str_rest)
        else:
            rest = str_rest.split(" ")

        if "//" in result and result.split("//")[0].lstrip("-").isdigit() and len(result.split("//")) > 1:
            if len(rest) < int(result.split("//")[0].replace(":", "")):
                temp = result.split("//")[1].strip()
                temp2 = await self.transform_parameter(temp, message, member)
                if '{' + temp + '}' == temp2:
                    return str(temp)
                return temp2
            else:
                if int(result.split("//")[0].replace(":", "")) == 0:
                    if str_rest.strip() == "":
                        return result.split("//")[1]
                    return str_rest
                result = result.split("//")[0]

        if "~" in result:
            if not result.split('~')[0].lstrip("-").isdigit():
                index = 0
            else:
                index = int(result.split('~')[0])
            if not result.split('~')[1].lstrip("-").isdigit():
                index2 = 100
            else:
                index2 = int(result.split('~')[1])
            if index > index2:
                return str(random.randint(index2, index))
            else:
                return str(random.randint(index, index2))

        if ":" in result:
            if not result.split(':')[0].lstrip("-").isdigit():
                index = None
            elif int(result.split(':')[0]) > 0:
                index = int(result.split(':')[0]) - 1
            else:
                index = int(result.split(':')[0])
            if not result.split(':')[1].lstrip("-").isdigit():
                index2 = None
            elif int(result.split(':')[1]) > 0 and index is None:
                index2 = int(result.split(':')[1]) - 1
            else:
                index2 = int(result.split(':')[1])
            if index is not None or index2 is not None:
                return ' '.join(rest[index:index2])

        if result.lstrip("-").isdigit():
            if len(rest) < int(result):
                return '   '
            else:
                if int(result) == 0:
                    return str_rest
                if int(result) > 0:
                    index = int(result) - 1
                else:
                    index = int(result)
                return rest[index]

        if result == "&":
            return str_rest.replace('"', '')

        if result.lower() == "x":
            return '   '

        if result in objects:
            return str(objects[result])
        try:
            first, second = result.split(".")
        except ValueError:
            return raw_result
        if first in objects and not second.startswith("_"):
            first = objects[first]
        else:
            return raw_result

        return str(getattr(first, second, raw_result))

    async def send_cmd_help(self, ctx, command=None):

        if not command:
            command = ctx.command
        cname = str(command).replace(" ", "-").lower()
        cname = str(cname).replace('pl-', 'pl')
        if command.help:
            prefix = get_server_prefixes(ctx.bot, ctx.guild)
            help_msg = get_str(ctx, f"cmd-{cname}-help")
            if ctx.channel.permissions_for(ctx.me).embed_links:
                embed = discord.Embed(title=f'{prefix}{str(command)}')
                help_msg = '\n'.join(command.help.split('\n\n')[
                                     1:]).format(help=help_msg)
                embed.description = help_msg
                cmds = '\n'.join([f'`{cmd.strip()}`' for cmd in command.help.split(
                    '\n\n')[0].format(command_prefix=prefix).split('\n')])
                embed.add_field(name='Usage', value=cmds, inline=False)
                if not ctx.guild:
                    embed.color = 0x71368a
                else:
                    embed.color = ctx.me.color
                if command.aliases:
                    aliases = '\n'.join(
                        [f'`{prefix}{(str(command.parent) + " ") if command.parent else ""}{a}`' for a in command.aliases])
                    embed.add_field(
                        name="Aliases", value=aliases, inline=False)
                return await ctx.send(embed=embed)
            else:
                return await ctx.send("```%s```" % dedent(ctx.command.help.format(command_prefix=get_server_prefixes(ctx.bot, ctx.guild), help=help_msg)))
        else:
            return await ctx.send(get_str(ctx, "cmd-help-help-not-found"))
            log.warning(f"MissingHelpError : {cname}")

    async def on_command_error(self, ctx, error):

        if not isinstance(ctx.channel, discord.abc.PrivateChannel):
            if self.debug_mode == ctx.message.guild.id:
                try:
                    await ctx.channel.send("```py\n" + str(error) + "```")
                except discord.HTTPException:
                    log.info("Can't send debug messages - Missing Permissions")
                    return

        if isinstance(error, commands.MissingRequiredArgument) or isinstance(error, commands.BadArgument):
            try:
                log.debug(f"{error}.. Sending help...")
                return await self.send_cmd_help(ctx)
            except discord.HTTPException:
                log.debug("Can't send help - Missing Permissions")
                return

        elif isinstance(error, commands.errors.CommandOnCooldown):
            try:
                scds = str(error).replace(
                    'You are on cooldown. Try again in', '')
                return await ctx.channel.send("```c\n{}{}```".format(get_str(ctx, "bot-cooldown"), scds), delete_after=10)
            except discord.HTTPException:
                log.debug("Can't send cooldown message - Missing Permissions")
                return

        elif isinstance(error, commands.errors.NoPrivateMessage):
            return await ctx.channel.send("```c\n{}```".format(get_str(ctx, "bot-not-mp")), delete_after=10)

        if isinstance(error, commands.errors.NotOwner):
            return

        elif isinstance(error, commands.errors.CheckFailure):
            try:
                return await ctx.channel.send("```c\n{} ({}permsinfo)```".format(get_str(ctx, 'bot-not-enough-permissions'), get_server_prefixes(ctx.bot, ctx.guild)), delete_after=10)
            except discord.HTTPException:
                log.debug(
                    "Can't send permissions failure message - Missing Permissions")
                return

        elif isinstance(error, commands.CommandNotFound):
            return

        elif NoVoiceChannel and isinstance(error, NoVoiceChannel):
            return

        else:
            if isinstance(error, commands.CommandInvokeError):
                if isinstance(error.original, discord.errors.Forbidden):
                    log.debug(
                        "discord.errors.Forbidden: FORBIDDEN (status code: 403): Missing Permissions")
                    return
                if isinstance(error.original, discord.errors.NotFound):
                    # log.info("discord.errors.NotFound: NotFound (status code: 404): Message not found")
                    return
                if isinstance(error.original, aiohttp.ClientError):
                    log.debug("Command raised an exception: ClientError")
                    return
                if isinstance(error.original, asyncio.futures.TimeoutError):
                    log.debug("Command raised an exception: TimeoutError")
                    return

            print('Ignoring exception in command {}:'.format(
                ctx.command), file=sys.stderr)
            traceback.print_exception(
                type(error), error, error.__traceback__, file=sys.stderr)
            log.error(f'Exception in command {ctx.command.name}: {error}')

    async def on_message(self, message):

        if not self.init_ok:
            return

        if message.author.bot:
            return

        if message.guild and not message.guild.me:  # should not happen no ?
            return

        if message.content in [f"<@!{self.user.id}>", self.user.mention]:
            message.content += " prefix now"

        prefixes = _prefix_callable(self, message)
        if not any(message.content.startswith(prefix) for prefix in prefixes):
            return

        for prefix in prefixes:
            if message.content.startswith(prefix):
                cmd_prefix = prefix  # Get the used prefix
                break

        if not isinstance(message.channel, discord.abc.PrivateChannel):
            settings = await SettingsDB.get_instance().get_guild_settings(message.guild.id)
            if not is_admin(message.author, message.channel):
                if not await self.on_message_check(message, settings, cmd_prefix):
                    return

        message_content = unidecode.unidecode(str(message.content))
        message_author = unidecode.unidecode(str(message.author))

        if not message.content[len(cmd_prefix):].strip() or not message.content[len(cmd_prefix):].strip().split(' '):
            return

        if self.get_command(message.content.strip()[len(cmd_prefix):].strip().split(' ')[0]):
            if message.author.id != owner_id and message.author.id in self.config.blacklisted:
                log.debug(
                    f"[User Blacklisted] {message.author.id}/{message_author} ({message_content.replace(cmd_prefix, globprefix, 1)[:50]})")

            else:
                log.info(
                    f"[Command] {message.author.id}/{message_author} ({message_content.replace(cmd_prefix, globprefix, 1)[:100]})")
                await self.process_commands(message)
                log.debug(
                    f"[Processed Command] {message.author.id}/{message_author} ({message_content.replace(cmd_prefix, globprefix, 1)[:100]})")

        # check if custom command exists
        elif not isinstance(message.channel, discord.abc.PrivateChannel):
            if settings.customcommands:
                await self.on_customcommand(message, settings, message_content, message_author, cmd_prefix)

    async def on_customcommand(self, message, settings, message_content, message_author, cmd_prefix):
        if settings.customcommands:
            cmd = message.content.lower()[len(cmd_prefix):].split(" ")[0]
            rest = None
            if len(message.content.lower()[len(cmd_prefix):].strip().split(" ")) > 1:
                rest = ' '.join(
                    message.content[len(cmd_prefix):].split(" ")[1:])
            if cmd in settings.customcommands:
                cmd = await self.format_cc(settings.customcommands[cmd], message)
                if message.author.id != owner_id and message.author.id in self.config.blacklisted:
                    log.debug(
                        f"[User Blacklisted CustomCommand] {message.author.id}/{message_author} ({message_content})")
                    return
                if ">>>" in cmd:
                    while ">>> " in cmd:
                        cmd = cmd.replace(">>> ", ">>>")

                    if "&&" in cmd:
                        if rest and "&&" in rest:
                            rest = rest.split("&&")
                        all = cmd.split("&&")
                        if len(all) > 9:
                            return await message.channel.send(get_str(message.guild, "cmd-choice-too-much-cmds", self), delete_after=10)
                        for m in all:
                            if m[-3:] == '   ':
                                m = m.lstrip()
                            else:
                                m = m.strip()
                            m = m[3:]
                            if 'download' in m:
                                message.id = 123  # hacky way to say that is a custom command
                            message.content = f"{cmd_prefix}{m}"
                            if len(m.split(' ')) < 2 and rest:
                                message.content += f" {rest}"
                            log.debug(
                                f"[CustomCommandCallMultiple] {message.author.id}/{message_author} ({message.content[:50]})")
                            await self.process_commands(message)
                        return

                    else:
                        if 'download' in cmd:
                            message.id = 123  # hacky way to say that is a custom command
                        message.content = cmd[3:]
                        message.content = f"{cmd_prefix}{message.content}"
                        if len(message.content.split(' ')) < 2 and rest:
                            message.content += f" {rest}"
                        log.debug(
                            f"[CustomCommandCall] {message.author.id}/{message_author} ({message.content[:50]})")
                        return await self.process_commands(message)

                pic = get_image_from_url(cmd)

                if pic:
                    e = discord.Embed()
                    e.set_image(url=pic)
                    cmds = cmd.replace(pic, "")
                    try:
                        await message.channel.send(embed=e, content=cmds)
                    except discord.Forbidden:
                        try:
                            await message.channel.send(get_str(message.guild, "need-embed-permission", self), delete_after=10)
                        except discord.Forbidden:
                            pass
                else:
                    try:
                        await message.channel.send(cmd)
                    except discord.Forbidden:
                        pass

                log.debug("[CustomCommand] {}/{} ({})".format(message.author.id,
                                                              message_author, message_content))

    async def on_message_check(self, message, settings, cmd_prefix):
        words = message.content[len(cmd_prefix):].split(' ')
        try:
            cmd = self.get_command(' '.join(words[:2]))
        except IndexError:
            cmd = None
        if not cmd:
            cmd = self.get_command(words[0])
        if cmd:
            command = cmd.name.lower()
            if cmd.parent:
                command = f'{cmd.parent.name.lower()} {command}'

        if str(message.channel.id) in settings.disabledchannels:
            if not settings.disabledchannels[str(message.channel.id)]:
                return False
            if cmd and command in settings.disabledchannels[str(message.channel.id)]:
                return False

        if settings.blacklisted:
            if message.author.id in settings.blacklisted:
                return False
            if any(r for r in message.author.roles if r.id in settings.blacklisted):
                return False

        if settings.disabledcommands:
            if cmd and command in settings.disabledcommands:
                try:
                    await message.channel.send("```c\n{}```".format(get_str(message.guild, "bot-disabled-command", self)), delete_after=10)
                except discord.Forbidden:
                    pass
                return False

        if settings.bound:
            if settings.bound in [c.id for c in message.guild.channels]:
                if settings.bound != message.channel.id:
                    try:
                        await message.channel.send("```\n{}```".format(get_str(message.guild, "bot-bind-mod", self)), delete_after=10)
                    except discord.Forbidden:
                        pass
                    return False
        return True

    async def on_ready(self):
        if self.init_ok:
            return
        # Store registred custom prefixes
        prefix_servers = SettingsDB.get_instance().guild_settings_collection.find(
            {
                "$and": [
                    {"prefix": {"$exists": True}},
                    {"prefix": {"$ne": globprefix}}
                ]
            }
        )

        async for server in prefix_servers:
            self.prefixes_map[server["_id"]] = server["prefix"]

        # Store registred custom languages
        language_servers = SettingsDB.get_instance().guild_settings_collection.find(
            {
                "$and": [
                    {"language": {"$exists": True}},
                    {"language": {"$ne": "english"}}
                ]
            }
        )

        async for lang in language_servers:
            self.languages_map[lang["_id"]] = lang["language"]

        # Store registred OwO mod
        owo_servers = SettingsDB.get_instance().guild_settings_collection.find(
            {
                "$and": [
                    {"owo": {"$exists": True}},
                    {"owo": {"$ne": False}}
                ]
            }
        )

        async for server in owo_servers:
            self.owo_map[server["_id"]] = server["owo"]

        # Store registred autosongs
        autosongs_servers = SettingsDB.get_instance().guild_settings_collection.find(
            {
                "$and": [
                    {"autosongs": {"$exists": True}},
                    {"autosongs": {"$ne": {}}}
                ]
            }
        )

        async for server in autosongs_servers:
            self.autosongs_map[server["_id"]] = server["autosongs"]

        # Multiprocessing guild count
        self.owner_id = owner_id
        self.config = await SettingsDB.get_instance().get_glob_settings()
        if self.is_main_process and self.shard_count != len(self.config.server_count):
            self.config.server_count = {}
            await SettingsDB.get_instance().set_glob_settings(self.config)

        # Load cogs
        for extension in _list_cogs():
            try:
                self.load_extension("cogs." + extension)
            except Exception as e:
                exc = '{}: {}'.format(type(e).__name__, e)
                log.warning(
                    'Failed to load extension {}\n{}'.format(extension, exc))

        total_cogs = len(_list_cogs())
        servers = len(self.guilds)
        owner = await self.safe_fetch('user', owner_id) or str(owner_id)

        log.info("-----------------")
        log.info("{} ({})".format(str(self.user), str(self.user.id)))
        log.info("{} server{}".format(servers, "s" if servers > 1 else ""))
        log.info("{} shard{}".format(self.shard_count,
                                     "s" if self.shard_count > 1 else ""))
        log.info("Prefix: {}".format(globprefix))
        log.info("Owner: {}".format(owner))
        log.info("{}/{} active cogs with {} commands".format(
            len(self.cogs), total_cogs, len(self.commands)))
        log.info("-----------------")

        if self.pipe and not self.pipe.closed:
            self.pipe.send(1)
            self.pipe.close()

        # Disable all loggers
        for name in ['launcher', 'lavalink', 'listenmoe']:
            logger = logging.getLogger(name)
            logger.disabled = not logger.disabled

        self.init_ok = True

    async def on_shard_ready(self, shard_id):
        log.info(f"Shard {shard_id} is ready")

    def run(self):
        super().run(token, reconnect=True, bot=True)
