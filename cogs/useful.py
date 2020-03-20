import random
import discord
import asyncio
import aiohttp

from time import perf_counter
from utils import checks
from TextToOwO import owo
from textwrap import dedent
from utils.db import SettingsDB
from discord.ext import commands
from datetime import datetime
from collections import Counter, OrderedDict
from utils.watora import globprefix, log, owner_id, ver, get_uptime, get_server_prefixes, is_basicpatron, is_patron, is_lover, get_str, sweet_bar, format_mentions, get_image_from_url
from cogs.gestion import cmd_help_msg as cmds


class Useful(commands.Cog):
    """The useful cog"""

    def __init__(self, bot):
        self.bot = bot
        self.next_cost = ['80.00', '90.00', '105.00', '120.00', '150.00']

    @commands.cooldown(rate=1, per=5.0, type=commands.BucketType.user)
    @commands.command(name="marry", aliases=["married", "mary", "mariage", "epouse", "epouser"])
    async def _marry(self, ctx, *, user: discord.Member = None):
        """
            {command_prefix}marry [user]

        {help}
        """
        husband_role_id = 501330901653782558

        settings = await SettingsDB.get_instance().get_glob_settings()
        embed = discord.Embed()
        embed.color = 0xFF0000

        if user == ctx.author:
            return await ctx.send(get_str(ctx, "cmd-weeb-alone"))
        if user == ctx.me:
            if ctx.guild:
                ids = [r.id for r in ctx.author.roles]
                if husband_role_id in ids:  # Watora's Husband can marry Watora
                    embed.title = "❤ " + get_str(ctx, "cmd-marry-happily")
                    embed.description = get_str(
                        ctx, "cmd-marry-success").format(f"**{ctx.author.name}**", f"**{user.name}**")
                    await ctx.send(embed=embed)
                    if str(user.id) in settings.marry:
                        before = settings.marry[str(user.id)]['id']
                        del settings.marry[before]  # Watora divorces before

                    date = datetime.today().strftime("%d %b %Y")

                    settings.marry[str(ctx.author.id)] = {}
                    settings.marry[str(ctx.author.id)]['id'] = str(user.id)
                    settings.marry[str(ctx.author.id)]['date'] = date
                    # stock the name in case of a day where the user is not on any bot servers anymore.
                    settings.marry[str(ctx.author.id)]['name'] = user.name

                    settings.marry[str(user.id)] = {}
                    settings.marry[str(user.id)]['id'] = str(ctx.author.id)
                    settings.marry[str(user.id)]['date'] = date
                    # stock the name in case of a day where the user is not on any bot servers anymore.
                    settings.marry[str(user.id)]['name'] = ctx.author.name

                    await SettingsDB.get_instance().set_glob_settings(settings)
                    return

            if not await is_lover(self.bot, ctx.author):
                return await ctx.send(get_str(ctx, "cmd-weeb-dont-touch-me"))
            else:
                return await ctx.send(get_str(ctx, "cmd-marry-too-young") + " {}".format("<:WatoraHyperBlush:458349268944814080>"))

        if not user:
            if str(ctx.author.id) in settings.marry:
                embed.title = "❤ {} ({})".format(get_str(ctx, "cmd-marry-married-to").format(
                    await self.bot.safe_fetch('user', int(settings.marry[str(ctx.author.id)]["id"]))
                    or settings.marry[str(ctx.author.id)]['name']),
                    settings.marry[str(ctx.author.id)]['date'])
                try:
                    return await ctx.send(embed=embed)
                except discord.Forbidden:
                    return await ctx.send(get_str(ctx, "need-embed-permission"), delete_after=20)
            else:
                return await self.bot.send_cmd_help(ctx)

        embed.title = "💍 " + \
            get_str(ctx, "cmd-marry-proposed").format(ctx.author.name, user.name)

        if str(user.id) in settings.marry:
            married_with = (await self.bot.safe_fetch('user', int(settings.marry[str(user.id)]['id']))
                            or settings.marry[str(user.id)]['name'])
            married_since = settings.marry[str(user.id)]['date']
            embed.description = "{} ({})".format(get_str(
                ctx, "cmd-marry-user-a-married").format(user.name, married_with), married_since)
            if married_with == ctx.author:
                embed.description = get_str(ctx, "cmd-marry-a-together")
            try:
                return await ctx.send(embed=embed)
            except discord.Forbidden:
                return await ctx.send(get_str(ctx, "need-embed-permission"), delete_after=20)
        elif str(ctx.author.id) in settings.marry:
            embed.description = get_str(ctx, "cmd-marry-author-a-married").format(
                "`{}divorce`".format(get_server_prefixes(ctx.bot, ctx.guild)))
            try:
                return await ctx.send(embed=embed)
            except discord.Forbidden:
                return await ctx.send(get_str(ctx, "need-embed-permission"), delete_after=20)
        embed.description = get_str(
            ctx, "cmd-marry-confirmation").format("`yes`", "`no`")
        confirm_message = await ctx.send(embed=embed)

        def check(m):
            if m.author.bot or m.author != user:
                return False
            if m.channel != ctx.channel:
                return False
            if m.content:
                return True
            return False

        try:
            response_message = await self.bot.wait_for('message', timeout=120, check=check)
        except asyncio.TimeoutError:
            try:
                await confirm_message.delete()
            except discord.HTTPException:
                pass
            return

        if response_message.author == ctx.author:
            try:
                await confirm_message.delete()
            except discord.HTTPException:
                pass
            return

        if response_message.content.lower().startswith('y'):
            if str(user.id) in settings.marry:  # 2nd check if it changed since the command call
                married_with = (await self.bot.safe_fetch('user', int(settings.marry[str(user.id)]['id']))
                                or settings.marry[str(user.id)]['name'])
                embed.description = get_str(
                    ctx, "cmd-marry-user-a-married").format(user.name, married_with)
                if married_with == ctx.author:
                    embed.description = get_str(ctx, "cmd-marry-a-together")
                try:
                    return await ctx.send(embed=embed)
                except discord.Forbidden:
                    return await ctx.send(get_str(ctx, "need-embed-permission"), delete_after=20)
            elif str(ctx.author.id) in settings.marry:
                embed.description = get_str(ctx, "cmd-marry-author-a-married").format(
                    "`{}divorce`".format(get_server_prefixes(ctx.bot, ctx.guild)))
                try:
                    return await ctx.send(embed=embed)
                except discord.Forbidden:
                    return await ctx.send(get_str(ctx, "need-embed-permission"), delete_after=20)

            embed.title = "❤ " + get_str(ctx, "cmd-marry-happily")
            embed.description = get_str(
                ctx, "cmd-marry-success").format(f"**{ctx.author.name}**", f"**{user.name}**")
            await ctx.send(embed=embed)

            date = datetime.today().strftime("%d %b %Y")

            settings.marry[str(ctx.author.id)] = {}
            settings.marry[str(ctx.author.id)]['id'] = str(user.id)
            settings.marry[str(ctx.author.id)]['date'] = date
            # stock the name in case of a day where the user is not on any bot servers anymore.
            settings.marry[str(ctx.author.id)]['name'] = user.name

            settings.marry[str(user.id)] = {}
            settings.marry[str(user.id)]['id'] = str(ctx.author.id)
            settings.marry[str(user.id)]['date'] = date
            # stock the name in case of a day where the user is not on any bot servers anymore.
            settings.marry[str(user.id)]['name'] = ctx.author.name

            await SettingsDB.get_instance().set_glob_settings(settings)
        elif response_message.content.lower().startswith('n'):
            await ctx.send(get_str(ctx, "cmd-marry-declined").format(ctx.author.mention) + " <:WatoraDisappointed:458349267715883060>", delete_after=30)
        else:
            try:
                await confirm_message.delete()
            except discord.HTTPException:
                pass

    @commands.cooldown(rate=1, per=5.0, type=commands.BucketType.user)
    @commands.command(aliases=["divorcer", "divorces", "div", "cancelmarriage"])
    async def divorce(self, ctx):
        """
            {command_prefix}divorce

        {help}
        """
        settings = await SettingsDB.get_instance().get_glob_settings()
        if str(ctx.author.id) not in settings.marry:
            return await ctx.send(get_str(ctx, "cmd-divorce-a-single") + " <:WatoraDisappointed:458349267715883060>")
        married = settings.marry[str(ctx.author.id)]
        married_since = married['date']
        married_with = await self.bot.safe_fetch('user', int(married["id"])) or married['name']
        datetime_date = datetime.strptime(married_since, '%d %b %Y')
        since_married = (ctx.message.created_at - datetime_date).days
        since_married_full = "{} ({})".format(f"**{married_since}**", get_str(ctx, "cmd-userinfo-days-ago").format(
            since_married) if since_married > 1 else get_str(ctx, "cmd-userinfo-day-ago").format(since_married))

        confirm_message = await ctx.send(get_str(ctx, "cmd-divorce-confirmation").format(f"`{married_with}`", since_married_full, "`yes`", "`no`"))

        def check(m):
            if m.author.bot or m.author != ctx.author:
                return False
            if m.channel != ctx.channel:
                return False
            if m.content:
                return True
            return False

        try:
            response_message = await self.bot.wait_for('message', timeout=120, check=check)
        except asyncio.TimeoutError:
            try:
                await confirm_message.delete()
            except discord.HTTPException:
                pass
            return await ctx.send(get_str(ctx, "cmd-divorce-cancelled"), delete_after=30)

        if response_message.content.lower().startswith('y'):
            del settings.marry[str(ctx.author.id)]
            try:
                del settings.marry[married['id']]
            except KeyError:
                log.error(
                    f"ERROR: {settings.marry[married['id']]} seems to not be married with {settings.marry[str(ctx.author.id)]} but they just divorce")
            await SettingsDB.get_instance().set_glob_settings(settings)

            await ctx.send("☑ " + get_str(ctx, "cmd-divorce-success"))
        else:
            await ctx.send(get_str(ctx, "cmd-divorce-cancelled"), delete_after=30)

    @commands.command(aliases=["aide", "command", "commands", "h"])
    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.user)
    async def help(self, ctx, *, command: str = None):
        """
            {command_prefix}help [command]
            {command_prefix}help [category]
            {command_prefix}help

        {help}
        """
        if command:
            command = command.strip('[]')
            if command.lower() in cmds:
                msg = "```apache\n"
                a = 0
                for cmd in cmds[command.lower()]:
                    if len(cmd) > a:
                        a = len(cmd)
                for cmd in cmds[command.lower()]:
                    if len(cmd) < a:
                        for n in range(a - len(cmd)):
                            msg += " "
                    help = get_str(ctx, f"cmd-{cmd}-help").split("\n")[0]
                    msg += "{} : {}\n".format(cmd, help)
                msg += "```"
                return await ctx.send(msg)

            if command.startswith(get_server_prefixes(ctx.bot, ctx.guild)):
                command = command[len(
                    get_server_prefixes(ctx.bot, ctx.guild)):]
            if not self.bot.get_command(command):
                return await ctx.send(get_str(ctx, "cmd-help-cmd-not-found").format(f"`{command}`"))

            else:
                result = self.bot.get_command(command)
                await self.bot.send_cmd_help(ctx, result)

        else:
            embed = discord.Embed()
            embed.set_author(name=get_str(ctx, "cmd-help-title"),
                             url="https://docs.watora.xyz/commands/music", icon_url=self.bot.user.avatar_url)
            if not ctx.guild:
                embed.color = 0x71368a
            else:
                embed.color = ctx.me.color
            embed.description = get_str(ctx, "cmd-help-description") + "\n" + get_str(
                ctx, "cmd-help-support").format('[**World of Watora**](https://discord.gg/ArJgTpM).\n**__**')
            if ctx.guild:
                settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
                is_admin = ctx.channel.permissions_for(ctx.author).manage_guild
                disabled = []
                if str(ctx.channel.id) in settings.disabledchannels:
                    disabled = settings.disabledchannels[str(ctx.channel.id)]
            for key in cmds:
                try:
                    title = key[0].upper() + key[1:]
                    descrip = '**,** '.join([f"`{cm}`" for cm in cmds[key] if not ctx.guild or is_admin or (
                        (cm.lower() not in settings.disabledcommands) and (cm.lower() not in disabled))])
                    if descrip:
                        embed.add_field(
                            name=f'{title} ({len(cmds[key])})', value=descrip, inline=False)
                except KeyError:
                    pass
            embed.add_field(name="__", value=get_str(ctx, "cmd-help-more-info-cmd") + " **`{}help [command]`**".format(get_server_prefixes(
                ctx.bot, ctx.guild)) + "\n" + get_str(ctx, "cmd-help-more-info-cat") + " **`{}help [category]`**".format(get_server_prefixes(ctx.bot, ctx.guild)))
            try:
                await ctx.send(embed=embed)
            except discord.Forbidden:
                await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.command(aliases=['botinfo', 'infobot'])
    @commands.cooldown(rate=1, per=5.0, type=commands.BucketType.user)
    async def stats(self, ctx):
        """
            {command_prefix}stats

        {help}
        """
        settings = await SettingsDB.get_instance().get_glob_settings()
        # users = len(set(self.bot.get_all_members()))  # set removes duplicate # BLOCKING CODE FFS
        servers = self.bot.guild_count
        # channels = len([c for c in self.bot.get_all_channels()]) # BLOCKING CODE FFS
        embed = discord.Embed()
        owner = await self.bot.safe_fetch('user', owner_id) or str(owner_id)
        embed.set_author(name=f"{self.bot.user.name} v{ver}",
                         icon_url=self.bot.user.avatar_url)
        if isinstance(ctx.channel, discord.abc.GuildChannel):
            embed.color = ctx.guild.me.color
        # embed.add_field(name="Version", value=ver, inline=False)
        embed.add_field(name="Library", value="Discord.py v{}".format(
            str(discord.__version__)), inline=False)
        embed.add_field(name="Uptime", value=str(get_uptime()))
        embed.add_field(name="Guild{}".format(
            "s" if servers > 1 else ""), value=servers)
        # embed.add_field(name="Channels", value=channels)
        embed.add_field(name="Shard{}".format(
            "s" if self.bot.shard_count > 1 else ""), value=self.bot.shard_count)
        # embed.add_field(name="Users", value=users)
        embed.add_field(name="Owner", value=owner)
        embed.add_field(name="Commands", value=len(self.bot.commands))
        embed.add_field(name="Autoplaylists",
                        value=len(settings.autoplaylists))
        embed.add_field(name="Donation",
                        value="[PayPal](https://www.paypal.me/watora)\n[Patreon](https://www.patreon.com/watora)")
        embed.add_field(
            name="Info", value="[Website](https://watora.xyz/)\n[FAQ](https://docs.watora.xyz/faq)")
        embed.add_field(
            name="Social", value="[Discord](https://discordapp.com/invite/ArJgTpM)\n[Twitter](https://twitter.com/watorabot)")
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.command()
    @commands.cooldown(rate=1, per=1.0, type=commands.BucketType.user)
    async def ping(self, ctx):
        """
            {command_prefix}ping

        {help}
        """
        embed = discord.Embed()
        if isinstance(ctx.channel, discord.abc.GuildChannel):
            embed.color = ctx.guild.me.color
        embed.set_author(
            name="Pong!", icon_url="https://cdn.discordapp.com/attachments/268495024801447936/349241478750404609/dmOYQuS.png")
        start = perf_counter()
        await ctx.channel.trigger_typing()
        end = perf_counter()
        embed.description = "%s ms!" % int((end - start) * 1000)
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            return await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.command()
    @commands.cooldown(rate=1, per=1.0, type=commands.BucketType.user)
    async def pong(self, ctx):
        """
            {command_prefix}pong

        Wut ? Did you just find an easter eggs ?
        """
        await ctx.send("<:WatoraLost:458349268621721601>")

    @commands.command()
    @commands.cooldown(rate=1, per=1.0, type=commands.BucketType.user)
    @commands.guild_only()
    async def shard(self, ctx):
        """
            {command_prefix}shard

        {help}
        """
        await ctx.send(get_str(ctx, "cmd-shard").format(f"`{ctx.guild.shard_id}`"))

    @commands.cooldown(rate=1, per=3, type=commands.BucketType.user)
    @commands.command(aliases=["votes", "upvote", "upvotes"])
    async def vote(self, ctx, user: discord.Member = None):
        """
            {command_prefix}vote

        Allows to upvote Watora on some bot lists.
        """
        if not user:
            user = ctx.author
        e = discord.Embed()
        if 'Update' in self.bot.cogs:
            msg = ""
            asyncio.ensure_future(self.bot.cogs['Update'].update())
            votes = self.bot.cogs['Update'].votes
            counter = Counter(k['id'] for k in votes if k.get('id'))
            counter = OrderedDict(counter.most_common())
            top5 = []
            for i, id in enumerate(counter, start=1):
                if i > 5:
                    break
                top5.append(id)
                member = await self.bot.safe_fetch('user', int(id)) or id
                msg += f"`{i}` **{member}** : **{counter[id]}** vote{'s' if counter[id] > 1 else ''}\n"
            month = datetime.now().strftime("%B")
            if str(user.id) not in top5:
                if str(user.id) in counter:
                    pos = list(counter).index(str(user.id)) + 1
                    nb = counter[str(user.id)]
                    if pos == 6:
                        msg += f"`{pos}` **{user}** : **{nb}** vote{'s' if nb > 1 else ''}\n"
                    else:
                        e.set_footer(
                            text=f"{pos} - {user} : {nb} vote{'s' if nb > 1 else ''}", icon_url=user.avatar_url)
        if isinstance(ctx.channel, discord.abc.GuildChannel):
            e.color = ctx.guild.me.color
        e.set_thumbnail(url=self.bot.user.avatar_url)
        e.set_author(
            name=f"Top Voters of {month}:", url=f"https://discordbots.org/bot/{self.bot.user.id}/vote")
        e.description = f"{msg}\n**[Vote for {self.bot.user.name} on Discord Bot List](https://discordbots.org/bot/{self.bot.user.id}/vote)**"

        try:
            await ctx.send(embed=e)
        except discord.Forbidden:
            return await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    @commands.command(aliases=["sayd", "say", "watora", "talk", "write", "med"])
    async def me(self, ctx, *, content=None):
        """
            {command_prefix}say [content]

        {help}
        """
        if not content or 'd' in ctx.invoked_with.lower():
            ctx.command.reset_cooldown(ctx)
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass
            return  # just delete the message and go away

        ctx.command.reset_cooldown(ctx)
        content = await self.bot.format_cc(content, ctx.message)
        content = format_mentions(content)
        pic = get_image_from_url(content)
        if pic:
            e = discord.Embed()
            e.set_image(url=pic)
            content = content.replace(pic, '')
            if self.bot.owo_map.get(ctx.guild.id, False):
                content = owo.text_to_owo(content)
            try:
                return await ctx.send(embed=e, content=content)
            except discord.Forbidden:
                return await ctx.send(get_str(ctx, "need-embed-permission"))

        if self.bot.owo_map.get(ctx.guild.id, False):
            content = owo.text_to_owo(content)
        await ctx.send(content)

    @commands.command()
    @commands.cooldown(rate=1, per=1.0, type=commands.BucketType.user)
    async def avatar(self, ctx, *, user: discord.Member = None):
        """
            {command_prefix}avatar [user]
            {command_prefix}avatar

        {help}
        """
        if not user:
            user = ctx.author
        embed = discord.Embed()
        if not isinstance(ctx.channel, discord.abc.PrivateChannel):
            embed.colour = user.colour
        if user == self.bot.user:
            embed.set_author(name=get_str(ctx, "cmd-avatar-my-avatar"))
        else:
            if ctx.author == user:
                embed.set_author(name=get_str(ctx, "cmd-avatar-your-avatar"))
            else:
                if ctx.guild:
                    settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
                    if settings.language == "french":
                        embed.set_author(name=get_str(ctx, "cmd-avatar-someone-avatar")
                                         .format("'" if user.name.lower()[0] in ["a", "e", "i", "u", "y", "o"] else "e ", user))
                    else:
                        embed.set_author(name=get_str(
                            ctx, "cmd-avatar-someone-avatar").format(user))

        ava = user.avatar_url
        embed.set_image(url=ava or user.default_avatar_url)
        embed.set_author(name=embed.author.name,
                         url=ava or user.default_avatar_url)  # Hacky
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.guild_only()
    @commands.command(aliases=["infouser", "profile", "ui", "profil", "memberinfo", "infomember", "whois"])
    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    async def userinfo(self, ctx, *, user: discord.Member = None):
        """
            {command_prefix}userinfo [user]
            {command_prefix}userinfo

        {help}
        """
        if not user:
            user = ctx.author

        # shared = sum([1 for m in self.bot.get_all_members() if m.id == user.id])

        if user.voice:
            other_people = len(user.voice.channel .members) - 1
            voice_fmt = '%s' % (get_str(ctx, "cmd-userinfo-voice-members") if other_people > 1 else get_str(
                ctx, "cmd-userinfo-voice-member")) if other_people else get_str(ctx, "cmd-userinfo-voice-alone")
            voice = voice_fmt.format(user.voice.channel.name, other_people)
        else:
            voice = get_str(ctx, "cmd-userinfo-not-connected")

        roles = [x.name for x in user.roles if x.name != "@everyone"]

        joined_at = user.joined_at
        since_created = (ctx.message.created_at - user.created_at).days
        try:
            since_joined = (ctx.message.created_at - joined_at).days
        except TypeError:
            since_joined = 0

        user_joined = joined_at.strftime("%d %b %Y %H:%M")
        user_created = user.created_at.strftime("%d %b %Y %H:%M")
        try:
            member_number = sorted(
                ctx.guild.members, key=lambda m: m.joined_at).index(user) + 1
        except TypeError:
            member_number = 0

        created_on = "{}\n(".format(user_created) + "{}".format(get_str(ctx, "cmd-userinfo-days-ago")
                                                                if since_created > 1 else get_str(ctx, "cmd-userinfo-day-ago")).format(since_created) + ")"
        joined_on = "{}\n(".format(user_joined) + "{}".format(get_str(ctx, "cmd-userinfo-days-ago")
                                                              if since_joined > 1 else get_str(ctx, "cmd-userinfo-day-ago")).format(since_joined) + ")"

        game = "{}".format(user.status)
        game = game[0].upper() + game[1:]
        if user.activity:
            if isinstance(user.activity, discord.Spotify):
                game = get_str(
                    ctx, "cmd-userinfo-listening-music").format(user.activity.title, user.activity.artist)
            elif user.activity.type == discord.ActivityType.playing:
                game = get_str(ctx, "cmd-userinfo-playing") + \
                    " {}".format(user.activity.name)
            elif user.activity.type == discord.ActivityType.watching:  # watching
                game = get_str(ctx, "cmd-userinfo-watching") + \
                    " {}".format(user.activity.name)
            elif user.activity.type == discord.ActivityType.streaming:
                game = get_str(ctx, "cmd-userinfo-streaming") + \
                    " [{}]({})".format(user.activity, user.activity.url)

        if roles:
            try:
                roles = sorted(roles, key=[
                               x.name for x in user.guild.roles[::-1] if x.name != "@everyone"].index)
            except ValueError:  # idk
                pass
            nbroles = len(roles)
            roles = ", ".join(roles)
        else:
            roles = "None"
            nbroles = 0

        data = discord.Embed(description=game)
        if not isinstance(ctx.channel, discord.abc.PrivateChannel):
            data.colour = user.colour
        data.add_field(name=get_str(
            ctx, "cmd-userinfo-joined-discord"), value=created_on)
        data.add_field(name=get_str(
            ctx, "cmd-userinfo-joined-guild"), value=joined_on)
        # data.add_field(name="{}".format(get_str(ctx, "cmd-userinfo-servers-shared") if shared > 2 else get_str(ctx, "cmd-userinfo-server-shared")), value=shared)
        data.add_field(name=get_str(ctx, "cmd-userinfo-voice"), value=voice)
        settings = await SettingsDB.get_instance().get_glob_settings()
        if str(user.id) in settings.marry:
            married_with = await self.bot.safe_fetch('user', int(settings.marry[str(user.id)]['id'])) or settings.marry[str(user.id)]['name']
            married_since = settings.marry[str(user.id)]['date']
            data.add_field(name=get_str(ctx, "cmd-userinfo-married-with"),
                           value=f"💕 {married_with} ({married_since})", inline=False)
        data.add_field(name="{}".format(get_str(ctx, "cmd-userinfo-roles") if nbroles >
                                        1 else get_str(ctx, "cmd-userinfo-role")) + " [%s]" % nbroles, value=roles, inline=False)
        data.set_footer(text=get_str(ctx, "cmd-userinfo-member", can_owo=False) + " #{} | ".format(
            member_number) + get_str(ctx, "cmd-userinfo-user-id", can_owo=False) + ":{}".format(user.id))

        name = str(user)
        name = " ~ ".join((name, user.nick)) if user.nick else name

        if user.avatar_url:
            data.set_author(name=name, url=user.avatar_url)
            data.set_thumbnail(url=user.avatar_url)
        else:
            data.set_author(name=name)

        try:
            await ctx.send(embed=data)
        except discord.HTTPException:
            await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.guild_only()
    @commands.command(aliases=["guildinfo", "infoguild", "infoserver", "si", "gi", "sinfo", "ginfo"])
    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    async def serverinfo(self, ctx, *, guild=None):
        """
            {command_prefix}serverinfo

        {help}
        """
        if guild:  # owner can see other's guild informations
            if ctx.author.id == owner_id:
                try:
                    guild = await self.bot.safe_fetch('guild', int(guild))
                except ValueError:
                    return await ctx.send("Guild not found...")
                if not guild:
                    return await ctx.send("Guild not found...")
            else:
                guild = ctx.guild
        else:
            guild = ctx.guild

        online = len([m.status for m in guild.members
                      if m.status == discord.Status.online or
                      m.status == discord.Status.idle or
                      m.status == discord.Status.dnd])
        total_users = len(guild.members)
        total_bot = len([m for m in guild.members if m.bot])
        text_channels = len([x for x in guild.channels
                             if type(x) == discord.TextChannel])
        voice_channels = len([x for x in guild.channels
                              if type(x) == discord.VoiceChannel])
        passed = (ctx.message.created_at - guild.created_at).days
        created_at = get_str(ctx, "cmd-serverinfo-since", can_owo=False).format(
            guild.created_at.strftime("%d %b %Y %H:%M"), passed)

        colour = ''.join([random.choice('0123456789ABCDEF') for x in range(6)])
        colour = int(colour, 16)

        data = discord.Embed(
            description=created_at,
            colour=discord.Colour(value=colour))
        data.add_field(name=get_str(ctx, "cmd-serverinfo-region"),
                       value=str(guild.region))
        data.add_field(name=get_str(ctx, "cmd-serverinfo-users"), value="{}/{} ({} bot{})".format(
            online, total_users, total_bot, 's' if total_bot > 2 else ''))
        data.add_field(name=get_str(
            ctx, "cmd-serverinfo-textchannels"), value=text_channels)
        data.add_field(name=get_str(
            ctx, "cmd-serverinfo-voicechannels"), value=voice_channels)
        data.add_field(name=get_str(ctx, "cmd-serverinfo-roles"),
                       value=len(guild.roles))
        data.add_field(name=get_str(ctx, "cmd-serverinfo-owner"),
                       value=str(guild.owner))
        data.set_footer(text=get_str(
            ctx, "cmd-serverinfo-server-id") + ": " + str(guild.id))
        claimed = await self.bot.server_is_claimed(guild.id)
        if claimed:
            user_id = int(claimed[0])
            claimed = list(claimed[1].items())[0]
            user = await self.bot.safe_fetch('member', user_id, guild=guild) or user_id
            data.add_field(
                name="Patreon Server", value="Claimed by {}. Since {}".format(user, claimed[1]))

        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)

        if settings.defaultnode:
            member = ctx.guild.get_member(int(settings.defaultnode))
            if member:
                # TODO: Translations
                data.add_field(name='Default music node',
                               value=f"Hosted by {member}", inline=False)

        if guild.icon_url:
            data.set_author(name=guild.name, url=guild.icon_url)
            data.set_thumbnail(url=guild.icon_url)
        else:
            data.set_author(name=guild.name)

        try:
            await ctx.send(embed=data)
        except discord.HTTPException:
            await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.guild_only()
    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    @commands.command(aliases=["inforole"])
    async def roleinfo(self, ctx, *, name):
        """
            {command_prefix}roleinfo [role]

        {help}
        """
        role = self.bot.get_role(ctx, name)

        if not role:
            return await ctx.send(get_str(ctx, "cmd-joinclan-role-not-found").format(name))

        role_count = 0
        all_users = []
        for user in ctx.guild.members:
            if role in user.roles:
                all_users.append('{}#{}'.format(user.name, user.discriminator))
                role_count += 1
        all_users.sort()
        all_users = ', '.join(all_users)
        em = discord.Embed(title=role.name, color=role.color)
        em.add_field(name='ID', value=role.id, inline=False)
        em.add_field(name='{}'.format(get_str(ctx, "cmd-roleinfo-users") if role_count >
                                      1 else get_str(ctx, "cmd-roleinfo-user")), value=role_count)
        if str(role.color) != "#000000":
            em.add_field(name=get_str(ctx, "cmd-roleinfo-color"),
                         value=str(role.color))
            em.set_thumbnail(url='http://www.colorhexa.com/%s.png' %
                             str(role.color).strip("#"))
        em.add_field(name=get_str(ctx, "cmd-roleinfo-mentionable"), value=get_str(ctx,
                                                                                  "music-plsettings-yes") if role.mentionable else get_str(ctx, "music-plsettings-no"))
        if 0 < role_count < 16:
            em.add_field(name=get_str(ctx, "cmd-roleinfo-all-users"),
                         value=all_users, inline=False)
        em.add_field(name=get_str(ctx, "cmd-roleinfo-creation"),
                     value=role.created_at.strftime("%Y-%m-%d"))
        if str(role.color) != "#000000":
            em.set_thumbnail(url='http://www.colorhexa.com/%s.png' %
                             str(role.color).strip("#"))
        try:
            await ctx.send(embed=em)
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.cooldown(rate=1, per=1.0, type=commands.BucketType.user)
    @commands.command(aliases=["about"])
    async def info(self, ctx):
        """
            {command_prefix}about

        {help}
        """
        msg = get_str(ctx, "cmd-info")
        try:
            await ctx.author.send(msg)
        except discord.HTTPException:
            return await ctx.send(get_str(ctx, "cant-send-pm"))
        try:
            await ctx.message.add_reaction("☑")
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "message-send-to-mp"))

    @commands.cooldown(rate=1, per=1.0, type=commands.BucketType.user)
    @commands.command(aliases=["cred", "creds", "crds", "crd"])
    async def credits(self, ctx):
        """
            {command_prefix}credits

        {help}
        """
        em = discord.Embed(description=get_str(ctx, "cmd-credits-title"))
        em.add_field(name="Zenrac", value="[{}]({})".format(
            get_str(ctx, "cmd-credits-bot-dev"), "https://github.com/Zenrac"))
        em.add_field(name="Rapptz - Danny", value='[discord.py]({})'.format(
            "https://github.com/Rapptz/discord.py/tree/rewrite"))
        em.add_field(name="Ifran-dahir",
                     value='[Jikan]({})'.format("https://jikan.moe/"))
        em.add_field(name="Sedmelluq", value='[Lavaplayer]({})'.format(
            "https://github.com/sedmelluq/"))
        em.add_field(name="Frederikam", value='[Lavalink]({})'.format(
            "https://github.com/Frederikam/Lavalink"))
        em.add_field(name="Devoxin", value='[Lavalink.py]({})'.format(
            "https://github.com/Devoxin/Lavalink.py"))
        em.add_field(name="Wolke & Akio",
                     value='[weeb.sh API]({})'.format("https://weeb.sh/"))
        em.add_field(name="AndyTempel", value='[weeb.sh Wrapper]({})'.format(
            "https://github.com/AndyTempel/weebapi"))
        em.add_field(name="Dank Memer", value='[Meme-Server]({})'.format(
            "https://github.com/DankMemer/meme-server"))
        em.add_field(name="RickBot IMGGEN", value='[Meme-Server]({})'.format(
            "https://services.is-going-to-rickroll.me/"))
        em.add_field(name="AndyTempel", value='[KSoft.Si API]({})'.format(
            "https://api.ksoft.si/"))
        em.add_field(name="Sworder & Ota",
                     value='[arcadia-api]({})'.format("https://arcadia-api.xyz"))
        em.add_field(name="LazyShpee", value='[iode]({})'.format(
            "https://github.com/LazyShpee"))
        em.add_field(name="Akio", value='[MTCL]({})'.format(
            "https://mctl.io/"))
        em.add_field(name="Peko", value='[{}]({})'.format(
            get_str(ctx, "cmd-credits-watora-designer"), "http://lumino.sakura.ne.jp"))
        em.add_field(name=get_str(ctx, "cmd-current-translation-written-by", can_owo=False),
                     value=get_str(ctx, "cmd-current-translation-author", can_owo=False), inline=False)

        try:
            await ctx.send(embed=em)
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.command(aliases=["patchnotes", "changlogs", "update", "patchnote"])
    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.user)
    async def changelog(self, ctx):
        """
            {command_prefix}changelog

        {help}
        """
        patchchannel = self.bot.get_channel(340263164505620483)
        try:
            if ctx.guild:
                settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
                if settings.language == "french":
                    patchchannel = self.bot.get_channel(268492317164437506)
        except KeyError:
            pass
        if not patchchannel:
            e = discord.Embed(
                description='See all changelogs on my official server!')
            if not ctx.guild:
                e.color = 0x71368a
            else:
                e.color = ctx.me.color
            e.set_thumbnail(url=self.bot.user.avatar_url)
            e.add_field(name='{}:'.format(get_str(ctx, "cmd-invitation-my-server")),
                        value='[World of Watora]({})'.format("https://discord.gg/ArJgTpM"))
            return await ctx.send(embed=e)
        async for lmsg in patchchannel.history(limit=2):
            if lmsg.author.id == owner_id:
                msg = lmsg
                break
        await ctx.send(msg.content)

    @commands.command(aliases=["dons", "donation", "donate", "donating", "donators", "donator"])
    @commands.cooldown(rate=1, per=1.0, type=commands.BucketType.user)
    async def don(self, ctx, *, text=None):
        """
            {command_prefix}don
            {command_prefix}don [text]
            {command_prefix}don off

        {help}
        """
        settings = None
        if text:
            if not await is_basicpatron(self.bot, ctx.author):
                return await ctx.send(embed=discord.Embed(description="Sorry, you have to be Patron to set a custom message!\n\n**[Patreon](https://www.patreon.com/watora)**"))

            settings = await SettingsDB.get_instance().get_glob_settings()

            if 'donators' not in settings.donation:
                settings.donation['donators'] = {}

            if text.lower() in ['stop', 'off', 'disable', 'empty', 'remove']:
                if str(ctx.author.id) in settings.donation['donators']:
                    settings.donation['donators'].pop(str(ctx.author.id))
                    await SettingsDB.get_instance().set_glob_settings(settings)
                    await ctx.send('Message removed!')

            else:
                settings.donation['donators'][str(ctx.author.id)] = text
                await SettingsDB.get_instance().set_glob_settings(settings)
                await ctx.send('Message set!')

        e = discord.Embed().set_footer(text=get_str(
            ctx, "cmd-don-thx-in-advance", can_owo=False))

        try:
            e.colour = ctx.author.colour
        except AttributeError:
            pass
        topdona = pbar = ''
        if not settings:  # Only 1 DB call
            settings = await SettingsDB.get_instance().get_glob_settings()
        if 'top' in settings.donation:
            topdona = settings.donation['top']
        if 'bar' in settings.donation:
            pbar = settings.donation['bar']

        e.description = f"**{datetime.now().strftime('%B %Y')}**"
        e.add_field(name=get_str(ctx, "cmd-don-make-a-donation"), value="[**Paypal**]({})".format(
            "https://www.paypal.me/watora") + "\n[**Patreon**]({})".format("https://www.patreon.com/watora"), inline=False)
        donators = settings.donation.get('donators', {})
        if donators:
            desc = ""
            for k, v in donators.items():
                fetched_member = await is_basicpatron(self.bot, int(k), fetch=True)
                if fetched_member:
                    tier = 2
                    if await is_patron(self.bot, int(k), resp=fetched_member):
                        tier = 5
                        if await is_lover(self.bot, int(k), resp=fetched_member):
                            tier = 10

                    username = fetched_member['user']['username'] + \
                        '#' + fetched_member['user']['discriminator']
                    text = format_mentions(v)[:100]
                    desc += f'`{username}` **${tier}/m** : {text}\n'
            if desc:
                e.add_field(name="Current patrons", value=desc)

        if pbar:
            if "," in pbar:
                pbar = pbar.replace(",", ".")
            prog_bar_str = ''
            pbar = pbar.split("/")
            max_v, min_v = pbar[1], pbar[0]
            max_value = float(pbar[1])
            min_value = float(pbar[0])
            prog_bar_str = sweet_bar(min_value, max_value)
            pbar = "`{}€/{}€` {}".format(min_v, max_v, prog_bar_str)
            e.add_field(name=get_str(
                ctx, "cmd-don-server-cost") + ' :', value=pbar)
            prog_bar_str = ''
            if max_value < min_value:
                max_value = [m for m in self.next_cost if float(m) > max_value]
                if max_value:
                    prog_bar_str = sweet_bar(min_value, float(max_value[0]))
                    pbar = "`{}€/{}€` {}".format(min_v,
                                                 max_value[0], prog_bar_str)
                    e.add_field(name="Upgrade server cost :", value=pbar)
        await ctx.send(embed=e)

    @commands.command(aliases=["infoperms", "permissionsinfo", "infopermissions", "aboutpermissions"])
    @commands.cooldown(rate=1, per=1.0, type=commands.BucketType.user)
    async def permsinfo(self, ctx):
        """
            {command_prefix}permsinfo

        {help}
        """
        msg = get_str(ctx, "cmd-perms-info").format(
            get_server_prefixes(ctx.bot, ctx.guild) if ctx.guild else "=")
        try:
            await ctx.author.send(msg)
        except discord.HTTPException:
            return await ctx.send(get_str(ctx, "cant-send-pm"))
        try:
            await ctx.message.add_reaction("☑")
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "message-send-to-mp"))

    @commands.command()
    @commands.cooldown(rate=1, per=1.0, type=commands.BucketType.user)
    async def id(self, ctx, *, usr: discord.Member = None):
        """
            {command_prefix}id [user]
            {command_prefix}id

        {help}
        """
        if not usr:
            await ctx.send(get_str(ctx, "cmd-id-your-id").format(ctx.author.mention, f"`{ctx.author.id}`"))
        elif usr == self.bot.user:
            await ctx.send(get_str(ctx, "cmd-id-my-id") + f" `{usr.id}`.")
        else:
            try:
                if ctx.guild:
                    settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
                    if settings.language == "french":
                        return await ctx.send(get_str(ctx, "cmd-id-user-id").format("'" if usr.name.lower()[0] in ["a", "e", "i", "u", "y", "o"] else "e ", f"`{usr.name}`", f"`{usr.id}`"))
            except KeyError:
                pass
            await ctx.send(get_str(ctx, "cmd-id-user-id").format(f"`{usr.name}`", f"`{usr.id}`"))

    @commands.command()
    @commands.is_owner()
    async def leaveserver(self, ctx, *, args):
        """
            {command_prefix}leaveserver

        Makes me leave a specified server.
        """
        try:
            target = await self.bot.safe_fetch('guild', int(args))
        except ValueError:
            target = None
        if not target:
            target = discord.utils.get(self.bot.guilds, name=args)
        if not target:
            return await ctx.send("Could not find this guild.")
        await target.leave()
        await ctx.send("I have left **{0.name}**... ({0.id})".format(target))

    @commands.command()
    @commands.is_owner()
    async def pbar(self, ctx, *, bar):
        """
            {command_prefix}pbar

        Sets the progress bar in the donation message.
        """
        settings = await SettingsDB.get_instance().get_glob_settings()
        settings.donation['bar'] = bar
        await SettingsDB.get_instance().set_glob_settings(settings)
        try:
            # try to update status
            await self.bot.cogs['Update'].message_status(bypass=True)
        except KeyError:
            pass
        await ctx.send(":ok_hand:")

    @commands.cooldown(rate=1, per=1.0, type=commands.BucketType.user)
    @commands.command(aliases=["invite", "invitations"])
    async def invitation(self, ctx):
        """
            {command_prefix}invitation

        {help}
        """
        if self.bot.user.bot:
            e = discord.Embed()
            if not ctx.guild:
                e.color = 0x71368a
            else:
                e.color = ctx.me.color
            e.set_thumbnail(url=self.bot.user.avatar_url)
            url = f"https://discordapp.com/api/oauth2/authorize?client_id={self.bot.user.id}&scope=bot"
            if self.bot.user.id == 220644154177355777:
                url += "&redirect_uri=https%3A%2F%2Fwatora.xyz%2F%3Finvited%3Dyes"  # redirect uri
            e.add_field(name='{}:'.format(get_str(ctx, "cmd-invitation-add-me")),
                        value='[{}]({})'.format(get_str(ctx, "cmd-invitation"), url), inline=False)
            e.add_field(name='{}:'.format(get_str(ctx, "cmd-invitation-my-server")),
                        value='[World of Watora]({})'.format("https://discord.gg/ArJgTpM"))
            await ctx.send(embed=e)

    @commands.cooldown(rate=1, per=600.0, type=commands.BucketType.user)
    @commands.command(aliases=["suggest", "idea"])
    async def suggestion(self, ctx, *, content):
        """
            {command_prefix}suggestion [text]

        {help}
        """
        if len(content.split(" ")) < 6 and not await is_basicpatron(self.bot, ctx.author):
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(get_str(ctx, "cmd-suggestion-useless"))

        e = discord.Embed(title='Suggestion', colour=0x738bd7)
        msg = ctx.message

        channel = 268495043235545088

        e.set_author(name=str(
            msg.author), icon_url=msg.author.avatar_url or msg.author.default_avatar_url)
        e.description = content
        e.timestamp = msg.created_at

        if msg.guild:
            e.add_field(name='Server', value='{0.name} (ID: {0.id})'.format(
                msg.guild), inline=False)

        e.add_field(name='Channel', value='{0} (ID: {0.id})'.format(
            msg.channel), inline=False)
        e.set_footer(text='Author ID: ' + str(msg.author.id))

        confirm_message = await ctx.send("Your suggestion **about Watora** is going to be sent to Watora's developper. Are you sure about that ?\nWrite `yes` or `no`.\n```diff\n- Warning: Any kind of abuse will make your account blacklisted from the bot (it means that you'll not be able to use Watora anymore).\n+ Please only write it in ENGLISH (or french...)```")

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
            ctx.command.reset_cooldown(ctx)
            return await ctx.send("Suggestion cancelled.", delete_after=30)
        if response_message.content.lower().startswith('y'):
            smsg = await self.bot.http.send_message(channel, content='', embed=e.to_dict())
            msg_id = smsg['id']
            await self.bot.http.add_reaction(channel, msg_id, "☑")
            await self.bot.http.add_reaction(channel, msg_id, "❌")
            await ctx.send(get_str(ctx, "cmd-suggestion-sent") + " :mailbox_with_mail:")
        else:
            ctx.command.reset_cooldown(ctx)
            await ctx.send("Suggestion cancelled.", delete_after=30)

    @commands.cooldown(rate=1, per=600.0, type=commands.BucketType.user)
    @commands.command(aliases=["problem"])
    async def bug(self, ctx, *, content):
        """
            {command_prefix}bug [text]

        {help}
        """
        if len(content.split(" ")) < 6 and not await is_basicpatron(self.bot, ctx.author):
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(get_str(ctx, "cmd-bug-useless"))

        e = discord.Embed(title='Bug', colour=0x723be7)
        msg = ctx.message

        channel = 268495081202384896

        e.set_author(name=str(
            msg.author), icon_url=msg.author.avatar_url or msg.author.default_avatar_url)
        e.description = content
        e.timestamp = msg.created_at

        if msg.guild:
            e.add_field(name='Server', value='{0.name} (ID: {0.id})'.format(
                msg.guild), inline=False)

        e.add_field(name='Channel', value='{0} (ID: {0.id})'.format(
            msg.channel), inline=False)
        e.set_footer(text='Author ID: ' + str(msg.author.id))

        confirm_message = await ctx.send("Your bug report **about Watora** is going to be sent to Watora's developper. Are you sure about that ?\nWrite `yes` or `no`.\n```diff\n- Warning: Any kind of abuse will make your account blacklisted from the bot (it means that you'll not be able to use Watora anymore).\n+ Please only write it in ENGLISH (or french...)```")

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
            ctx.command.reset_cooldown(ctx)
            return await ctx.send("Report cancelled.", delete_after=30)
        if response_message.content.lower().startswith('y'):
            smsg = await self.bot.http.send_message(channel, content='', embed=e.to_dict())
            await ctx.send(get_str(ctx, "cmd-bug-sent") + " :mailbox_with_mail:")
        else:
            ctx.command.reset_cooldown(ctx)
            await ctx.send("Report cancelled.", delete_after=30)

    @commands.cooldown(rate=1, per=600.0, type=commands.BucketType.user)
    @commands.command(aliases=["avis"])
    async def feedback(self, ctx, *, content):
        """
            {command_prefix}feedback [text]

        {help}
        """
        if len(content.split(" ")) < 6 and not await is_basicpatron(self.bot, ctx.author):
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(get_str(ctx, "cmd-feedback-useless"))

        e = discord.Embed(title='Feedback', colour=0x2ecc71)
        msg = ctx.message

        channel = 346251537217093632

        e.set_author(name=str(
            msg.author), icon_url=msg.author.avatar_url or msg.author.default_avatar_url)
        e.description = content
        e.timestamp = msg.created_at

        if msg.guild:
            e.add_field(name='Server', value='{0.name} (ID: {0.id})'.format(
                msg.guild), inline=False)

        e.add_field(name='Channel', value='{0} (ID: {0.id})'.format(
            msg.channel), inline=False)
        e.set_footer(text='Author ID: ' + str(msg.author.id))

        confirm_message = await ctx.send("Your feedback **about Watora** is going to be sent to Watora's developper. Are you sure about that ?\nWrite `yes` or `no`.\n```diff\n- Warning: Any kind of abuse will make your account blacklisted from the bot (it means that you'll not be able to use Watora anymore).\n+ Please only write it in ENGLISH (or french...)```")

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
            ctx.command.reset_cooldown(ctx)
            return await ctx.send("Feedback cancelled.", delete_after=30)
        if response_message.content.lower().startswith('y'):
            smsg = await self.bot.http.send_message(channel, content='', embed=e.to_dict())
            await ctx.send(get_str(ctx, "cmd-feedback-sent") + " :mailbox_with_mail:")
        else:
            ctx.command.reset_cooldown(ctx)
            await ctx.send("Feedback cancelled.", delete_after=30)

    @commands.command(aliases=["ver"])
    async def version(self, ctx):
        """
            {command_prefix}ver

        {help}
        """
        await ctx.send(get_str(ctx, "cmd-ver-current") + f" **{ver}**.")

    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    @commands.command(aliases=["infoshards", "shardinfo", "shardsinfo", "status", "shardstatus", "shardsstatus"])
    async def infoshard(self, ctx):
        """
            {command_prefix}infoshard

        {help}
        """
        nshards = len(self.bot.shards)
        msg = "```xl\nCurrently on {} shard{} with {} guilds (all: {}).\n\n".format(
            nshards, "s" if nshards > 1 else "", len(self.bot.guilds), self.bot.guild_count)
        for i, n in enumerate(list(self.bot.shards.keys())):
            gshard = 0
            for s in self.bot.guilds:
                if s.shard_id == n:
                    gshard += 1
            msg += f"[{n}] : {gshard} guilds. (latency : {(round([shard[1] for shard in self.bot.latencies][i], 2))*1000} ms)\n"

        msg += "```"
        await ctx.send(msg)

    @commands.cooldown(rate=1, per=10.0, type=commands.BucketType.user)
    @commands.command(aliases=["langinfo", "infolang"])
    async def infolangages(self, ctx):
        """
            {command_prefix}infolangages

        Where there are the most ppl using Watora ?
        """
        c = Counter(x.region for x in self.bot.guilds)
        msg = "```xl\nCurrently on {} guild{} (all: {}).\n\n".format(len(
            self.bot.guilds), "s" if len(self.bot.guilds) > 1 else "", self.bot.guild_count)
        for (x, y) in c.most_common():
            msg += f"[{x}] : {y}\n"
        msg += "```"
        await ctx.send(msg)

    @commands.is_owner()
    @commands.command(aliases=["whereis", "whatserver"])
    async def whereare(self, ctx, *, id: int):
        """
            {command_prefix}whereare

        Displays the list of server someone is with me.
        """
        n = 1985
        servers = []
        msg = "{} is on :\n\n".format(id)
        for s in self.bot.guilds:
            if s.get_member(id):
                servers.append(s)

        for c, s in enumerate(servers, start=1):
            msg += "**{}** : **{}** ({})\n".format(c, s.name, s.id)
        if servers:
            for i in range(0, len(msg), n):
                await ctx.send(msg[i:i + n])
        else:
            await ctx.send("On 0 server.")

    @commands.is_owner()
    @commands.command(aliases=["getinvitations", "getinvitation"])
    async def getinvite(self, ctx, *, id):
        """
            {command_prefix}getinvite [guild_id]

        Gets the availables invitations of a guild.
        """
        try:
            target = await self.bot.safe_fetch('guild', int(args))
        except ValueError:
            target = None
        msg = ""
        if not target:
            target = discord.utils.get(self.bot.guilds, name=id)
        if not target:
            return await ctx.send("**{}** guild not found.".format(id))
        try:
            for e in await target.invites():
                msg += e.url + '\n'
            await ctx.author.send("Invitation : {}".format(msg))
        except discord.HTTPException:
            await ctx.send(":x: missing permissions...")

    @commands.is_owner()
    @commands.command(aliases=["lastmessage", "lastmsg"])
    async def lastmessages(self, ctx, nb: int, *, id: int):
        """
            {command_prefix}lastmessages [channel_id]

        Gets the last messages in a channel.
        """
        msg = []
        n = 1985
        patchchannel = self.bot.get_channel(id)
        if not patchchannel:
            return
        async for lmsg in patchchannel.history(limit=nb):
            msg.append(f"[{lmsg.created_at}] {lmsg.author}/ {lmsg.content}")
            if lmsg.attachments:
                for att in lmsg.attachments:
                    msg.append(att.url)
        msg.reverse()
        msg = '\n\n'.join(msg)
        for i in range(0, len(msg), n):
            await ctx.send(msg[i:i + n])

    @checks.has_permissions(manage_roles=True)
    @commands.guild_only()
    @commands.command(aliases=["giveroles"])
    async def giverole(self, ctx, role: discord.Role, *, user: discord.Member):
        """
            {command_prefix}giverole [role] [user]

        {help}
        """
        if not ctx.channel.permissions_for(ctx.me).manage_roles:
            return await ctx.send(get_str(ctx, "need-manage-roles-permission"))
        if role not in user.roles:
            if role.position >= ctx.author.top_role.position and ctx.author.id != owner_id and not ctx.author is ctx.guild.owner:
                return await ctx.send(get_str(ctx, "role-not-enough-high"))
            if role.position >= ctx.me.top_role.position:
                return await ctx.send(get_str(ctx, "not-enough-permissions"))

            await user.add_roles(role)

            try:
                await ctx.message.add_reaction("☑")
            except discord.Forbidden:
                await ctx.send(get_str(ctx, "cmd-giverole-add").format(f"**{user}**", f"`{role}`"))

        else:
            if role.position >= ctx.author.top_role.position and ctx.author.id != owner_id and not ctx.author is ctx.guild.owner:
                return await ctx.send(get_str(ctx, "role-not-enough-high"))
            if role.position >= ctx.me.top_role.position:
                return await ctx.send(get_str(ctx, "not-enough-permissions"))

            await user.remove_roles(role)

            await ctx.send(get_str(ctx, "cmd-giverole-remove").format(f"`{role}`", f"**{user}**"))

    @commands.group(name="getrole", aliases=["getroles"])
    @commands.guild_only()
    async def _getrole(self, ctx, *, name):
        """
            {command_prefix}getrole [role]
            {command_prefix}getrole add [role]
            {command_prefix}getrole remove [role]

        {help}
        """
        adding = None
        if name.split(' ')[0].lower() in ['add', 'remove']:
            adding = True if (name.split(' ')[0].lower() == 'add') else False
            name = ' '.join(name.split(' ')[1:])
            if not name:
                return await self.bot.send_cmd_help(ctx)

        role = self.bot.get_role(ctx, name)

        if not role:
            return await ctx.send(get_str(ctx, "cmd-joinclan-role-not-found").format(name))

        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        if not settings.roles:
            return await ctx.send(get_str(ctx, "cmd-getrole-no-role-available").format(f"`{get_server_prefixes(ctx.bot, ctx.guild)}setroles`"))
        if role.id not in settings.roles and (ctx.author.id != owner_id):
            return await ctx.send(get_str(ctx, "cmd-getrole-role-not-obtainable").format(f"`{get_server_prefixes(ctx.bot, ctx.guild)}setroles`"))
        if [r for r in ctx.author.roles if r == role]:
            if adding:  # can be None
                return
            try:
                await ctx.author.remove_roles([r for r in ctx.author.roles if r == role][0])
            except discord.Forbidden:
                return await ctx.send(get_str(ctx, "cmd-getrole-not-enough-perm").format(ctx.author.mention, f"`{role}`"))
            await ctx.send(get_str(ctx, "cmd-getrole-remove-success").format(ctx.author.mention, f"`{role}`"))
        else:
            if adding is False:  # can be None
                return
            try:
                await ctx.author.add_roles(role)
                try:
                    await ctx.message.add_reaction("☑")
                except discord.Forbidden:
                    await ctx.send(get_str(ctx, "cmd-getrole-add-success").format(role))
            except discord.Forbidden:
                await ctx.send(get_str(ctx, "cmd-getrole-not-enough-perm-add").format(f"`{role}`"))

    @commands.guild_only()
    @commands.group(name="setrole", aliases=["setroles"], invoke_without_command=True)
    async def _setrole(self, ctx, *, name):
        """
            {command_prefix}setrole create [role_name]
            {command_prefix}setrole delete [role_name]
            {command_prefix}setrole list

        {help}
        """
        if not ctx.invoked_subcommand:
            await ctx.invoke(self.___add, ctx=ctx, name=name)

    @checks.has_permissions(manage_guild=True)
    @_setrole.command(name="add", aliases=["+", "new", "create"])
    async def ___add(self, ctx, *, name):
        """
            {command_prefix}setrole create [role_name]

        {help}
        """
        role = self.bot.get_role(ctx, name)

        if not role:
            return await ctx.send(get_str(ctx, "cmd-joinclan-role-not-found").format(name))

        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)

        if role.id not in settings.roles:
            settings.roles.append(role.id)
            await SettingsDB.get_instance().set_guild_settings(settings)
            await ctx.send(get_str(ctx, "cmd-setrole-added"))
        else:
            await ctx.send(get_str(ctx, "cmd-setrole-already"))

    @checks.has_permissions(manage_guild=True)
    @_setrole.command(name="reset", aliases=["removeall"])
    async def ___reset(self, ctx):
        """
            {command_prefix}setrole reset

        {help}
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        settings.roles = []
        await SettingsDB.get_instance().set_guild_settings(settings)
        await ctx.send(get_str(ctx, "cmd-setrole-reset").format("`{}getrole`".format(get_server_prefixes(ctx.bot, ctx.guild))))

    @checks.has_permissions(manage_guild=True)
    @_setrole.command(name="remove", aliases=["delete", "-"])
    async def ___delete(self, ctx, *, name):
        """
            {command_prefix}setrole delete [role_name]

        {help}
        """
        role = self.bot.get_role(ctx, name)

        if not role:
            return await ctx.send(get_str(ctx, "cmd-joinclan-role-not-found").format(name))

        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)

        if settings.roles:
            if role.id in settings.roles:
                settings.roles.remove(role.id)
                await SettingsDB.get_instance().set_guild_settings(settings)
                await ctx.send(get_str(ctx, "cmd-setrole-removed"))
            else:
                await ctx.send(get_str(ctx, "cmd-setrole-already-d"))
        else:
            await ctx.send(get_str(ctx, "cmd-getrole-no-role-available").format(f"`{get_server_prefixes(ctx.bot, ctx.guild)}setrole`"))

    @_setrole.command(name="list", aliases=["all", "view", "now"])
    async def ___list(self, ctx):
        """
            {command_prefix}setrole list

        {help}
        """
        n = 0
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        msg = [get_str(ctx, "cmd-setrole-list")]
        if settings.roles:
            for clan in settings.roles:
                roles = [r for r in ctx.guild.roles if r.id == clan]
                if not roles:
                    settings.roles.remove(clan)
                    await SettingsDB.get_instance().set_guild_settings(settings)
                    continue
                role = roles[0]
                n += 1
                msg.append("``{}`` {}\n".format(n, role.name))
            if len(msg) == 1:
                return await ctx.send(get_str(ctx, "cmd-getrole-no-role-available").format(f"`{get_server_prefixes(ctx.bot, ctx.guild)}setrole`"))
            to_send = ""
            for line in msg:
                if len(to_send) + len(line) > 1980:  # TODO find a better way to do this
                    await ctx.send(to_send)          # This is ugly
                    to_send = ""
                to_send += line

            if to_send:
                await ctx.send(to_send)
        else:
            await ctx.send(get_str(ctx, "cmd-getrole-no-role-available").format(f"`{get_server_prefixes(ctx.bot, ctx.guild)}setrole`"))

    @commands.command(aliases=['redeem'])
    @commands.cooldown(rate=1, per=2.0, type=commands.BucketType.user)
    async def claim(self, ctx, guild_id: int = None):
        """
            {command_prefix}claim (guild_id)

        Allows to claim a guild.
        """
        if guild_id:
            guild = await self.bot.safe_fetch('guild', guild_id)
            if not guild:
                # TODO: Translations
                return await ctx.send("I didn't find this guild. Ensure your ID or use the command on the guild without specifying an ID.")
        else:
            guild = ctx.guild
        if not await is_patron(self.bot, ctx.author):
            # TODO: Translations
            return await ctx.send("You need to be at least Super Patron on my server to claim a server!")
        settings = await SettingsDB.get_instance().get_glob_settings()
        claimed = await self.bot.server_is_claimed(guild.id)

        if claimed:
            if int(claimed[0]) == ctx.author.id:
                # TODO: Translations
                return await ctx.send(f"This server is already claimed by yourself. Use `{get_server_prefixes(ctx.bot, guild)}unclaim` if you want to unclaim it!")
            claimer = await self.bot.safe_fetch('member', int(claimed[0]), guild=guild) or claimed[0]
            # TODO: Translations
            await ctx.send(f"This server is already claimed by {claimer}.")

        for k, m in settings.claim.items():
            if str(guild.id) in m:
                if not await is_patron(self.bot, int(k)):
                    settings.claim[k].pop(str(guild.id))

        # TODO: Translations
        confirm_message = await ctx.send("Are you sure you want to claim **{}** (id: {}), you'll not be able to unclaim it before 7 days! Type `yes` or `no`.".format(guild.name, guild.id))

        def check(m):
            if m.author.bot or m.author != ctx.author:
                return False
            if m.channel != ctx.channel:
                return False
            if m.content:
                return True
            return False

        try:
            response_message = await self.bot.wait_for('message', timeout=120, check=check)
        except asyncio.TimeoutError:
            try:
                await confirm_message.delete()
            except discord.HTTPException:
                pass
            return

        if not response_message.content.lower().startswith('y'):
            # TODO: Translations
            return await ctx.send("Claim cancelled.")

        if str(ctx.author.id) not in settings.claim:
            settings.claim[str(ctx.author.id)] = {str(
                guild.id): datetime.today().strftime("%d %b %Y")}
        else:
            max_claim = 2
            if await is_lover(self.bot, ctx.author):
                max_claim = 5
            if ctx.author.id == owner_id:
                max_claim = 9e40
            if len(settings.claim[str(ctx.author.id)]) >= max_claim:
                # TODO: Translations
                return await ctx.send("You reached your max claim server count ({}).\n"
                                      "You can unclaim one of your claimed server by issuing `{}unclaim (guild_id)`\n"
                                      "To see your current claimed server, use the command `{}claimlist`".format(max_claim, get_server_prefixes(ctx.bot, guild), get_server_prefixes(ctx.bot, guild)))
            settings.claim[str(ctx.author.id)][str(guild.id)
                                               ] = datetime.today().strftime("%d %b %Y")

        # TODO: Translations
        await ctx.send('Server successfully claimed !')
        await SettingsDB.get_instance().set_glob_settings(settings)

    @commands.command(aliases=['unredeem'])
    @commands.cooldown(rate=1, per=2.0, type=commands.BucketType.user)
    async def unclaim(self, ctx, guild_id: int = None):
        """
            {command_prefix}unclaim (guild_id)

        Allows to unclaim a guild.
        """
        if not guild_id:
            guild_id = str(ctx.guild.id)
        else:
            # param is type int just to ensure that it can be converted to int easily thanks to discord.py
            guild_id = str(guild_id)
        if not await is_patron(self.bot, ctx.author):
            # TODO: Translations
            return await ctx.send("You need to be at least Super Patron on my server to claim/unclaim a server!")
        settings = await SettingsDB.get_instance().get_glob_settings()
        if str(ctx.author.id) in settings.claim:
            if guild_id in settings.claim[str(ctx.author.id)]:
                claimed_since = settings.claim[str(ctx.author.id)][guild_id]
                datetime_date = datetime.strptime(claimed_since, '%d %b %Y')
                since_claimed = (ctx.message.created_at - datetime_date).days
                if (since_claimed < 7) and ctx.author.id != owner_id:
                    # TODO: Translations
                    return await ctx.send("Sorry you're in cooldown! You'll be able to unclaim this server in `{}` days!".format(7 - since_claimed))
                settings.claim[str(ctx.author.id)].pop(guild_id)
                # TODO: Translations
                await ctx.send('Server successfully unclaimed !')
                return await SettingsDB.get_instance().set_glob_settings(settings)
        # TODO: Translations
        await ctx.send('This server is not in your claimed servers...')

    @commands.command(aliases=['redeemlist'])
    @commands.cooldown(rate=1, per=2.0, type=commands.BucketType.user)
    async def claimlist(self, ctx, *, member: discord.Member = None):
        """
            {command_prefix}claimlist

        Displays the list of your claimed guild.
        """
        if not member:
            member = ctx.author
        if not await is_patron(self.bot, member):
            # TODO: Translations
            return await ctx.send("You need to be at least Super Patron on my server to claim/unclaim a server!")
        settings = await SettingsDB.get_instance().get_glob_settings()
        if (str(member.id) not in settings.claim) or not settings.claim[str(member.id)]:
            # TODO: Translations
            return await ctx.send("You don't have any claimed server. Start to add some by using `{}claim`".format(get_server_prefixes(ctx.bot, ctx.guild)))
        desc = ''
        for i, m in enumerate(settings.claim[str(member.id)].items(), start=1):
            guild = await self.bot.safe_fetch('guild', int(m[0]))
            desc += f'`{i}. `' + (('**' + guild.name + '** ')
                                  if guild else '') + f'(`{m[0]}`) ' + f'({m[1]})\n'
        embed = discord.Embed(description=desc)
        embed.set_author(name=member.name, icon_url=member.avatar_url)
        max_claim = 2
        if await is_lover(self.bot, member):
            max_claim = 5
        if member.id == owner_id:
            max_claim = 9e40
        embed.set_footer(
            # TODO: Translations
            text=f"Used claim {len(settings.claim[str(member.id)])}/{max_claim}")
        await ctx.send(embed=embed)

    @commands.guild_only()
    @commands.command(aliases=["guildparam", "servparam", "serversettings", "setting", "config", "guildsettings", "set", "sets"])
    @commands.cooldown(rate=1, per=1.0, type=commands.BucketType.user)
    async def settings(self, ctx, *, guild=None):
        """
            {command_prefix}settings

        {help}
        """
        if guild:  # owner can see other's guild settings
            if ctx.author.id == owner_id:
                try:
                    guild = await self.bot.safe_fetch('guild', int(guild))
                except ValueError:
                    return await ctx.send("Guild not found...")
                if not guild:
                    return await ctx.send("Guild not found...")
            else:
                guild = ctx.guild
        else:
            guild = ctx.guild

        settings = await SettingsDB.get_instance().get_guild_settings(guild.id)
        welcome_channels = []
        goodbye_channels = []
        ignore_channels = []
        autorolemsg = []
        getrolemsg = []
        djmsg = []
        set_dj_roles = set_autoroles_msg = set_roles_msg = ""

        for channel in guild.channels:
            if str(channel.id) in settings.welcomes:
                welcome_channels.append(f"#{channel.name}")
        welcome = ', '.join(welcome_channels)
        if welcome_channels == []:
            welcome = "❌"

        for channel in guild.channels:
            if str(channel.id) in settings.goodbyes:
                goodbye_channels.append(f"#{channel.name}")
        goodbye = ', '.join(goodbye_channels)
        if goodbye_channels == []:
            goodbye = "❌"

        cc = len(settings.customcommands)
        dc = len(settings.disabledcommands)
        clan = len(settings.clans)
        lang = settings.language

        for channel in guild.channels:
            if str(channel.id) in settings.disabledchannels:
                cmd_disabled = len(settings.disabledchannels[str(channel.id)])
                opt = '({} command{})'.format(cmd_disabled, 's'
                                              if cmd_disabled != 1 else '') if cmd_disabled != 0 else ''
                ignore_channels.append(f"#{channel.name} {opt}")
        ignore = ', '.join(ignore_channels)
        if ignore_channels == []:
            ignore = "❌"

        if settings.bound:
            cid = settings.bound
            allid = [c.id for c in guild.channels]
            if int(cid) in allid:
                bind = [c.name for c in guild.channels if c.id == int(cid)][0]
            else:
                bind = False
        else:
            bind = False

        if settings.autoroles:
            for id in settings.autoroles:
                role = guild.get_role(id)
                if role:
                    autorolemsg.append(role.name)
                    set_autoroles_msg = ', '.join(autorolemsg)
            if not set_autoroles_msg:
                set_autoroles_msg = "❌"
        else:
            set_autoroles_msg = "❌"

        if settings.roles:
            for id in settings.roles:
                role = guild.get_role(id)
                if role:
                    getrolemsg.append(role.name)
                    set_roles_msg = ', '.join(getrolemsg)
            if not set_roles_msg:
                set_roles_msg = "❌"
        else:
            set_roles_msg = "❌"

        if settings.djs:
            if "all" in settings.djs:
                set_dj_roles = "@\u200beveryone"
            else:
                for id in settings.djs:
                    role = guild.get_role(id)
                    if role:
                        djmsg.append(role.name)
                        set_dj_roles = ', '.join(djmsg)
                if not set_dj_roles:
                    set_dj_roles = "❌"
        else:
            set_dj_roles = "❌"

        vol = f"{settings.volume}%"

        vote = f"{settings.vote}%"

        if not settings.timer:
            timer = get_str(ctx, 'music-autoleave-never')
        else:
            timer = f"{settings.timer} {get_str(ctx, 'cmd-nextep-seconds')}"

        if settings.channel:
            channel = guild.get_channel(settings.channel)
            if channel:
                np = f"#{channel}"
            else:
                np = "❌"
        elif settings.channel is None:
            np = "☑ Auto"
        else:
            np = "❌"

        embed = discord.Embed()

        embed.set_author(name=get_str(
            ctx, "cmd-settings-title"), icon_url=guild.icon_url)
        if not guild:
            embed.color = 0x71368a
        else:
            embed.color = ctx.me.color

        if not settings.blacklisted:
            bl_users = 0
        else:
            message_bl = []
            for l in settings.blacklisted:
                m = discord.utils.find(lambda m: m.id == int(l), ctx.guild.roles) or await self.bot.safe_fetch('member', int(l), guild=ctx.guild)
                if m:
                    message_bl.append(f"`{m}`")
                if message_bl:
                    bl_users = ', '.join(message_bl)
                else:
                    bl_users = 0

        ac_desc_list = []
        for key in settings.autosongs.keys():
            channel = ctx.guild.get_channel(int(key))
            if channel:
                ac_desc_list.append(channel.name)
        if ac_desc_list:
            ac_desc = ', '.join(ac_desc_list)
        else:
            ac_desc = get_str(ctx, "music-plsettings-no")

        struct = "*{} :* **{}**"
        embed.description = get_str(
            ctx, "cmd-help-support").format('[World of Watora](https://discord.gg/ArJgTpM)')

        msg = []
        names = ['guild-pref', 'language', 'owo']
        values = [get_server_prefixes(ctx.bot, guild), lang, [get_str(
            ctx, "music-plsettings-no"), get_str(ctx, "music-plsettings-yes")][settings.owo]]
        for i, name in enumerate(names):
            msg.append(struct.format(
                get_str(ctx, f"cmd-settings-{name}"), values[i]))
        embed.add_field(name=get_str(ctx, "cmd-settings-glob"),
                        value='\n'.join(msg))

        msg = []
        names = ['clans', 'autoroles', 'o-roles', 'dj-roles']
        values = [clan, set_autoroles_msg, set_roles_msg, set_dj_roles]
        for i, name in enumerate(names):
            msg.append(struct.format(
                get_str(ctx, f"cmd-settings-{name}"), values[i]))
        embed.add_field(name=get_str(ctx, "cmd-userinfo-roles"),
                        value='\n'.join(msg), inline=False)

        msg = []
        names = ['cc', 'dc']
        values = [cc, dc]
        for i, name in enumerate(names):
            msg.append(struct.format(
                get_str(ctx, f"cmd-settings-{name}"), values[i]))
        embed.add_field(name=get_str(ctx, "cmd-settings-commands"),
                        value='\n'.join(msg), inline=False)

        msg = []
        names = ['bluser']
        values = [bl_users]
        if bind:
            names.append('bind')
            values.append(bind)
        else:
            names.append('ic')
            values.append(ignore)
        for i, name in enumerate(names):
            msg.append(struct.format(
                get_str(ctx, f"cmd-settings-{name}"), values[i]))
        embed.add_field(name=get_str(ctx, "cmd-settings-permissions"),
                        value='\n'.join(msg), inline=False)

        msg = []
        names = ['wm', 'gm']
        values = [welcome, goodbye]
        for i, name in enumerate(names):
            msg.append(struct.format(
                get_str(ctx, f"cmd-settings-{name}"), values[i]))
        embed.add_field(name=get_str(ctx, "cmd-settings-messages"),
                        value='\n'.join(msg), inline=False)

        msg = []
        names = ['autoplay', 'lazy', 'lvc', 'dv', 'vote', 'ac', 'np']
        values = [[get_str(ctx, "music-plsettings-no"), get_str(ctx, "music-plsettings-yes")][settings.autoplay], [get_str(
            ctx, "music-plsettings-no"), get_str(ctx, "music-plsettings-yes")][settings.lazy], timer, vol, vote, ac_desc, np]
        for i, name in enumerate(names):
            msg.append(struct.format(
                get_str(ctx, f"cmd-settings-{name}"), values[i]))

        if settings.defaultnode:
            member = ctx.guild.get_member(int(settings.defaultnode))
            if member:
                # TODO: Translations and move it
                msg.append(struct.format(
                    "Default music node", f'Hosted by {member}'))
        embed.add_field(name=get_str(ctx, "cmd-settings-player"),
                        value='\n'.join(msg), inline=False)

        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"))


def setup(bot):
    bot.add_cog(Useful(bot))
