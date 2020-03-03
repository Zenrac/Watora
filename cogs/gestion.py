import os
import aiohttp
import inspect
import discord
import asyncio
import traceback

from utils import checks
from utils.db import SettingsDB
from utils.dataIO import dataIO
from discord.ext import commands
from collections import Counter
from TextToOwO import owo as towo
from utils.chat_formatting import pagify, box
from utils.watora import globprefix, log, owner_id, get_server_prefixes, get_str, no_lang_loaded

cmds = {}
cmds['music'] = ["join", "np", "play", "queue", "search", "skip", "forceskip", "replay", "previous", "relatedsong", "replaynow", "previousnow", "stop", "pl", "radio",
                 "repeat", "pause", "volume", "playnow", "playnext", "clear", "promote", "shuffle", "remove", "moveto", "lyrics", "bassboost", "equalizer", "blindtest", "blindtestscore"]
cmds['fun'] = ["8ball", "minesweeper", "ily", "roll", "flip", "me", "customcommand", "choice",
               "ascii", "meme", "picture", "osu", "marry", "divorce", "anime", "manga", "char", "nextep"]  # TODO: Add mal command with a translation
cmds['useful'] = ["don", "info", "poll", "stats", "credits", "changelog", "permsinfo", "version", "infoshard", "avatar",
                  "userinfo", "serverinfo", "roleinfo", "getrole", "ping", "invitation", "suggestion", "bug", "feedback", "clan", "joinclan"]
cmds['moderation'] = ["kick", "ban", "hackban",
                      "voicekick", "clean", "purge", "stfu"]
cmds['config'] = ["prefix", "language", "owo", 'blacklist', 'settings', "defvolume", "defvote", "autoleave", "npmsg",
                  "welcome", "goodbye", "autorole", "ignore", "disabledcommand", "setdj", "bind", "lazy", "autoplay", "autoconnect"]

cmd_list = {
    'Social actions':           ['tickle', 'cuddle', 'kiss', 'pat', 'lick', 'hug', 'poke', 'slap', 'punch', 'stare', 'bite', 'shoot'],
    'Animals':                  ['cat', 'dog'],
    'Anime':                    ['megumin', 'jojo', 'initial_d'],
    'Anime actions':            ['smug', 'pout', 'sleepy', 'love', 'lewd', 'neko', 'nom', 'cry', 'dance', 'blush', 'shrug', 'insult', 'awoo', 'clagwimoth', 'smile', 'teehee', 'thumbsup', 'tail', 'waifu_insult', 'animedab', 'highfive', 'banghead', 'poi', 'greet', 'baka'],
    'Memes':                    ['wastedpic', 'discord_memes', 'delet_this', 'owopic', 'triggeredpic', 'nani', 'thinking'],
}

# Arcadia API
# cmd_list.update({
#   'Filters':                  ['triggered', 'triggeredinvert', 'illuminati', 'invert', 'convmatrix', 'convinvert', 'convolute', 'pixelate', 'tobecontinued', 'wasted', 'beautiful', 'bob', 'distortion', 'glitch', 'mosaic', 'blurple', 'halloween', 'orangly', 'blood', 'bloodhelp', 'blur', 'discordlogo', 'displace', 'ghost', 'grayscale', 'implode', 'posterize', 'sepia', 'snow', 'time', 'animeprotest', 'angry', 'codebabes', 'hitler', 'link', 'respect', 'whoisthis', 'shocked', 'alexflipnote'],
#  'Generators':               ['presidentialalert', 'thisexample', 'thisfilm', 'hibiki', 'shy', 'searching', 'bluneko', 'wanted', 'bravery', 'brilliance', 'balance', 'loveship']
# })
# Eclyssia API
cmd_list.update({
    'Filters':                  ['blur', 'triggered', 'whatspokemon', 'captcha', 'beautiful', 'greyscale', 'invert', 'pixelate', 'posterize', 'sepia'],
})

cmd_list.update({
    'Generators':               ['hibiki', 'shy', 'searching', 'bluneko'],
    'NSFW (in NSFW channel)':   ['neko', 'hentai']
})

# Dank Memer API
cmd_meme = {
    '1 avatar': ['wanted', 'hitler', 'goggles', 'radialblur', 'airpods',
                 'warp', 'aborted', 'affect', 'bongocat', 'cancer', 'dab', 'dank', 'deepfry',
                 'delete', 'disability', 'door', 'egg', 'failure', 'fakenews', 'fedora', 'gay', 'jail',
                 'laid', 'magik', 'rip', 'roblox', 'salty', 'satan', 'sickban', 'trash', 'ugly', 'warp', 'whodidthis'],
    '1 text': ['inator', 'stroke', 'violence', 'violentsparks', 'thesearch', 'sneakyfox',
               'piccolo', 'nothing', 'abandon', 'justpretending', 'fuck', 'expanddong', 'doglemon', 'corporate',
               'confusedcat', 'citation', 'cheating', 'armor', 'balloon', 'boo', 'brain', 'changemymind', 'crysip', 'excuseme',
               'facts', 'humansgood', 'knowyourlocation', 'master', 'note', 'ohno', 'plan', 'savehumanity', 'shit', 'slapsroof',
               'surprised', 'vr', 'walking'],
    '2 avatars': ['bed', 'madethis', 'screams', 'robinslap', 'spank'],
    '1 avatar 1 text 1 username': ['byemom', 'quote', 'tweet', 'youtube'],
    '1 avatar 1 text': ['garfield', 'floor', 'unpopular', 'whothisis']
}

for img_cmd in cmd_meme.values():
    cmd_list['Memes'] += img_cmd

cmd_help_msg = cmds.copy()

cmds['image'] = []
for img_cmd in cmd_list.values():
    cmds['image'] += img_cmd

for m, v in cmd_list.items():
    cmds[m.lower()] = v

cmds['all'] = []
for cat_cmd in cmds.values():
    cmds['all'] += cat_cmd


