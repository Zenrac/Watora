import random
import math
import aiohttp
import discord
import asyncio
import inspect
import traceback
import unidecode

from io import BytesIO
from utils import checks
from utils.db import SettingsDB
from discord.ext import commands
from pyfiglet import figlet_format
from utils.watora import get_server_prefixes, is_lover, is_basicpatron, get_str, format_mentions, get_image_from_url


class Fun(commands.Cog):
    """The fun cog"""

    def __init__(self, bot):
        self.bot = bot
        self.minesweeper_levels = {
            'BEGINNER': (10, 10, 10),
            'INTERMEDIATE': (12, 12, 25),
            'EXPERT': (14, 14, 50)
        }

    def to_keycap(self, c):
        return '\N{KEYCAP TEN}' if c == 10 else str(c) + '\u20e3'

    def generate_minesweeper_board(self, nrows, ncols, nbombs):
        """
        Generates a minesweeper board as an array of arrays of numbers.
        -1 is a bomb,
        0 is empty,
        Positive numbers are the number of adjacent bombs.
        """
        nrows = max(1, min(14, nrows))
        ncols = max(1, min(14, ncols))
        nbombs = max(0, min(ncols * nrows, nbombs))
        bombs = []
        posibilities = []
        for r in range(nrows):
            for c in range(ncols):
                posibilities += [(r, c)]
        for i in range(nbombs):
            if posibilities:
                newbomb = {'x': -1, 'y': -1}
                position = random.choice(posibilities)
                newbomb['x'] = position[0]
                newbomb['y'] = position[1]
                posibilities.remove(position)
                bombs.append(newbomb)

        board = [[0] * ncols for _ in range(nrows)]
        for r in range(nrows):
            for c in range(ncols):
                has_bomb = any(
                    map(lambda b: b['x'] == r and b['y'] == c, bombs))
                if has_bomb:
                    board[r][c] = -1
                else:
                    adjc = 0
                    for i in range(r - 1, r + 2):
                        for j in range(c - 1, c + 2):
                            adjc += sum(map(lambda b: 1 if b['x']
                                            == i and b['y'] == j else 0, bombs))
                    board[r][c] = adjc

        REPR = [':bomb:', ':cyclone:', ':one:', ':two:', ':three:',
                ':four:', ':five:', ':six:', ':seven:', ':eight:']
        msg = '\n'.join(''.join(map(lambda n: "||{}||".format(
            REPR[n + 1] if len(REPR) > n + 1 else ':cyclone:'), row)) for row in board)
        if len(msg) > 2000:
            # Prevent from infinite loop.
            return self.generate_minesweeper_board(min(ncols - 1, 10), min(nrows - 1, 10), nbombs)
        return msg

    @commands.command(aliases=["mine", "mines", "demineur", "démineur"])
    async def minesweeper(self, ctx, level_or_rows='BEGINNER', ncols: int = 10, nbombs: int = 10):
        """
            {command_prefix}minesweeper [level]
            {command_prefix}minesweeper [number of rows] [number of cols] [number of bombs]

        {help}
            BEGINNER: 10, 10, 10,
            INTERMEDIATE: 12, 12, 25
            EXPERT: 14, 14, 50
        """
        choice = None

        for k in self.minesweeper_levels.keys():
            if k.startswith(level_or_rows.upper()):
                choice = self.minesweeper_levels[k]
                break

        if choice:
            board = self.generate_minesweeper_board(*choice)
            return await ctx.send(board)
        try:
            level_or_rows = int(level_or_rows)
            ncols = int(ncols)
            nbombs = int(nbombs)
        except ValueError:
            return await self.bot.send_cmd_help(ctx)

        board = self.generate_minesweeper_board(level_or_rows, ncols, nbombs)
        await ctx.send(board)

    @commands.command(name="8ball", aliases=["8balls", "eightball"])
    async def _8ball(self, ctx, *, more: str):
        """
            {command_prefix}8ball [question]

        {help}
        """
        await ctx.send(random.choice(get_str(ctx, "cmd-8ball-options").split("|")))

    @commands.command(aliases=['wp', 'watopingd', 'wpd'])
    async def watoping(self, ctx):
        """
            {command_prefix}watoping

        Best emoji ever.
        """
        if 'd' in ctx.invoked_with.lower():
            ctx.command.reset_cooldown(ctx)
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass

        await ctx.send("<:watoping:458349269875949569>")

    @commands.cooldown(rate=1, per=2, type=commands.BucketType.user)
    @commands.command(name="ily", aliases=["jtm"])
    async def _ily(self, ctx, more=None):
        """
            {command_prefix}ily

        {help}
        """
        fetched_member = await is_lover(self.bot, ctx.author, fetch=True)
        if more and not fetched_member:
            await ctx.send(get_str(ctx, "cmd-ily-nope"))
        elif more:
            await ctx.send("<:WatoraCry:458349266495078413>")
        elif fetched_member:
            await ctx.send(random.choice(get_str(ctx, "cmd-ily-yes").split("|")))
        else:
            await ctx.send(random.choice(get_str(ctx, "cmd-ily-no").split("|")))

    @commands.command()
    async def roll(self, ctx, maxi: str = 100, mini: int = 0):
        """
            {command_prefix}roll [number_of_dice]d[number_of_face]
            {command_prefix}roll [min] [max]
            {command_prefix}roll [max]
            {command_prefix}roll

        {help}
        """
        if not str(maxi).isdigit():
            numbers = maxi.split('d')
            if not len(numbers) == 2:
                return await self.bot.send_cmd_help(ctx)

            number, face = numbers

            try:
                number = min(int(number), 10)
                face = min(int(face), 10000)
            except ValueError:
                return await self.bot.send_cmd_help(ctx)

            results = []

            for m in range(number):
                results.append(random.randint(1, face))

            if number != 1:
                roll = '{} ({})'.format(
                    sum(results), ' + '.join([str(m) for m in results]))
            else:
                roll = sum(results)

        elif int(maxi) <= mini:
            roll = random.randint(int(maxi), mini)
        else:
            roll = random.randint(mini, int(maxi))

        await ctx.send(":game_die: " + get_str(ctx, "cmd-roll").format(ctx.author.name, roll))

    @commands.command()
    async def flip(self, ctx, *, user: discord.Member = None):
        """
            {command_prefix}flip [user]
            {command_prefix}flip

        {help}
        """
        if user:
            msg = ""
            if user.id == self.bot.user.id or await is_basicpatron(self.bot, user):
                user = ctx.author
                msg = get_str(ctx, "cmd-flip-nice-try") + "\n\n"
            char = "abcdefghijklmnopqrstuvwxyz"
            tran = "ɐqɔpǝɟƃɥᴉɾʞlɯuodbɹsʇnʌʍxʎz"
            table = str.maketrans(char, tran)
            name = user.display_name.translate(table)
            char = char.upper()
            tran = "∀qƆpƎℲפHIſʞ˥WNOԀQᴚS┴∩ΛMX⅄Z"
            table = str.maketrans(char, tran)
            name = name.translate(table)
            await ctx.send(msg + "(╯°□°）╯︵ " + name[::-1])
        else:
            await ctx.send("*" + get_str(ctx, "cmd-flip-success") + " " + random.choice([get_str(ctx, "cmd-flip-heads"), get_str(ctx, "cmd-flip-tails")]) + "*")

    @commands.guild_only()
    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.user)
    @commands.group(aliases=["cc", "customcom", "aliases", "alias", "customcommande"])
    async def customcommand(self, ctx):
        """
            {command_prefix}cc add [command] [content]
            {command_prefix}cc edit [command] [new_content]
            {command_prefix}cc delete [command]
            {command_prefix}cc list
            {command_prefix}cc raw [command]

        {help}
        """
        if not ctx.invoked_subcommand:
            await ctx.send(get_str(ctx, "command-invalid-usage").format("{}help cc".format(get_server_prefixes(ctx.bot, ctx.guild))))

    @commands.guild_only()
    @checks.has_permissions(manage_guild=True)
    @customcommand.command(name="add", aliases=["+", "new"])
    async def _add(self, ctx, command, *, content):
        """
            {command_prefix}cc add [command] [content]
            {command_prefix}cc add [command] >>>[my_command]

        {help}
        """
        command = command.lower()
        cmd = self.bot.get_command(command)
        if cmd:
            return await ctx.send(get_str(ctx, "cmd-customcommand-in-basic-command"))

        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)

        if command not in settings.customcommands:
            content = format_mentions(content)
            settings.customcommands[command] = content
            await SettingsDB.get_instance().set_guild_settings(settings)
            await ctx.send(get_str(ctx, "cmd-customcommand-added"))
        else:
            await ctx.send(get_str(ctx, "cmd-customcommand-already-exists").format("`{}customcom edit`".format(get_server_prefixes(ctx.bot, ctx.guild))))

    @customcommand.command(name="raw", aliases=["real", "content"])
    async def _raw(self, ctx, command):
        """
            {command_prefix}cc raw [command]

        {help}
        """
        command = command.lower()

        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)

        if not settings.customcommands:
            await ctx.send(get_str(ctx, "cmd-customcommand-raw-no-cc").format("`{}customcom add`".format(get_server_prefixes(ctx.bot, ctx.guild))))

        elif command in settings.customcommands:
            await ctx.send(get_str(ctx, "cmd-customcommand-raw-content").format(f"`{command}`") + "\n{}".format(settings.customcommands[command]))
        else:
            await ctx.send(get_str(ctx, "cmd-customcommand-raw-dont-exist"))

    @checks.has_permissions(manage_guild=True)
    @customcommand.command(name="edit", aliases=["change", "modify"])
    async def _edit(self, ctx, command, *, new_content):
        """
            {command_prefix}cc edit [command] [new_content]

        {help}
        """
        command = command.lower()

        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)

        if not settings.customcommands:
            await ctx.send(get_str(ctx, "cmd-customcommand-raw-no-cc").format("`{}customcom add`".format(get_server_prefixes(ctx.bot, ctx.guild))))

        elif command in settings.customcommands:
            settings.customcommands[command] = new_content
            await SettingsDB.get_instance().set_guild_settings(settings)
            await ctx.send(get_str(ctx, "cmd-customcommand-success-edit"))
        else:
            await ctx.send(get_str(ctx, "cmd-customcommand-failed-edit").format("`{}customcom add`".format(get_server_prefixes(ctx.bot, ctx.guild))))

    @checks.has_permissions(manage_guild=True)
    @customcommand.command(name="delete", aliases=["remove", "-"])
    async def _delete(self, ctx, command):
        """
            {command_prefix}cc delete [command]

        {help}
        """
        command = command.lower()

        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)

        if not settings.customcommands:
            await ctx.send(get_str(ctx, "cmd-customcommand-raw-no-cc").format("`{}customcom add`".format(get_server_prefixes(ctx.bot, ctx.guild))))

        elif command in settings.customcommands:
            settings.customcommands.pop(command, None)
            await SettingsDB.get_instance().set_guild_settings(settings)
            await ctx.send(get_str(ctx, "cmd-customcommand-deleted"))
        else:
            await ctx.send(get_str(ctx, "cmd-customcommand-failed-edit").format("`{}customcom add`".format(get_server_prefixes(ctx.bot, ctx.guild))))

    @customcommand.command(name="list", aliases=["all", "view"])
    async def _list(self, ctx):
        """
            {command_prefix}cc list

        {help}
        """
        msg = [get_str(ctx, "cmd-customcommand-list")]

        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)

        if not settings.customcommands:
            return await ctx.send(get_str(ctx, "cmd-customcommand-raw-no-cc").format("`{}customcom add`".format(get_server_prefixes(ctx.bot, ctx.guild))))

        for n, command in enumerate(settings.customcommands, start=1):
            msg.append("``{}`` {}\n".format(n, command))

        if len(msg) == 1:
            return await ctx.send(get_str(ctx, "cmd-customcommand-raw-no-cc").format("`{}customcom add`".format(get_server_prefixes(ctx.bot, ctx.guild))))

        to_send = ""
        for line in msg:
            if len(to_send) + len(line) > 1980:  # TODO find a better way to do this
                await ctx.send(to_send)      # This is ugly
                to_send = ""
            to_send += line

        if to_send:
            await ctx.send(to_send)

    @commands.cooldown(rate=1, per=2.0, type=commands.BucketType.user)
    @commands.command()
    async def ascii(self, ctx, *, text):
        """
            {command_prefix}ascii [text]

        {help}
        """
        text = unidecode.unidecode(text)
        msg = str(figlet_format(text.strip(), font="standard"))
        if len(msg) > 2000:
            await ctx.send(get_str(ctx, "cmd-ascii-too-long"))
        else:
            mseg = '```{}```'.format(msg)
            if mseg != "``````":
                await ctx.send(mseg)

    @commands.cooldown(rate=1, per=2.0, type=commands.BucketType.user)
    @commands.command(aliases=['sondage', 'survey'])
    @commands.guild_only()
    async def poll(self, ctx, *, question):
        """
            {command_prefix}poll [question]

        {help}
        """
        messages = [
            ctx.message]  # a list of messages to delete when we're all done
        question = format_mentions(question)
        answers = []
        for i in range(1, 11):
            messages.append(await ctx.send(get_str(ctx, "cmd-poll-init").format("`{}cancel`".format(get_server_prefixes(ctx.bot, ctx.guild)))))
            try:
                entry = await self.bot.wait_for('message', check=lambda m: len(m.content) <= 100 and m.author == ctx.author and m.channel == ctx.channel, timeout=60.0)
            except asyncio.TimeoutError:
                break

            if not entry:
                break

            prefixes = [get_server_prefixes(
                ctx.bot, ctx.guild), f"<@!{self.bot.user.id}>", self.bot.user.mention]
            if any([entry.content.startswith(p) for p in prefixes]):
                break

            messages.append(entry)

            answers.append((self.to_keycap(i), entry.clean_content))

        try:
            await ctx.channel.delete_messages(messages)
        except discord.Forbidden:
            pass  # oh well

        answer = '\n'.join(map(lambda t: '%s - %s' % t, answers))
        if answer == "":
            return await ctx.send(get_str(ctx, "cmd-poll-cancelled"), delete_after=10)
        actual_poll = await ctx.send('**%s** {}:\n\n*- %s*\n\n%s'.format(get_str(ctx, "cmd-poll-someone-asks")) % (ctx.author, question, answer))
        for emoji, _ in answers:
            await actual_poll.add_reaction(emoji)

    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    @commands.command()
    async def meme(self, ctx, pic, *, msg):
        """
            {command_prefix}meme [User] [top_text]|[bottom_text]
            {command_prefix}meme [custom_url] [top_text]|[bottom_text]

        {help}
        """
        user = None
        #  msg = unidecode.unidecode(msg)
        if len(ctx.message.mentions) > (2 if self.bot.user.mention in ctx.prefix else 1):
            return await ctx.send(get_str(ctx, "cmd-meme-one-user"))
        if ctx.message.mentions:
            # mention on a nicknamed user on mobile creates weird issue (no '!' where it should)
            user = ctx.message.mentions[-1]
            if str(user.id) not in pic:  # It was a prefix
                user = None
                if len(ctx.message.mentions) > 1:
                    user = ctx.message.mentions[0]
        if ctx.guild:
            if pic.isdigit():
                target = ctx.guild.get_member(int(pic))
                if target:
                    user = target

            check_str = [
                u for u in ctx.guild.members if u.name.lower() == pic.lower()]
            if check_str:
                user = check_str[0]

        if user:
            pic = str(user.avatar_url)

        pic = pic.strip('<>')

        msg = " ".join(msg.split())  # remove useless spaces
        msg = msg.replace('\r', '').replace('\n', '').replace("-", "--").replace("_", "__").replace(
            "?", "~q").replace("#", "~h").replace(" ", "_").replace("%", "~p").replace("/", "~s").replace('"', "''")
        try:
            part1 = msg.split("|")[0]
        except IndexError:
            part1 = "_"
        try:
            part2 = msg.split("|")[1]
        except IndexError:
            part2 = "_"
        if part1 == "":
            part1 = "_"
        if part2 == "":
            part2 = "_"
        if not get_image_from_url(pic):
            return await ctx.send(get_str(ctx, "command-invalid-usage").format("{}help meme".format(get_server_prefixes(ctx.bot, ctx.guild))))
        if part2 != "_":
            total = "https://memegen.link/custom/{}/{}.jpg?alt={}".format(
                part1, part2, pic)
        else:
            total = "https://memegen.link/custom/{}/_.jpg?alt={}".format(
                part1, pic)
        embed = discord.Embed()
        embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar_url)

        # download file
        async with aiohttp.request("GET", total) as resp:
            img = BytesIO(await resp.read())

        f = discord.File(img, filename="image.png")
        embed.set_image(url="attachment://image.png")

        if not user:
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass
        try:
            await ctx.send(file=f, embed=embed)
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    @commands.command(name="osu", aliases=["ozu", "osu!"])
    async def osu(self, ctx, *, name: str):
        """
            {command_prefix}osu [Username]
            {command_prefix}osu [mode] [Username]

        {help}
        """
        if ctx.message.mentions:
            # mention on a nicknamed user on mobile creates weird issue (no '!' where it should)
            user = ctx.message.mentions[-1]
            if str(user.id) not in name:  # It was a prefix
                user = None
                if len(ctx.message.mentions) > 1:
                    user = ctx.message.mentions[0]
            name = user.name
        pseudo = name.split(" ")
        mode = None
        modes = ["standard", "taiko", "ctb", "catch the beat",
                 "mania", "default", "defaut", "défaut", "normal", "osu"]
        conv = {"standard": "0", "taiko": "1", "ctb": "2", "catch the beat": "2", "mania": "3",
                "default": "0", "défaut": "0", "defaut": "0", "normal": "0", "osu": "0"}
        mode = [word for word in pseudo if word.lower() in modes]

        if not mode:
            mode = "standard"
        else:
            mode = mode[0]
            pseudo.remove(mode)

        pseudo = '%20'.join(pseudo)
        if not pseudo:
            pseudo = mode
        if not isinstance(ctx.channel, discord.abc.PrivateChannel):
            color = "hex" + str(ctx.author.color)[1:]
        else:
            color = "pink"
        mode = conv[mode.lower()]
        em = discord.Embed()
        em.set_author(name="osu!", icon_url="https://image.noelshack.com/fichiers/2018/11/4/1521143059-ici.png",
                      url=f"https://osu.ppy.sh/u/{pseudo}")
        em.set_image(
            url=f"https://lemmmy.pw/osusig/sig.php?colour={color}&uname={pseudo}&mode={mode}&pp=0&onlineindicator=undefined&xpbar")
        try:
            await ctx.send(embed=em)
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"), delete_after=20)

    @commands.cooldown(rate=3, per=1.5, type=commands.BucketType.user)
    @commands.command(name="choice", aliases=["pick", "choices", "select", "choose", "choix"])
    async def choice(self, ctx, *, name: str):
        """
            {command_prefix}choice [option_1] | [option_2] | [option_3] | ...
            {command_prefix}choice >>>[command_option_1] | >>>[command_option_2] | [option_3] | ...

        {help}
        """
        choices = [o for o in name.split("|") if o.strip()]
        if choices:
            opt = random.choice(choices)
        else:
            return await ctx.send(get_str(ctx, "cmd-choice-empty-option"))

        opt = opt.strip()
        opt = await self.bot.format_cc(opt, ctx.message)
        if "&&" in opt:
            all = opt.split("&&")
            if len(all) > 9:
                return await ctx.send(get_str(ctx, "cmd-choice-too-much-cmds"))
            for m in all:
                m = m.lstrip()
                m = m[3:]
                ctx.message.content = f"{get_server_prefixes(ctx.bot, ctx.guild)}{m}"
                await self.bot.process_commands(ctx.message)
            return

        if ">>>" in opt:
            while ">>> " in opt:
                opt = opt.replace(">>> ", ">>>")
            opt = ''.join(opt.split(">>>")[1:])
            ctx.message.content = f"{get_server_prefixes(ctx.bot, ctx.guild)}{opt}"

            return await self.bot.process_commands(ctx.message)

        opt = format_mentions(opt)
        pic = get_image_from_url(opt)
        if pic:
            e = discord.Embed()
            e.set_image(url=pic)
            opts = opt.replace(pic, "")
            try:
                return await ctx.send(embed=e, content=opts)
            except discord.Forbidden:
                return await ctx.send(get_str(ctx, "need-embed-permission"))

        await ctx.send(opt)

    @commands.cooldown(rate=3, per=1.5, type=commands.BucketType.user)
    @commands.command(aliases=['f', 'press', 'respect', 'respects'])
    async def pressf(self, ctx, *, target: str = None):
        """
            {command_prefix}f (something)

        Press F to pay respect.
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        settings.respect += 1
        await SettingsDB.get_instance().set_guild_settings(settings)

        desc = f'**{ctx.author.name}** has paid their respects'
        desc += f' to {target}.' if target else '.'

        e = discord.Embed(description=desc)
        e.set_footer(
            text=f"Total of {settings.respect} respect{'s' if settings.respect != 1 else ''} on this server.")

        await ctx.send(embed=e)

    @commands.is_owner()
    @commands.command()
    async def funeval(self, ctx, *, stmt: str):
        """
            {command_prefix}musiceval

        Evals something.
        """
        try:
            result = eval(stmt)
            if inspect.isawaitable(result):
                result = await result
        except Exception:
            exc = traceback.format_exc().splitlines()
            result = exc[-1]
        return await ctx.channel.send("```py\n--- In ---\n{}\n--- Out ---\n{}\n```".format(stmt, result))


def setup(bot):
    bot.add_cog(Fun(bot))