class Gestion(commands.Cog):
    """The gestion cog. Required to start the bot."""

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession(loop=self.bot.loop)
        self.load_languages()

    def cog_unload(self):
        asyncio.ensure_future(self.session.close())

    def load_languages(self):
        """Reloads languages in i18n, raise a ValueError when it fails"""
        self.languages = []
        savePath = os.getcwd() + "//config//i18n//"

        for file in os.listdir(savePath):
            self.languages.append(file.replace(".json", ""))
        for lang in self.languages:
            try:
                self.bot.loaded_languages[lang] = dataIO.load_json(
                    f"config/i18n/{lang+'.json'}")
            except ValueError as e:
                log.warning(f"[Translation] Failed to load {lang}\n({e})")
            else:
                log.debug(f"[Translation] Loaded : {lang}")
            for key in self.bot.loaded_languages[lang]:
                if key not in no_lang_loaded:
                    log.warning(f'Abnormal key found {key} in {lang}')
            for key in no_lang_loaded:
                if key not in self.bot.loaded_languages[lang]:
                    log.warning(f'Key not found {key} in {lang}')
        log.info(f"[Translation] All loaded!")

    async def set_server_prefixes(self, server, prefix):
        """Sets the prefix for the server."""
        settings = await SettingsDB.get_instance().get_guild_settings(server.id)

        if prefix in [globprefix, '', ' ', None]:
            settings.prefix = globprefix
            self.bot.prefixes_map.pop(server.id, None)
        else:
            settings.prefix = prefix[:200]  # Avoid stupid prefix
            self.bot.prefixes_map[server.id] = prefix

        await SettingsDB.get_instance().set_guild_settings(settings)

    @commands.group(aliases=["rl"])
    @commands.is_owner()
    async def reloadlanguage(self, ctx):
        """
            {command_prefix}reloadlanguage

        Reloads my languages.
        """
        try:
            self.load_languages()
            await ctx.send("Languages reloaded !")
        except ValueError as e:
            await ctx.send(f"Languages not reloaded ! `{e}`")

    @commands.command(aliases=['rt'])
    @commands.is_owner()
    async def reloadtokens(self, ctx):
        """
            {command_prefix}reloadtokens

        Reload the bot tokens.
        """
        self.bot.tokens = dataIO.load_json("config/tokens.json")
        await ctx.send("Tokens reloaded !")

    @commands.guild_only()
    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.user)
    @commands.command(name="clean", aliases=["cleanup", "deletemsg"])
    @checks.mod_or_permissions(manage_messages=True)
    async def _cleanup(self, ctx, search: int = 100):
        """
            {command_prefix}clean [num_msg]
            {command_prefix}clean

        {help}
        """
        search = min(int(search), 200)
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass
        spammers = Counter()
        channel = ctx.message.channel
        prefixes = [get_server_prefixes(
            ctx.bot, ctx.guild), ctx.me.mention, "watora"]
        if callable(prefixes):
            prefixes = prefixes(ctx.message.guild)

        def is_possible_command_invoke(entry):
            valid_call = any(entry.content.startswith(prefix.lower())
                             for prefix in prefixes)
            return valid_call and not entry.content[1:2].isspace()

        can_delete = ctx.channel.permissions_for(
            channel.guild.me).manage_messages

        if not can_delete:
            api_calls = 0
            async for entry in ctx.channel.history(limit=search, before=ctx.message):
                if api_calls and api_calls % 5 == 0:
                    await asyncio.sleep(1.1)

                if entry.author == self.bot.user:
                    try:
                        await entry.delete()
                    except discord.HTTPException:
                        pass
                    spammers['{}'.format(self.bot.user.name)] += 1
                    api_calls += 1

                if is_possible_command_invoke(entry):
                    try:
                        await entry.delete()
                    except discord.HTTPException:
                        continue
                    else:
                        spammers[entry.author.display_name] += 1
                        api_calls += 1
        else:
            def predicate(m): return m.author == self.bot.user or is_possible_command_invoke(m)  # noqa: E731
            try:
                deleted = await ctx.channel.purge(limit=search, before=ctx.message, check=predicate)
            except discord.NotFound:
                return
            spammers = Counter(m.author.display_name for m in deleted)

        deleted = sum(spammers.values())
        messages = ["{} {}".format(deleted, get_str(
            ctx, "cmd-clean-cleaned-message") if deleted == 1 else get_str(ctx, "cmd-clean-cleaned-messages"))]

        if deleted:
            messages.append('')
            spammers = sorted(spammers.items(),
                              key=lambda t: t[1], reverse=True)
            messages.extend(
                map(lambda t: '- **{0[0]}**: {0[1]}'.format(t), spammers))

        if search > 1:  # Don't send message if user wrote 1 (custom command?)
            await ctx.send('\n'.join(messages), delete_after=5)

    @commands.command(aliases=["prune", "purgeall", "deleteall"])
    @commands.guild_only()
    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.user)
    @checks.mod_or_permissions(manage_messages=True)
    async def purge(self, ctx, search_range: int = 100):
        """
            {command_prefix}purge [num_msg]
            {command_prefix}purge

        {help}
        """
        search_range = min(int(search_range), 200)
        if self.bot.user.bot:
            if ctx.channel.permissions_for(ctx.me).manage_messages:
                try:
                    await ctx.message.delete()
                    await ctx.channel.purge(limit=search_range, before=ctx.message)
                except discord.HTTPException:
                    pass
            else:
                await ctx.send(get_str(ctx, "need-manage-messages-permission"))

    @commands.guild_only()
    @commands.command(aliases=["tg", "ftg"])
    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.user)
    @checks.mod_or_permissions(manage_messages=True)
    async def stfu(self, ctx, user: discord.Member, search_range: int = 100):
        """
            {command_prefix}stfu [user] [num_msg]
            {command_prefix}stfu [user]

        {help}
        """
        search_range = min(int(search_range), 200)
        if user.id == owner_id != ctx.author.id:
            return await ctx.send("Nope.")
        if self.bot.user.bot:
            if ctx.channel.permissions_for(ctx.me).manage_messages:
                try:
                    await ctx.message.delete()
                    await ctx.channel.purge(limit=search_range, before=ctx.message, check=lambda m: m.author == user)
                except discord.HTTPException:
                    pass
            else:
                await ctx.send(get_str(ctx, "need-manage-messages-permission"))

    @commands.group(aliases=["prefixe", "prefixes"])
    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.user)
    @commands.guild_only()
    async def prefix(self, ctx):
        """
            {command_prefix}prefix change [new_prefix]
            {command_prefix}prefix now
            {command_prefix}prefix reset

        {help}
        """
        if not ctx.invoked_subcommand:
            await ctx.send(get_str(ctx, "command-invalid-usage").format("{}help prefix".format(get_server_prefixes(ctx.bot, ctx.guild))))

    @prefix.command(name="change", aliases=["set", "config"])
    @commands.guild_only()
    @checks.has_permissions(manage_guild=True)
    async def _change(self, ctx, *, prefixes: str):
        """
            {command_prefix}prefix change [new_prefix]

        {help}
        """
        if prefixes.startswith('[') and prefixes.endswith(']'):
            prefixes = prefixes[1:-1].lstrip()
        if prefixes in [globprefix, '', ' ', None]:
            return await ctx.invoke(self._reset)
        await self.set_server_prefixes(ctx.guild, prefixes)
        await ctx.send(get_str(ctx, "cmd-prefix-set-prefix").format(f"{prefixes}prefix reset"))

    @prefix.command(name='reset', aliases=["stop", globprefix, "off", "normal"])
    @checks.has_permissions(manage_guild=True)
    async def _reset(self, ctx):
        """
            {command_prefix}prefix reset

        {help}
        """
        await self.set_server_prefixes(ctx.message.guild, globprefix)
        await ctx.send(get_str(ctx, "cmd-prefix-reset").format(globprefix))

    @prefix.command(name='now', aliases=["atm", "current"])
    async def _now(self, ctx):
        """
            {command_prefix}prefix now

        {help}
        """
        prefix = self.bot.prefixes_map.get(ctx.guild.id, globprefix)
        await ctx.send(get_str(ctx, "cmd-prefix-current").format(prefix))

    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.user)
    @commands.command(aliases=["disabled"])
    @checks.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def ignore(self, ctx, channel: discord.TextChannel = None, param: str = None, *, command: str = None):
        """
            {command_prefix}ignore [channel] add [command|all|category]
            {command_prefix}ignore [channel] remove [command|all|category]
            {command_prefix}ignore [channel] now
            {command_prefix}ignore [channel]
            {command_prefix}ignore

        {help}
        """
        if not channel:
            channel = ctx.channel

        cid = str(channel.id)
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)

        if param and param != "all":
            if param.lower().startswith('n'):
                if cid not in settings.disabledchannels:
                    return await ctx.send(get_str(ctx, "cmd-ignore-not-disabled").format("`{}`".format(channel.name)))
                if not settings.disabledchannels[cid]:
                    return await ctx.send(get_str(ctx, "cmd-ignore-all-disabled").format("`{}`".format(channel.name)))
                info = '`{}`'.format('`, `'.join(
                    settings.disabledchannels[cid]))
                if len(info) > 1700:
                    await ctx.send(get_str(ctx, "cmd-ignore-number-commands").format(
                        len(settings.disabledchannels[cid]), channel.name))
                else:
                    await ctx.send(get_str(ctx, "cmd-ignore-now").format(f"`{channel.name}`", "\n\n{}".format(info)))
            elif command:
                strcommand = command = command.lower()
                if strcommand in cmds:
                    if strcommand == "all":
                        return await ctx.invoke(self.ignore, channel=channel)
                    cmd = cmds[strcommand]
                else:
                    cmd = self.bot.get_command(strcommand)
                    if cmd:
                        total_command = cmd.name
                        if cmd.parent:
                            total_command = f'{cmd.parent} {total_command}'
                if not cmd:
                    return await ctx.send(get_str(ctx, "cmd-dc-cmd-not-found"))
                if param.lower().startswith('r'):
                    disabled_cmds = [1]
                    if cid in settings.disabledchannels:
                        if isinstance(cmd, list):
                            disabled_cmds = []
                            for c in cmd:
                                if c in settings.disabledchannels[cid]:
                                    settings.disabledchannels[cid].remove(c)
                                    disabled_cmds.append(c)
                        elif total_command in settings.disabledchannels[cid]:
                            settings.disabledchannels[cid].remove(
                                total_command)
                    else:
                        return await ctx.send(get_str(ctx, "cmd-ignore-enabled").format("0", "`{}`".format(channel.name)))
                    if settings.disabledchannels[cid]:
                        info = '`{}`'.format('`, `'.join(
                            settings.disabledchannels[cid]))
                        if len(info) > 1700:
                            await ctx.send(get_str(ctx, "cmd-ignore-enabled").format(len(disabled_cmds), "`{}`".format(channel.name)))
                        else:
                            await ctx.send(get_str(ctx, "cmd-ignore-now").format(f"`{channel.name}`", "\n\n{}".format(info)))
                    else:
                        settings.disabledchannels.pop(cid)
                        await ctx.send(get_str(ctx, "cmd-ignore-no-anymore"))
                else:
                    disabled_cmds = [1]
                    if cid not in settings.disabledchannels:
                        settings.disabledchannels[cid] = cmd if isinstance(cmd, list) else [
                            total_command]
                    else:
                        if isinstance(cmd, list):
                            disabled_cmds = []
                            for c in cmd:
                                if c not in settings.disabledchannels[cid]:
                                    settings.disabledchannels[cid].append(c)
                                    disabled_cmds.append(c)
                        elif total_command not in settings.disabledchannels[cid]:
                            settings.disabledchannels[cid].append(
                                total_command)
                    info = '`{}`'.format('`, `'.join(
                        settings.disabledchannels[cid]))
                    if len(info) > 1700:
                        await ctx.send(get_str(ctx, "cmd-ignore-disabled").format(len(disabled_cmds), "`{}`".format(channel.name)))
                    else:
                        await ctx.send(get_str(ctx, "cmd-ignore-now").format(f"`{channel.name}`", "\n\n{}".format(info)))

                await SettingsDB.get_instance().set_guild_settings(settings)
            else:
                return await self.bot.send_cmd_help(ctx)
        else:
            if cid not in settings.disabledchannels:
                settings.disabledchannels[cid] = []
                await SettingsDB.get_instance().set_guild_settings(settings)
                await ctx.send(get_str(ctx, "cmd-ignore-commands-disabled"))
            else:
                settings.disabledchannels.pop(cid)
                await SettingsDB.get_instance().set_guild_settings(settings)
                await ctx.send(get_str(ctx, "cmd-ignore-commands-enabled"))

    @commands.group(aliases=["dc", "disabledcommande", "disabledcom"])
    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.user)
    @commands.guild_only()
    async def disabledcommand(self, ctx):
        """
            {command_prefix}dc add [command|all|category]
            {command_prefix}dc delete [command|all|category]
            {command_prefix}dc list

        {help}
        """
        if not ctx.invoked_subcommand:
            await ctx.send(get_str(ctx, "command-invalid-usage").format("{}help dc".format(get_server_prefixes(ctx.bot, ctx.guild))))

    @checks.has_permissions(manage_guild=True)
    @disabledcommand.command(name="add", aliases=["+", "new", 'a'])
    async def dc_add(self, ctx, *, command):
        """
            {command_prefix}dc add [command|all|category]

        {help}
        """
        strcommand = command = command.lower()
        if strcommand in cmds:
            settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
            disabled_cmds = []
            for cmd in cmds[strcommand]:
                if cmd not in settings.disabledcommands:
                    settings.disabledcommands.append(cmd)
                    disabled_cmds.append(cmd)
            await SettingsDB.get_instance().set_guild_settings(settings)
            info = '{}'.format('`, `'.join(disabled_cmds))
            if len(info) > 1700 or not disabled_cmds:
                return await ctx.send(get_str(ctx, "cmd-ignore-disabled").format(len(disabled_cmds), "`{}`".format(ctx.guild.name)))

            return await ctx.send(get_str(ctx, "cmd-dc-add-cmd-now-disabled").format(info))

        cmd = self.bot.get_command(strcommand)
        if not cmd:
            return await ctx.send(get_str(ctx, "cmd-dc-cmd-not-found"))
        command = cmd.name
        if cmd.parent:
            command = f'{cmd.parent} {command}'

        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        if command not in settings.disabledcommands:
            settings.disabledcommands.append(command)
            await SettingsDB.get_instance().set_guild_settings(settings)
            await ctx.send(get_str(ctx, "cmd-dc-add-cmd-now-disabled").format(command))
        else:
            await ctx.send(get_str(ctx, "cmd-dc-add-already-disabled").format("{}dc remove".format(get_server_prefixes(ctx.bot, ctx.guild))))

    @checks.has_permissions(manage_guild=True)
    @disabledcommand.command(name="remove", aliases=["delete", "-", 'r'])
    async def dc_delete(self, ctx, *, command):
        """
            {command_prefix}dc remove [command|all|category]

        {help}
        """
        strcommand = command = command.lower()
        if strcommand in cmds:
            settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
            if strcommand == 'all':
                count = len(settings.disabledcommands)
                settings.disabledcommands.clear()
                await SettingsDB.get_instance().set_guild_settings(settings)
                return await ctx.send(get_str(ctx, "cmd-ignore-enabled").format(count, "`{}`".format(ctx.guild.name)))
            disabled_cmds = []
            for cmd in cmds[strcommand]:
                if cmd in settings.disabledcommands:
                    settings.disabledcommands.remove(cmd)
                    disabled_cmds.append(cmd)
            await SettingsDB.get_instance().set_guild_settings(settings)
            info = '{}'.format('`, `'.join(disabled_cmds))
            if len(info) > 1700 or not disabled_cmds:
                return await ctx.send(get_str(ctx, "cmd-ignore-enabled").format(len(disabled_cmds), "`{}`".format(ctx.guild.name)))
            if disabled_cmds:
                return await ctx.send(get_str(ctx, "cmd-dc-delete-enabled-anew").format(info))
        cmd = self.bot.get_command(strcommand)
        if not cmd:
            return await ctx.send(get_str(ctx, "cmd-dc-cmd-not-found"))
        command = cmd.name
        if cmd.parent:
            command = f'{cmd.parent} {command}'
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        if settings.disabledcommands:
            if command in settings.disabledcommands:
                settings.disabledcommands.remove(command)
                await SettingsDB.get_instance().set_guild_settings(settings)
                await ctx.send(get_str(ctx, "cmd-dc-delete-enabled-anew").format(command))
            else:
                await ctx.send(get_str(ctx, "cmd-dc-delete-is-not-disabled"))
        else:
            await ctx.send(get_str(ctx, "cmd-dc-delete-no-disabled-commands").format("{}dc add".format(get_server_prefixes(ctx.bot, ctx.guild))))

    @disabledcommand.command(name="list", aliases=["all", "view", "now"])
    async def dc_list(self, ctx):
        """
            {command_prefix}dc list

        {help}
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)

        if not settings.disabledcommands:
            return await ctx.send(get_str(ctx, "cmd-dc-delete-no-disabled-commands").format("{}dc add".format(get_server_prefixes(ctx.bot, ctx.guild))))

        msg = "{}\n{}".format(get_str(ctx, "cmd-dc-list-list"),
                              '`{}`'.format('`, `'.join(settings.disabledcommands)))

        to_send = ""
        for line in msg:
            if len(to_send) + len(line) > 1980:  # TODO find a better way to do this
                await ctx.send(to_send)          # This is ugly
                to_send = ""
            to_send += line

        if to_send:
            await ctx.send(to_send)

    @commands.guild_only()
    @commands.group(aliases=["bl"])
    async def blacklist(self, ctx):
        """
            {command_prefix}blacklist add [user|role]
            {command_prefix}blacklist remove [user|role]
            {command_prefix}blacklist clear
            {command_prefix}blacklist list

        {help}
        """
        if not ctx.invoked_subcommand:
            await ctx.send(get_str(ctx, "command-invalid-usage").format("{}help blacklist".format(get_server_prefixes(ctx.bot, ctx.guild))))

    @checks.has_permissions(manage_guild=True)
    @blacklist.command(name="add", aliases=["+"])
    async def _blacklist_add(self, ctx, *, name):
        """
            {command_prefix}blacklist add [user|role]

        {help}
        """
        is_role = False

        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)

        if ctx.message.mentions:
            user = ctx.message.mentions[-1]
            if user.mention not in name:  # It was a prefix
                user = None
                if len(ctx.message.mentions) > 1:
                    user = ctx.message.mentions[0]
            if user:
                name = str(user.id)  # or int conv fail with .lower() etc

        targets = [r for r in ctx.guild.members if r.name.lower() ==
                   name.lower() or str(r.id) == name]
        if not targets:  # maybe a role
            is_role = True
            target = self.bot.get_role(ctx, name)

            if not target:
                return await self.bot.send_cmd_help(ctx)
        else:
            target = targets[0]

        if target.id not in settings.blacklisted:
            settings.blacklisted.append(target.id)
            await SettingsDB.get_instance().set_guild_settings(settings)
            await ctx.send(get_str(ctx, "cmd-blacklist{}-added".format("-r" if is_role else '')))
        else:
            await ctx.send(get_str(ctx, "cmd-blacklist{}-a-bl".format("-r" if is_role else '')))

    @checks.has_permissions(manage_guild=True)
    @blacklist.command(name="remove", aliases=["-"])
    async def _blacklist_remove(self, ctx, *, name):
        """
            {command_prefix}blacklist remove [user|role]

        {help}
        """
        is_role = False

        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)

        if ctx.message.mentions:
            user = ctx.message.mentions[-1]
            if user.mention not in name:  # It was a prefix
                user = None
                if len(ctx.message.mentions) > 1:
                    user = ctx.message.mentions[0]
            if user:
                name = str(user.id)  # or int conv fail with .lower() etc

        targets = [r for r in ctx.guild.members if r.name.lower() ==
                   name.lower() or str(r.id) == name]
        if not targets:  # maybe a role
            is_role = True
            target = self.bot.get_role(ctx, name)

            if not target:
                return await self.bot.send_cmd_help(ctx)
        else:
            target = targets[0]

        if settings.blacklisted:
            if target.id in settings.blacklisted:
                settings.blacklisted.remove(target.id)
                await SettingsDB.get_instance().set_guild_settings(settings)
                await ctx.send(get_str(ctx, "cmd-blacklist{}-removed".format("-r" if is_role else '')))
            else:
                await ctx.send(get_str(ctx, "cmd-blacklist-not-bl"))
        else:
            await ctx.send(get_str(ctx, "cmd-blacklist-no-bl-og"))

    @blacklist.command(name="list")
    async def _blacklist_list(self, ctx):
        """
            {command_prefix}blacklist list

        {help}
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)

        blacklist = self._guild_populate_list(ctx, settings.blacklisted)

        if blacklist:
            for page in blacklist:
                await ctx.send(box(page))
        else:
            await ctx.send(get_str(ctx, "cmd-blacklist-is-empty"))

    @checks.has_permissions(manage_guild=True)
    @blacklist.command(name="clear")
    async def _blacklist_clear(self, ctx):
        """
            {command_prefix}blacklist clear

        {help}
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)

        settings.blacklisted = []
        await SettingsDB.get_instance().set_guild_settings(settings)
        await ctx.send(get_str(ctx, "cmd-blacklist-now-empty"))

    @commands.guild_only()
    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.user)
    @commands.command(aliases=["lang", "langage"])
    async def language(self, ctx, lang):
        """
            {command_prefix}language [lang]
            {command_prefix}language list

        {help}
        """

        if lang.lower() in ['list', 'view', 'all', 'info']:
            msg = "- "
            msg += '\n- '.join(self.languages)
            embed = discord.Embed()
            if ctx.guild:
                embed.color = ctx.me.color
            footer = f"I need help to get translated in other languages ! Please join **[my server](https://discord.gg/ArJgTpM)** if you feel interested."
            embed.description = "**Available languages**\n\n{}\n\n{}".format(
                msg, footer)
            try:
                return await ctx.send(embed=embed)
            except discord.Forbidden:
                return await ctx.send(get_str(ctx, "need-embed-permission"))

        elif not ctx.channel.permissions_for(ctx.author).manage_guild and not ctx.author.id == owner_id:
            raise commands.errors.CheckFailure

        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)

        langs = [g for g in self.languages]
        for available_lang in langs:
            if available_lang.startswith(lang.lower()):
                lang = available_lang
        if lang.lower() in langs:
            if settings.language == lang.lower():
                return await ctx.send(get_str(ctx, "cmd-already-language"))
            settings.language = lang.lower()
            self.bot.languages_map[ctx.guild.id] = lang.lower()
            await SettingsDB.get_instance().set_guild_settings(settings)
            await ctx.send(get_str(ctx, "cmd-new-language"))
        else:
            await ctx.send(get_str(ctx, "cmd-language-invalid-language").format("`{}language list`".format(get_server_prefixes(ctx.bot, ctx.guild))))

    @commands.guild_only()
    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.user)
    @commands.command(aliases=["modeowo", 'owofy', "modowo", "langowo", "owolang", "owomod"])
    async def owo(self, ctx, *, text=None):
        """
            {command_prefix}owo [text]
            {command_prefix}owo

        {help}
        """
        if text:
            return await ctx.send(towo.text_to_owo(text))
        else:
            if not ctx.channel.permissions_for(ctx.author).manage_guild and not ctx.author.id == owner_id:
                raise commands.errors.CheckFailure

            settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)

            settings.owo = not settings.owo
            self.bot.owo_map[ctx.guild.id] = settings.owo
            await SettingsDB.get_instance().set_guild_settings(settings)
            await ctx.send(get_str(ctx, "cmd-owo-status") + " " + get_str(ctx, "cmd-owo-{}".format(['disabled', 'enabled'][settings.owo])) + ' {}'.format("^w^" if settings.owo else '!'))

    @commands.group(aliases=["sbl"])
    @commands.is_owner()
    async def superblacklist(self, ctx):
        """
            {command_prefix}superblacklist add [user]
            {command_prefix}superblacklist remove [user]
            {command_prefix}superblacklist clear
            {command_prefix}superblacklist list

        Manages my blacklist commands.
        """
        if not ctx.invoked_subcommand:
            await ctx.send(get_str(ctx, "command-invalid-usage").format("{}help blacklist".format(get_server_prefixes(ctx.bot, ctx.guild))))

    @superblacklist.command(name="add", aliases=["+"])
    async def _superblacklist_add(self, ctx, *, user: discord.Member):
        """
            {command_prefix}superblacklist add [user]

        Adds a user to my blacklist.
        """
        settings = await SettingsDB.get_instance().get_glob_settings()
        if user.id not in settings.blacklisted:
            settings.blacklisted.append(user.id)
            await SettingsDB.get_instance().set_glob_settings(settings)
            self.bot.config = settings
            await ctx.send("User has been blacklisted.")
        else:
            await ctx.send("User is already blacklisted.")

    @superblacklist.command(name="addid", aliases=["+id"])
    async def _superblacklist_addid(self, ctx, id: int):
        """
            {command_prefix}superblacklist addid [id]

        Adds a user id to my blacklist.
        """
        settings = await SettingsDB.get_instance().get_glob_settings()
        user = await self.bot.safe_fetch('member', id, guild=ctx.guild)
        if not user:
            await ctx.send("User not found, if you really want to superblacklist it, use `{}sbl hackaddid`".format(get_server_prefixes(ctx.bot, ctx.guild)))
        elif user.id not in settings.blacklisted:
            settings.blacklisted.append(user.id)
            await SettingsDB.get_instance().set_glob_settings(settings)
            self.bot.config = settings
            await ctx.send("User has been blacklisted.")
        else:
            await ctx.send("User is already blacklisted.")

    @superblacklist.command(name="hackaddid", aliases=["hack+id", "hid"])
    async def _superblacklist_hackaddid(self, ctx, id: int):
        """
            {command_prefix}superblacklist addid [id]

        Adds a user id to my blacklist even if I can't find him on my servers.
        """
        settings = await SettingsDB.get_instance().get_glob_settings()
        if id not in settings.blacklisted:
            settings.blacklisted.append(id)
            await SettingsDB.get_instance().set_glob_settings(settings)
            self.bot.config = settings
            await ctx.send("User has been blacklisted.")
        else:
            await ctx.send("User is already blacklisted.")

    @superblacklist.command(name="remove", aliases=["-"])
    async def _superblacklist_remove(self, ctx, *, user: discord.Member):
        """
            {command_prefix}superblacklist remove [user]

        Removes a user from my blacklist.
        """
        settings = await SettingsDB.get_instance().get_glob_settings()
        if user.id in settings.blacklisted:
            settings.blacklisted.remove(user.id)
            await SettingsDB.get_instance().set_glob_settings(settings)
            self.bot.config = settings
            await ctx.send("User has been removed from the blacklist.")
        else:
            await ctx.send("User is not blacklisted.")

    @superblacklist.command(name="removeid", aliases=["-id"])
    async def _superblacklist_removeid(self, ctx, *, id: int):
        """
            {command_prefix}superblacklist removeid [id]

        Removes a user id from my blacklist.
        """
        settings = await SettingsDB.get_instance().get_glob_settings()
        if id in settings.blacklisted:
            settings.blacklisted.remove(id)
            await SettingsDB.get_instance().set_glob_settings(settings)
            self.bot.config = settings
            await ctx.send("User has been removed from the blacklist.")
        else:
            await ctx.send("User is not blacklisted.")

    @superblacklist.command(name="list")
    async def _superblacklist_list(self, ctx):
        """
            {command_prefix}superblacklist list

        Displays my blacklist.
        """
        settings = await SettingsDB.get_instance().get_glob_settings()
        blacklist = self._populate_list(settings.blacklisted)

        if blacklist:
            for page in blacklist:
                await ctx.send(box(page))
        else:
            await ctx.send("The blacklist is empty.")

    @superblacklist.command(name="clear")
    async def _superblacklist_clear(self, ctx):
        """
            {command_prefix}superblacklist clear

        Clears my blacklist.
        """
        settings = await SettingsDB.get_instance().get_glob_settings()
        settings.blacklisted = []
        await SettingsDB.get_instance().set_glob_settings(settings)
        self.bot.config = settings
        await ctx.send("Blacklist is now empty.")

    def _populate_list(self, _list):
        users = []
        total = len(_list)

        for user_id in _list:
            user = discord.utils.get(self.bot.get_all_members(), id=user_id)
            if user:
                users.append(str(user))

        if users:
            not_found = total - len(users)
            users = ", ".join(users)
            if not_found:
                users += "\n\n ... and {} users I could not find".format(
                    not_found)
            return list(pagify(users, delims=[" ", "\n"]))

        return []

    def _guild_populate_list(self, ctx, _list):
        users = []
        total = len(_list)

        for user_id in _list:
            user = discord.utils.get(ctx.guild.members, id=user_id)
            if not user:
                user = discord.utils.get(ctx.guild.roles, id=user_id)
            if user:
                users.append(str(user))

        if users:
            not_found = total - len(users)
            users = ", ".join(users)
            if not_found:
                users += "\n\n ... and {} users I could not find".format(
                    not_found)
            return list(pagify(users, delims=[" ", "\n"]))

        return []

    @commands.command(aliases=['vck', 'vk', 'vckick', 'voicechannelkick', 'kickvoicechannel', 'vkick', 'voicechankick'])
    @commands.guild_only()
    @checks.has_permissions(manage_channels=True)
    async def voicekick(self, ctx, *, user: discord.Member):
        """
            {command_prefix}voicekick [user]

        {help}
        """
        if not ctx.author.guild_permissions.move_members:
            raise commands.errors.CheckFailure

        if not ctx.me.guild_permissions.move_members or not ctx.channel.permissions_for(ctx.me).manage_channels:
            return await ctx.send(get_str(ctx, "not-enough-permissions"))

        if user.top_role.position > ctx.author.top_role.position and ctx.author.id != owner_id and not ctx.author is ctx.guild.owner:
            return await ctx.send(get_str(ctx, "role-not-enough-high"))

        dest = await ctx.guild.create_voice_channel(name='voicekick', reason=f'[ {ctx.author} ] Voicekick')

        if not user.voice:
            return await ctx.send(get_str(ctx, "cmd-userinfo-not-connected"))

        await user.move_to(channel=dest, reason=f'[ {ctx.author} ] Voicekick')

        await dest.delete(reason=f'[ {ctx.author} ] Voicekick')
        await ctx.message.add_reaction('👢')

    @commands.command()
    @commands.guild_only()
    @checks.has_permissions(kick_members=True)
    async def kick(self, ctx, *, user: discord.Member):
        """
            {command_prefix}kick [user]

        {help}
        """
        if not ctx.channel.permissions_for(ctx.me).kick_members:
            return await ctx.send(get_str(ctx, "not-enough-permissions"))

        if user.id == owner_id != ctx.author:
            return await ctx.send(get_str(ctx, "cmd-kick-cant-kick").format(ctx.guild.get_member(owner_id).name))

        if user.id == ctx.me.id:
            return await ctx.send(get_str(ctx, "cmd-kick-cant-kick-myself"))

        if user.top_role.position >= ctx.author.top_role.position and ctx.author.id != owner_id and not ctx.author is ctx.guild.owner:
            return await ctx.send(get_str(ctx, "role-not-enough-high"))
        if user.top_role.position >= ctx.me.top_role.position:
            return await ctx.send(get_str(ctx, "not-enough-permissions"))

        confirm_message = await ctx.send(get_str(ctx, "cmd-kick-confirmation-kick").format(user or id))

        def check(m):
            if m.author.bot or m.author != ctx.author:
                return False
            if m.channel != ctx.channel:
                return False
            if m.content and m.content.lower()[0] in "yn" or m.content.lower().startswith(get_server_prefixes(ctx.bot, ctx.guild)) or m.content.startswith(m.guild.me.mention) or m.content.lower().startswith('exit'):
                return True
            return False

        try:
            response_message = await self.bot.wait_for('message', timeout=30, check=check)
        except asyncio.TimeoutError:
            try:
                await confirm_message.delete()
            except discord.HTTPException:
                pass
            return await ctx.send(get_str(ctx, "cmd-kick-cancelling-kick"), delete_after=30)

        if response_message.content.lower().startswith('y'):
            try:
                await user.send(get_str(ctx, "cmd-kick-kicked").format(ctx.guild.name) + " {0.name}#{0.discriminator}.".format(ctx.author))
            except discord.Forbidden:
                pass
            try:
                await ctx.guild.kick(user)
            except discord.Forbidden:
                return await user.send(get_str(ctx, "cmd-kick-failed"))

            await ctx.send("```c\n" + get_str(ctx, "cmd-kick-success").format(user) + f" {ctx.author}.```")
        else:
            await ctx.send(get_str(ctx, "cmd-kick-cancelled"))

    @commands.command(aliases=["directban"])
    @commands.guild_only()
    @checks.has_permissions(ban_members=True)
    async def bandirect(self, ctx, *, user: discord.Member):
        """
            {command_prefix}directban [user]

        Bans a user from the server without confirmation.
        """
        if not ctx.channel.permissions_for(ctx.me).ban_members:
            return await ctx.send(get_str(ctx, "not-enough-permissions"))

        if user.id == owner_id != ctx.author:
            return await ctx.send(get_str(ctx, "cmd-kick-cant-kick").format(ctx.guild.get_member(owner_id).name))

        if user.id == ctx.me.id:
            return await ctx.send(get_str(ctx, "cmd-kick-cant-kick-myself"))

        if user.top_role.position >= ctx.author.top_role.position and ctx.author.id != owner_id and not ctx.author is ctx.guild.owner:
            return await ctx.send(get_str(ctx, "role-not-enough-high"))
        if user.top_role.position >= ctx.me.top_role.position:
            return await ctx.send(get_str(ctx, "not-enough-permissions"))

        try:
            await user.send(get_str(ctx, "cmd-ban-banned").format(ctx.guild.name) + " {0.name}#{0.discriminator}.".format(ctx.author))
        except discord.Forbidden:
            pass

        try:
            await ctx.guild.ban(user)
        except discord.Forbidden:
            return await user.send(get_str(ctx, "cmd-ban-failed"))

        await ctx.send("```c\n" + get_str(ctx, "cmd-ban-success").format(user) + f" {ctx.author}.```")

    @commands.command(aliases=["directkick"])
    @commands.guild_only()
    @checks.has_permissions(ban_members=True)
    async def kickdirect(self, ctx, *, user: discord.Member):
        """
            {command_prefix}directkick [user]

        Kicks a user from the server without confirmation.
        """
        if not ctx.channel.permissions_for(ctx.me).ban_members:
            return await ctx.send(get_str(ctx, "not-enough-permissions"))

        if user.id == owner_id != ctx.author:
            return await ctx.send(get_str(ctx, "cmd-kick-cant-kick").format(ctx.guild.get_member(owner_id).name))

        if user.id == ctx.me.id:
            return await ctx.send(get_str(ctx, "cmd-kick-cant-kick-myself"))

        if user.top_role.position >= ctx.author.top_role.position and ctx.author.id != owner_id and not ctx.author is ctx.guild.owner:
            return await ctx.send(get_str(ctx, "role-not-enough-high"))
        if user.top_role.position >= ctx.me.top_role.position:
            return await ctx.send(get_str(ctx, "not-enough-permissions"))

        try:
            await user.send(get_str(ctx, "cmd-kick-kicked").format(ctx.guild.name) + " {0.name}#{0.discriminator}.".format(ctx.author))
        except discord.Forbidden:
            pass

        try:
            await ctx.guild.ban(user)
        except discord.Forbidden:
            return await user.send(get_str(ctx, "cmd-kick-failed"))

        await ctx.send("```c\n" + get_str(ctx, "cmd-kick-success").format(user) + f" {ctx.author}.```")

    @commands.command()
    @commands.guild_only()
    @checks.has_permissions(ban_members=True)
    async def ban(self, ctx, *, user: discord.Member):
        """
            {command_prefix}ban [user]

        {help}
        """
        if not ctx.channel.permissions_for(ctx.me).ban_members:
            return await ctx.send(get_str(ctx, "not-enough-permissions"))

        if user.id == owner_id != ctx.author:
            return await ctx.send(get_str(ctx, "cmd-kick-cant-kick").format(ctx.guild.get_member(owner_id).name))

        if user.id == ctx.me.id:
            return await ctx.send(get_str(ctx, "cmd-kick-cant-kick-myself"))

        if user.top_role.position >= ctx.author.top_role.position and ctx.author.id != owner_id and not ctx.author is ctx.guild.owner:
            return await ctx.send(get_str(ctx, "role-not-enough-high"))
        if user.top_role.position >= ctx.me.top_role.position:
            return await ctx.send(get_str(ctx, "not-enough-permissions"))

        def check(m):
            if m.author.bot or m.author != ctx.author:
                return False
            if m.channel != ctx.channel:
                return False
            if m.content and m.content.lower()[0] in "yn" or m.content.lower().startswith(get_server_prefixes(ctx.bot, ctx.guild)) or m.content.startswith(m.guild.me.mention) or m.content.lower().startswith('exit'):
                return True
            return False

        confirm_message = await ctx.send(get_str(ctx, "cmd-ban-confirmation-ban").format(user))

        try:
            response_message = await self.bot.wait_for('message', timeout=30, check=check)
        except asyncio.TimeoutError:
            try:
                await confirm_message.delete()
            except discord.HTTPException:
                pass
            return await ctx.send(get_str(ctx, "cmd-ban-cancelling-ban"), delete_after=30)

        if response_message.content.lower().startswith('y'):
            try:
                await user.send(get_str(ctx, "cmd-ban-banned").format(ctx.guild.name) + " {0.name}#{0.discriminator}.".format(ctx.author))
            except discord.Forbidden:
                pass

            try:
                await ctx.guild.ban(user)
            except discord.Forbidden:
                return await user.send(get_str(ctx, "cmd-ban-failed"))

            await ctx.send("```c\n" + get_str(ctx, "cmd-ban-success").format(user) + f" {ctx.author}.```")
        else:
            await ctx.send(get_str(ctx, "cmd-ban-cancelled"), delete_after=30)

    @commands.command(aliases=['forceban', 'banhack', 'banforce'])
    @commands.guild_only()
    @checks.has_permissions(ban_members=True)
    async def hackban(self, ctx, id: int):
        """
            {command_prefix}hackban [ID]

        {help}
        """
        if not ctx.channel.permissions_for(ctx.me).ban_members:
            return await ctx.send(get_str(ctx, "not-enough-permissions"))
        user = ctx.guild.get_member(id)
        if user:
            return await ctx.invoke(self.ban, user=user)
        confirm_message = await ctx.send(get_str(ctx, "cmd-hackban-confirmation-ban").format(user or id))

        def check(m):
            if m.author.bot or m.author != ctx.author:
                return False
            if m.channel != ctx.channel:
                return False
            if m.content and m.content.lower()[0] in "yn" or m.content.lower().startswith(get_server_prefixes(ctx.bot, ctx.guild)) or m.content.startswith(m.guild.me.mention) or m.content.lower().startswith('exit'):
                return True
            return False

        try:
            response_message = await self.bot.wait_for('message', timeout=30, check=check)
        except asyncio.TimeoutError:
            try:
                await confirm_message.delete()
            except discord.HTTPException:
                pass
            return await ctx.send(get_str(ctx, "cmd-hackban-cancelling-ban"), delete_after=30)

        if response_message.content.lower().startswith('y'):
            if user:
                try:
                    await user.send(get_str(ctx, "cmd-ban-banned").format(ctx.guild.name) + " {0.name}#{0.discriminator}.".format(ctx.author))
                except discord.Forbidden:
                    pass
                try:
                    await ctx.guild.ban(user)
                except discord.Forbidden:
                    return await user.send(get_str(ctx, "cmd-ban-failed"))
                return await ctx.send("```c\n" + get_str(ctx, "cmd-ban-success").format(user) + f" {ctx.author}.```")
            else:
                try:
                    await self.bot.http.ban(id, ctx.guild.id)
                    await ctx.send("```c\n" + get_str(ctx, "cmd-ban-success").format(id) + f" {ctx.author}.```")
                except discord.Forbidden:
                    await user.send(get_str(ctx, "cmd-hackban-failed"))
        else:
            await ctx.send(get_str(ctx, "cmd-hackban-cancelled"), delete_after=30)

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

    @commands.guild_only()
    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.user)
    @commands.group(aliases=["ar", "aar", "autoasignrole", "autoasignroles", "autoroles"], invoke_without_command=True)
    async def autorole(self, ctx, *, role):
        """
            {command_prefix}autorole add [role]
            {command_prefix}autorole remove [role]
            {command_prefix}autorole reset
            {command_prefix}autorole now

        {help}
        """
        if not ctx.invoked_subcommand:
            await ctx.invoke(self.autorole_set, name=role)

    @autorole.command(name="now", aliases=["list", "queue", "current"])
    async def autorole_now(self, ctx):
        """
            {command_prefix}autorole now

        {help}
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        roles = []
        for id in settings.autoroles:
            role = ctx.guild.get_role(id)
            if role:
                roles.append(role.name)
        if not roles:
            return await ctx.send(get_str(ctx, "cmd-autorole-no-autorole"))
        msg = "`{}`".format("`, `".join(roles))
        await ctx.send(get_str(ctx, "cmd-autorole-list-{}".format("roles" if len(settings.autoroles) > 1 else "one-role")).format(msg))

    @checks.has_permissions(manage_guild=True)
    @autorole.command(name="reset", aliases=["off", "delete", "stop", "rien"])
    async def autorole_reset(self, ctx):
        """
            {command_prefix}autorole reset

        {help}
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        settings.autoroles = []
        await SettingsDB.get_instance().set_guild_settings(settings)
        await ctx.send(get_str(ctx, "cmd-autorole-all-removed"))

    @checks.has_permissions(manage_guild=True)
    @autorole.command(name="set", aliases=["add", "+", "are", "config"])
    async def autorole_set(self, ctx, *, name):
        """
            {command_prefix}autorole add [role]

        {help}
        """
        role = self.bot.get_role(ctx, name)

        if not role:
            return await ctx.send(get_str(ctx, "cmd-joinclan-role-not-found").format(name))
        if role.position >= ctx.author.top_role.position and ctx.author.id != owner_id and not ctx.author is ctx.guild.owner:
            return await ctx.send(get_str(ctx, "role-not-enough-high"))
        if role.position >= ctx.me.top_role.position:
            return await ctx.send(get_str(ctx, "not-enough-permissions"))

        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        if role.id not in settings.autoroles:
            settings.autoroles.append(role.id)
        roles = []
        for id in settings.autoroles:
            role = ctx.guild.get_role(id)
            if role:
                roles.append(role.name)
        await SettingsDB.get_instance().set_guild_settings(settings)
        msg = "`{}`".format("`, `".join(roles))
        await ctx.send(get_str(ctx, "cmd-autorole-updated-{}".format("roles" if len(settings.autoroles) > 1 else "one-role")).format(msg))

    @checks.has_permissions(manage_guild=True)
    @autorole.command(name="remove", aliases=["-"])
    async def autorole_remove(self, ctx, *, name):
        """
            {command_prefix}autorole remove [role]

        {help}
        """
        role = self.bot.get_role(ctx, name)

        if not role:
            return await ctx.send(get_str(ctx, "cmd-joinclan-role-not-found").format(name))

        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        if role.id in settings.autoroles:
            settings.autoroles.remove(role.id)
        roles = []
        for id in settings.autoroles:
            role = ctx.guild.get_role(id)
            if role:
                roles.append(role.name)
        await SettingsDB.get_instance().set_guild_settings(settings)
        if not roles:
            return await ctx.send(get_str(ctx, "cmd-autorole-all-removed"))
        msg = "`{}`".format("`, `".join(roles))
        await ctx.send(get_str(ctx, "cmd-autorole-updated-{}".format("roles" if len(settings.autoroles) > 1 else "one-role")).format(msg))

    @commands.command(aliases=["removeclan", "leaveclan", "jclan", "lclan"])
    @commands.guild_only()
    async def joinclan(self, ctx, *, name):
        """
            {command_prefix}joinclan [role]

        {help}
        """
        role = self.bot.get_role(ctx, name)

        if not role:
            return await ctx.send(get_str(ctx, "cmd-joinclan-role-not-found").format(name))

        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        if not settings.clans:
            return await ctx.send(get_str(ctx, "cmd-joinclan-no-clans-available").format("`{}clan create`.".format(get_server_prefixes(ctx.bot, ctx.guild))))
        if role.id not in settings.clans:
            return await ctx.send(get_str(ctx, "cmd-joinclan-cant-be-given").format("`{}clan create`.".format(get_server_prefixes(ctx.bot, ctx.guild))))
        if role in ctx.author.roles:
            await ctx.author.remove_roles(role)
            return await ctx.send(get_str(ctx, "cmd-giverole-remove").format(f"`{role}`", f"**{ctx.author}**"))
        if [r for r in ctx.author.roles if r.id in settings.clans]:
            return await ctx.send(get_str(ctx, "cmd-joinclan-already-have-clan"))
        else:
            try:
                await ctx.author.add_roles(role)
                try:
                    await ctx.message.add_reaction("☑")
                except discord.Forbidden:
                    await ctx.send(get_str(ctx, "cmd-joinclan-success").format(role))
            except discord.Forbidden:
                await ctx.send(get_str(ctx, "not-enough-permissions"))

    @commands.guild_only()
    @commands.group(aliases=["clans"])
    async def clan(self, ctx):
        """
            {command_prefix}clan create [role_name]
            {command_prefix}clan delete [role_name]
            {command_prefix}clan list

        {help}
        """
        if not ctx.invoked_subcommand:
            await ctx.send(get_str(ctx, "command-invalid-usage").format("{}help clan".format(get_server_prefixes(ctx.bot, ctx.guild))))

    @checks.has_permissions(manage_guild=True)
    @clan.command(name="add", aliases=["+", "new", "create"])
    async def __add(self, ctx, *, name):
        """
            {command_prefix}clan create [role_name]

        {help}
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        role = self.bot.get_role(ctx, name)
        if not role:
            return await ctx.send(get_str(ctx, "cmd-joinclan-role-not-found").format(name))
        if role.id not in settings.clans:
            settings.clans.append(role.id)
            await SettingsDB.get_instance().set_guild_settings(settings)
            await ctx.send(get_str(ctx, "cmd-clan-create-success"))
        else:
            await ctx.send(get_str(ctx, "cmd-clan-create-already-exist"))

    @checks.has_permissions(manage_guild=True)
    @clan.command(name="delete", aliases=["remove", "-"])
    async def __delete(self, ctx, *, name):
        """
            {command_prefix}clan delete [role_name]

        {help}
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        role = self.bot.get_role(ctx, name)
        if not role:
            return await ctx.send(get_str(ctx, "cmd-joinclan-role-not-found").format(name))
        if settings.clans:
            if role.id in settings.clans:
                settings.clans.remove(role.id)
                await SettingsDB.get_instance().set_guild_settings(settings)
                await ctx.send(get_str(ctx, "cmd-clan-delete-success"))
            else:
                await ctx.send(get_str(ctx, "cmd-clan-not-existing"))
        else:
            await ctx.send(get_str(ctx, "cmd-joinclan-no-clans-available").format("`{}clan create`.".format(get_server_prefixes(ctx.bot, ctx.guild))))

    @clan.command(name="list", aliases=["all", "view"])
    async def __list(self, ctx):
        """
            {command_prefix}clan list

        {help}
        """
        n = 0
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        msg = [get_str(ctx, "cmd-clan-list")]
        if settings.clans:
            for clan in settings.clans:
                role = self.bot.get_role(ctx, clan)
                if not role:
                    settings.clans.remove(clan)
                    await SettingsDB.get_instance().set_guild_settings(settings)
                    continue
                n += 1
                msg.append("``{}`` {}\n".format(n, role.name))
            if len(msg) == 1:
                return await ctx.send(get_str(ctx, "cmd-clan-no-clans").format("{}clan add".format(get_server_prefixes(ctx.bot, ctx.guild))))
            to_send = ""
            for line in msg:
                if len(to_send) + len(line) > 1980:  # TODO find a better way to do this
                    await ctx.send(to_send)          # This is ugly
                    to_send = ""
                to_send += line

            if to_send:
                await ctx.send(to_send)
        else:
            await ctx.send(get_str(ctx, "cmd-clan-no-clans").format("{}clan add".format(get_server_prefixes(ctx.bot, ctx.guild))))

    @checks.has_permissions(manage_guild=True)
    @commands.command(name="bind", aliases=["djmode", "bound", "boundchannel", "bindchannel", "linkchannel", "ignoreallchannels", "bindmode", "channelbind"])
    async def channel_karaoke(self, ctx, channel: discord.TextChannel = None):
        """
            {command_prefix}bind [channel]
            {command_prefix}bind

        {help}
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        if not channel:
            channel = ctx.channel
        cid = channel.id
        if settings.bound:
            settings.bound = None
            await SettingsDB.get_instance().set_guild_settings(settings)
            await ctx.send(get_str(ctx, "music-bind-disabling"))
        else:
            settings.bound = cid
            await SettingsDB.get_instance().set_guild_settings(settings)
            await ctx.send(get_str(ctx, "music-bind-enabling"))

    @commands.command()
    @commands.is_owner()
    async def gestioneval(self, ctx, *, stmt: str):
        """
            {command_prefix}gestioneval

        Evals something.
        """
        try:
            result = eval(stmt)
            if inspect.isawaitable(result):
                result = await result
        except Exception:
            exc = traceback.format_exc().splitlines()
            result = exc[-1]
        await ctx.channel.send("```py\n--- In ---\n{}\n--- Out ---\n{}\n```".format(stmt, result))

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        settings = await SettingsDB.get_instance().get_guild_settings(guild.id)
        if settings.language != "english":
            return

        e = discord.Embed()
        e.color = int("FF015B", 16)
        e.set_thumbnail(url=self.bot.user.avatar_url)
        msg = f"Hi, I'm **{self.bot.user.name}**, thanks for adding me to your server !\n\nI'm currently \
            in English, but __I can speak in many other languages__.\n\n\
            Use **`{settings.prefix}help lang`** to display help about how to change my language.\n\
            Use **`{settings.prefix}permsinfo`** to display informations about my permissions.\n\
            Use **`{settings.prefix}help`** to display my command list.\n\n\
            **__Here's some useful links :__**\n\n\
            My [**Patreon**](https://patreon.com/watora)\n\
            My [**Support Server**](https://discord.gg/ArJgTpM)\n\
            My [**Website**](https://watora.xyz)\n\
            My [**GitHub**](https://github.com/Zenrac/watora-translations)"
        e.set_footer(text=f"You're my {self.bot.guild_count}th guild!")
        e.description = msg
        channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)
                    and c.permissions_for(guild.me).send_messages
                    and c.permissions_for(guild.me).embed_links]

        better_channels = [bc for bc in channels if 'bot' in bc.name.lower()]
        for channel in better_channels:
            return await channel.send(embed=e)
        for channel in channels:
            return await channel.send(embed=e)


def setup(bot):
    bot.add_cog(Gestion(bot))
