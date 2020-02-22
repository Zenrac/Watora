import discord
import aiohttp
import asyncio
import json

from io import BytesIO
from unidecode import unidecode
from urllib.parse import quote
from discord.ext import commands
from utils.watora import is_lover, get_str, is_basicpatron, get_image_from_url
from weebapi import Client as weebclient
from arcadia.errors import Forbidden
from arcadia import Client as arcadiaclient
from cogs.gestion import cmd_list, cmd_meme

memer = "https://dankmemer.services/api"
ksoft_api = "https://api.ksoft.si/images/random-image"
cmd = '{command_prefix}'
doc = '"""'


class Weeb(commands.Cog):
    """Cog for weeb content such as kiss, hug"""

    def __init__(self, bot):
        self.bot = bot
        self._cd = commands.CooldownMapping.from_cooldown(
            1.0, 3.0, commands.BucketType.user)
        self.lazy_api = "https://i.ode.bz/auto"
        self.session = aiohttp.ClientSession(loop=self.bot.loop)
        self.ksoft_headers = {
            'authorization': f'Bearer {self.bot.tokens["KSOFT"]}'}
        self.dankmemer_header = {'authorization': self.bot.tokens['MEMER']}
        weebclient.pluggable(bot=bot, api_key=self.bot.tokens['WEEB'])
        arcadiaclient.pluggable(
            bot=bot, token=self.bot.tokens['ARCADIA'], aiosession=self.session)

    def cog_unload(self):
        asyncio.ensure_future(self.session.close())
        del self.bot.arcadia

    async def get_image_ksoft(self, tag: str, nsfw: bool = True):
        params = f'?tag={tag}&nsfw={nsfw}'
        url = ksoft_api + params
        async with self.session.get(url, headers=self.ksoft_headers, timeout=20) as response:
            if response.status != 200:
                raise Forbidden('You are not allowed to access this resource.')
            ext = response.content_type.split('/')[-1]
            img = await response.read()
            await response.release()
        img = json.loads(img)
        return img['url']

    async def cog_check(self, ctx):
        bucket = self._cd.get_bucket(ctx.message)
        retry_after = bucket.update_rate_limit()
        if await is_basicpatron(self.bot, ctx.author):  # less cd for Patrons
            if retry_after:
                if retry_after < 2:
                    bucket.reset()
                    return True
                else:
                    retry_after -= 2

        if retry_after:
            raise commands.errors.CommandOnCooldown(bucket, retry_after)
        return True

    async def cog_command_error(self, ctx, error):
        """A local error handler for all errors arising from commands in this cog"""
        if hasattr(error, 'original'):
            if isinstance(error.original, aiohttp.ClientError) or isinstance(error.original, asyncio.futures.TimeoutError):
                try:
                    await ctx.send(":exclamation: " + get_str(ctx, "cmd-nextep-error"), delete_after=20)
                except discord.HTTPException:
                    pass

    async def get_meme_image(self, image_type: str, url: str = None, text: str = None,
                             timeout: int = 300, **args):
        """
        Basic get_image function using aiohttp
        Returns a Discord File
        """
        if text:
            text = quote(text)
        url = '{}/{}{}{}'.format(memer, image_type.lower(), '?avatar1={}'.format(url) if url else '',
                                 '{}text={}'.format('&' if url else '?', text) if text else '')
        for p, v in args.items():
            url += '&{}={}'.format(p, v)
        async with self.session.get(url, headers=self.dankmemer_header, timeout=timeout) as response:
            if response.status != 200:
                raise Forbidden('You are not allowed to access this resource.')
            ext = response.content_type.split('/')[-1]
            img = BytesIO(await response.read())
            await response.release()
        return discord.File(img, filename="image.{}".format(ext))

    @commands.command(aliases=["image", "img", "generators", "generator", "images", "gen", "generate", "pic", "imagelist", "weeb", "picturelist", "pictures", "weeblist", "weebpic", "helpweeb", "weebhelp"])
    async def picture(self, ctx):
        """
            {command_prefix}picture

        {help}
        """
        embed = discord.Embed(
            description="Powered by weeb.sh and arcadia-api.")
        embed.set_author(name="Image list", icon_url=self.bot.user.avatar_url)
        if not ctx.guild:
            embed.color = 0x71368a
        else:
            embed.color = ctx.me.color

        for k, v in cmd_list.items():
            embed.add_field(name=k, value=f'`{"`, `".join(v)}`', inline=False)
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"))

    weeb = ['Anime actions', 'Anime', 'Memes']
    weeb_cmd = []
    memes = []
    for m in cmd_meme.values():
        memes += m
    for we in weeb:
        for v in cmd_list[we]:
            if v not in memes:
                weeb_cmd.append(v)

    aliases = {
        'clagwimoth': ", '?', '??', '???'",
        'neko': ", 'catgirl', 'catgirls'",
        'delet_this': ', "deletethis", "deletthis", "delete_that", "delete_this", "deletethat"',
        'discord_memes': '", discordmemes", "discord_meme", "discordmeme"',
        'tail': ', "wag"',
        'waifu_insult': ', "waifuinsult", "waifuinsults"',
        'initial_d': ', "initiald"',
        'greet': ', "aurevoir", "cya", "greetings", "greeting"',
        'love': ', "deredere"'
    }

    for m in weeb_cmd:
        a = f"""

@commands.command(aliases=['{m}s'{aliases.get(m, '')}])
async def {m}(self, ctx):
    {doc}
        {cmd}{m}

    Displays a random {m} image.
    {doc}
    image = await self.bot.weebsh.get_random(image_type="{m.replace('animedab', 'dab').replace('love', 'deredere').replace('pic', '').replace('tail', 'wag')}")
    embed = discord.Embed().set_image(url=image)
    try:
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send(get_str(ctx, "need-embed-permission"))
        """
        exec(a)

    for m in cmd_list['Filters']:
        a = f"""

@commands.command(name='{m}', aliases=['{m}fy', '{m}ly'])
async def _{m}(self, ctx, pic=None):
    {doc}
        {cmd}{m} [user]
        {cmd}{m} [url]

    {m} someone.
    {doc}
    user = None
    if not pic:
        user = ctx.author
    embed = discord.Embed()
    embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar_url)
    if not user:
        if ctx.message.mentions:
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

        check_str = [u for u in ctx.guild.members if u.name.lower() == pic.lower()]
        if check_str:
            user = check_str[0]

    if pic:
        pic = pic.strip('<>')

    if user:
        pic = str(user.avatar_url_as(format='png'))
    elif not get_image_from_url(pic):
        return await self.bot.send_cmd_help(ctx)

    img = await self.bot.arcadia.get_image('{m}'.replace('color', '').replace('halloween', 'jackolantern'), url=pic, timeout=20)
    embed.set_image(url=f"attachment://%s" % img.filename)

    try:
        await ctx.send(file=img, embed=embed)
    except discord.Forbidden:
        await ctx.send(get_str(ctx, "need-embed-permission"))
        """
        exec(a)

    for m in cmd_meme['1 avatar']:
        a = f"""

@commands.command(name='{m}', aliases=['{m}fy', '{m}ly'])
async def _{m}(self, ctx, pic=None):
    {doc}
        {cmd}{m} [user]
        {cmd}{m} [url]

    {m} someone.
    {doc}
    user = None
    if not pic:
        user = ctx.author
    embed = discord.Embed()
    embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar_url)
    if not user:
        if ctx.message.mentions:
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

        check_str = [u for u in ctx.guild.members if u.name.lower() == pic.lower()]
        if check_str:
            user = check_str[0]

    if pic:
        pic = pic.strip('<>')

    if user:
        pic = str(user.avatar_url_as(format='png'))
    elif not get_image_from_url(pic):
        return await self.bot.send_cmd_help(ctx)


    img = await self.get_meme_image('{m}', url=pic, timeout=20)
    embed.set_image(url=f"attachment://%s" % img.filename)
    embed.set_footer(text="Powered by DANK MEMER IMGEN")

    try:
        await ctx.send(file=img, embed=embed)
    except discord.Forbidden:
        await ctx.send(get_str(ctx, "need-embed-permission"))
        """
        exec(a)
    for m in cmd_meme['1 text']:
        a = f"""
@commands.command(name='{m}', aliases=['{m}s'])
async def _{m}(self, ctx, *, text):
    {doc}
        {cmd}{m} [text]

    Write some text about {m}.
    {doc}
    embed = discord.Embed()
    embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar_url)

    img = await self.get_meme_image('{m.replace("sip", "")}', text=text, timeout=20)
    embed.set_image(url=f"attachment://%s" % img.filename)
    embed.set_footer(text="Powered by DANK MEMER IMGEN")

    try:
        if '.mp4' not in img.filename:
            await ctx.send(file=img, embed=embed)
        else:
            await ctx.send(file=img)
    except discord.Forbidden:
        await ctx.send(get_str(ctx, "need-embed-permission"))
        """
        exec(a)

    for m in cmd_meme['2 avatars']:
        a = f"""
@commands.command(name='{m}', aliases=['{m}fy', '{m}ly'])
async def _{m}(self, ctx, pic=None, pic2=None):
    {doc}
        {cmd}{m} [user|url] [user|url]

    {m} two peoples.
    {doc}
    user = None
    user2 = None
    if not pic:
        user = ctx.author
    if not pic2:
        user2 = ctx.author
    embed = discord.Embed()
    embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar_url)
    if not user:
        if ctx.message.mentions:
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

            check_str = [u for u in ctx.guild.members if u.name.lower() == pic.lower()]
            if check_str:
                user = check_str[0]

    if not user2:
        if ctx.message.mentions:
            user2 = ctx.message.mentions[-1]
            if str(user2.id) not in pic2:  # It was a prefix
                user2 = None
                if len(ctx.message.mentions) > 1:
                    user2 = ctx.message.mentions[-1]
        if ctx.guild:
            if pic2.isdigit():
                target = ctx.guild.get_member(int(pic2))
                if target:
                    user2 = target

            check_str = [u for u in ctx.guild.members if u.name.lower() == pic2.lower()]
            if check_str:
                user2 = check_str[0]

    if pic:
        pic = pic.strip('<>')
    if pic2:
        pic2 = pic2.strip('<>')

    if user:
        pic = str(user.avatar_url_as(format='png'))
    elif not get_image_from_url(pic):
        return await self.bot.send_cmd_help(ctx)
    if user2:
        pic2 = str(user2.avatar_url_as(format='png'))
    elif not get_image_from_url(pic2):
        return await self.bot.send_cmd_help(ctx)

    img = await self.get_meme_image('{m.replace('robin', '')}', url=pic, avatar2=pic2, timeout=20)
    embed.set_image(url=f"attachment://%s" % img.filename)
    embed.set_footer(text="Powered by DANK MEMER IMGEN")

    try:
        await ctx.send(file=img, embed=embed)
    except discord.Forbidden:
        await ctx.send(get_str(ctx, "need-embed-permission"))
        """
        exec(a)

    for m in cmd_meme['1 avatar 1 text']:
        a = f"""
@commands.command(name='{m}', aliases=['{m}fy', '{m}ly'])
async def _{m}(self, ctx, pic=None, *, text=None):
    {doc}
        {cmd}{m} [user] [text]

    {m} someone.
    {doc}
    user = None
    if not pic:
        user = ctx.author
    embed = discord.Embed()
    embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar_url)
    if not user:
        if ctx.message.mentions:
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

    if pic:
        pic = pic.strip('<>')

    if user:
        pic = str(user.avatar_url_as(format='png'))
    elif not get_image_from_url(pic):
        text = (pic if pic else '') + ' ' + (text if text else '')
        pic = str(ctx.author.avatar_url_as(format='png'))

    img = await self.get_meme_image('{m}', url=pic, text=text, timeout=20)
    embed.set_image(url=f"attachment://%s" % img.filename)
    embed.set_footer(text="Powered by DANK MEMER IMGEN")

    try:
        await ctx.send(file=img, embed=embed)
    except discord.Forbidden:
        await ctx.send(get_str(ctx, "need-embed-permission"))
        """
        exec(a)

    for m in cmd_meme['1 avatar 1 text 1 username']:
        a = f"""
@commands.command(name='{m}', aliases=['{m}fy', '{m}ly'])
async def _{m}(self, ctx, pic=None, *, text: str = None):
    {doc}
        {cmd}{m} [user] [text]

    {m} someone.
    {doc}
    user = None
    if not pic:
        user = ctx.author
    embed = discord.Embed()
    embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar_url)
    if not user:
        if ctx.message.mentions:
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

    if pic:
        pic = pic.strip('<>')

    if user:
        pic = str(user.avatar_url_as(format='png'))
    elif not get_image_from_url(pic):
        text = (pic if pic else '') + ' ' + (text if text else '')
        user = ctx.author
        pic = str(user.avatar_url_as(format='png'))

    img = await self.get_meme_image('{m}', url=pic, username1=user.name, text=text, timeout=20)
    embed.set_image(url=f"attachment://%s" % img.filename)
    embed.set_footer(text="Powered by DANK MEMER IMGEN")

    try:
        await ctx.send(file=img, embed=embed)
    except discord.Forbidden:
        await ctx.send(get_str(ctx, "need-embed-permission"))
        """
        exec(a)

    @commands.command()
    async def hentai(self, ctx):
        """
            {command_prefix}hentai

        Displays a random hentai gif.
        """
        if ctx.guild and not ctx.channel.is_nsfw():
            return await ctx.send(get_str(ctx, "need-nsfw-channel-to-be-used"))
        embed = discord.Embed()
        embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar_url)
        img = await self.get_image_ksoft('hentai_gif')
        embed.set_image(url=img)
        embed.set_footer(text="Powered by KSoft.Si API")
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.command(aliase=["inu"])
    async def dog(self, ctx):
        """
            {command_prefix}dog

        {help}
        """
        image = await self.bot.weebsh.get_random(image_type="animal_dog")
        embed = discord.Embed().set_image(url=image)
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.command()
    async def cat(self, ctx):
        """
            {command_prefix}cat

        {help}
        """
        image = await self.bot.weebsh.get_random(image_type="animal_cat")
        embed = discord.Embed().set_image(url=image)
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.command(aliases=["catgirl", "catgirls", "nya", "nyah", "nyan"])
    async def neko(self, ctx):
        """
            {command_prefix}neko

        Displays a random neko image.
        """
        nsfw = 1
        if ctx.guild and ctx.channel.is_nsfw():
            nsfw = 3
        image = await self.bot.weebsh.get_random(image_type="neko", nsfw=nsfw)
        embed = discord.Embed().set_image(url=image)
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.command()
    async def bite(self, ctx, target: discord.Member):
        """
            {command_prefix}bite [user]

        Allows to bite someone.
        """
        author = ctx.author
        if target == ctx.author:
            if await is_lover(self.bot, ctx.author):
                author = ctx.me
            else:
                return await ctx.send(get_str(ctx, "cmd-weeb-alone"))
        if target == ctx.me and not await is_lover(self.bot, ctx.author):
            return await ctx.send(get_str(ctx, "cmd-weeb-dont-touch-me"))
        image = await self.bot.weebsh.get_random(image_type="bite")
        embed = discord.Embed(description=get_str(
            ctx, "cmd-bite").format(f'**{target.name}**', f'**{author.name}**'))
        embed = embed.set_image(url=image)
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.command(aliases=["look", "watch"])
    async def stare(self, ctx, target: discord.Member):
        """
            {command_prefix}stare [user]

        Allows to stare someone.
        """
        author = ctx.author
        if target == ctx.author:
            return await ctx.send(get_str(ctx, "cmd-weeb-alone"))
        pic = await self.bot.weebsh.get_random(image_type="stare")
        embed = discord.Embed(description=get_str(
            ctx, "cmd-stare").format(f'**{author.name}**', f'**{target.name}**'))
        embed.set_image(url=pic)
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.command()
    async def tickle(self, ctx, target: discord.Member):
        """
            {command_prefix}trickle [user]

        Allows to tickle someone.
        """
        author = ctx.author
        if target == ctx.author:
            if await is_lover(self.bot, ctx.author):
                author = ctx.me
            else:
                return await ctx.send(get_str(ctx, "cmd-weeb-alone"))
        if target == ctx.me and not await is_lover(self.bot, ctx.author):
            return await ctx.send(get_str(ctx, "cmd-weeb-dont-touch-me"))
        pic = await self.bot.weebsh.get_random(image_type="tickle")
        embed = discord.Embed(description=get_str(
            ctx, "cmd-tickle").format(f'**{target.name}**', f'**{author.name}**'))
        embed.set_image(url=pic)
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.command()
    async def cuddle(self, ctx, target: discord.Member):
        """
            {command_prefix}cuddle [user]

        Allows to cuddle someone.
        """
        author = ctx.author
        if target == ctx.author:
            if await is_lover(self.bot, ctx.author):
                author = ctx.me
            else:
                return await ctx.send(get_str(ctx, "cmd-weeb-alone"))
        if target == ctx.me and not await is_lover(self.bot, ctx.author):
            return await ctx.send(get_str(ctx, "cmd-weeb-dont-touch-me"))
        pic = await self.bot.weebsh.get_random(image_type="cuddle")
        embed = discord.Embed(description=get_str(
            ctx, "cmd-cuddle").format(f'**{target.name}**', f'**{author.name}**'))
        embed.set_image(url=pic)
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.command()
    async def kiss(self, ctx, target: discord.Member):
        """
            {command_prefix}kiss [user]

        Allows to kiss someone.
        """
        author = ctx.author
        if target == ctx.author:
            if await is_lover(self.bot, ctx.author):
                author = ctx.me
            else:
                return await ctx.send(get_str(ctx, "cmd-weeb-alone"))
        if target == ctx.me and not await is_lover(self.bot, ctx.author):
            return await ctx.send(get_str(ctx, "cmd-weeb-dont-touch-me"))
        pic = await self.bot.weebsh.get_random(image_type="kiss")
        embed = discord.Embed(description=get_str(
            ctx, "cmd-kiss").format(f'**{target.name}**', f'**{author.name}**'))
        embed.set_image(url=pic)
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.command()
    async def pat(self, ctx, target: discord.Member):
        """
            {command_prefix}pat [user]

        Allows to pat someone.
        """
        author = ctx.author
        if target == ctx.author:
            if await is_lover(self.bot, ctx.author):
                author = ctx.me
            else:
                return await ctx.send(get_str(ctx, "cmd-weeb-alone"))
        if target == ctx.me and not await is_lover(self.bot, ctx.author):
            return await ctx.send(get_str(ctx, "cmd-weeb-dont-touch-me"))
        pic = await self.bot.weebsh.get_random(image_type="pat")
        embed = discord.Embed(description=get_str(
            ctx, "cmd-pat").format(f'**{target.name}**', f'**{author.name}**'))
        embed.set_image(url=pic)
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.command()
    async def lick(self, ctx, target: discord.Member):
        """
            {command_prefix}lick [user]

        Allows to lick someone.
        """
        author = ctx.author
        if target == ctx.author:
            if await is_lover(self.bot, ctx.author):
                author = ctx.me
            else:
                return await ctx.send(get_str(ctx, "cmd-weeb-alone"))
        if target == ctx.me and not await is_lover(self.bot, ctx.author):
            return await ctx.send(get_str(ctx, "cmd-weeb-dont-touch-me"))
        pic = await self.bot.weebsh.get_random(image_type="lick")
        embed = discord.Embed(description=get_str(
            ctx, "cmd-lick").format(f'**{target.name}**', f'**{author.name}**'))
        embed.set_image(url=pic)
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.command()
    async def hug(self, ctx, target: discord.Member):
        """
            {command_prefix}hug [user]

        Allows to hug someone.
        """
        author = ctx.author
        if target == ctx.author:
            if await is_lover(self.bot, ctx.author):
                author = ctx.me
            else:
                return await ctx.send(get_str(ctx, "cmd-weeb-alone"))
        if target == ctx.me and not await is_lover(self.bot, ctx.author):
            return await ctx.send(get_str(ctx, "cmd-weeb-dont-touch-me"))
        pic = await self.bot.weebsh.get_random(image_type="hug")
        embed = discord.Embed(description=get_str(
            ctx, "cmd-hug").format(f'**{target.name}**', f'**{author.name}**'))
        embed.set_image(url=pic)
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.command()
    async def poke(self, ctx, target: discord.Member):
        """
            {command_prefix}poke [user]

        Allows to poke someone.
        """
        author = ctx.author
        if target == ctx.author:
            if await is_lover(self.bot, ctx.author):
                author = ctx.me
            else:
                return await ctx.send(get_str(ctx, "cmd-weeb-alone"))
        if target == ctx.me and not await is_lover(self.bot, ctx.author):
            return await ctx.send(get_str(ctx, "cmd-weeb-dont-touch-me"))
        pic = await self.bot.weebsh.get_random(image_type="poke")
        embed = discord.Embed(description=get_str(
            ctx, "cmd-poke").format(f'**{target.name}**', f'**{author.name}**'))
        embed.set_image(url=pic)
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.command(aliases=['gifle'])
    async def slap(self, ctx, target: discord.Member):
        """
            {command_prefix}slap [user]

        Allows to slap someone.
        """
        author = ctx.author
        if target == ctx.me and not await is_lover(self.bot, author):
            return await ctx.send(get_str(ctx, "cmd-weeb-dont-touch-me"))
        pic = await self.bot.weebsh.get_random(image_type="slap")
        embed = discord.Embed(description=get_str(
            ctx, "cmd-slap").format(f'**{target.name}**', f'**{author.name}**'))
        if target == ctx.author:
            pic = "https://s.put.re/1JQqwNT.gif"
            embed = discord.Embed(description=get_str(
                ctx, "cmd-slap-yourself").format(f'**{author.name}**'))
        embed.set_image(url=pic)
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.command()
    async def punch(self, ctx, target: discord.Member):
        """
            {command_prefix}punch [user]

        Allows to punch someone.
        """
        author = ctx.author
        if target == ctx.me and not await is_lover(self.bot, author):
            return await ctx.send(get_str(ctx, "cmd-weeb-dont-touch-me"))
        pic = await self.bot.weebsh.get_random(image_type="punch")
        embed = discord.Embed(description=get_str(
            ctx, "cmd-punch").format(f'**{target.name}**', f'**{author.name}**'))
        if target == ctx.author:
            pic = "https://s.put.re/1JQqwNT.gif"
            embed = discord.Embed(description=get_str(
                ctx, "cmd-punch-yourself").format(f'**{author.name}**'))
        embed.set_image(url=pic)
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.command(aliases=["shoot"])
    async def bang(self, ctx, target: discord.Member):
        """
            {command_prefix}shoot [user]

        Allows to shoot someone.
        """
        author = ctx.author
        if target == ctx.author:
            return await ctx.send(get_str(ctx, "cmd-shoot-yourself"))
        if target == ctx.me and not await is_lover(self.bot, author):
            return await ctx.send(get_str(ctx, "cmd-shoot-watora"))
        pic = await self.bot.weebsh.get_random(image_type="bang")
        embed = discord.Embed(description=get_str(
            ctx, "cmd-shoot").format(f'**{author.name}**', f'**{target.name}**'))
        embed.set_image(url=pic)
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.command(aliases=['kancolle'])
    async def hibiki(self, ctx, *, pic=None):
        """
            {command_prefix}hibiki [user]
            {command_prefix}hibiki [url] --url
            {command_prefix}hibiki [text]

        Hibiki holding something.. OwO what's this ?
        """
        await self.iode_gen(ctx, type='hibiki', pic=pic)

    @commands.command()
    async def shy(self, ctx, *, pic=None):
        """
            {command_prefix}shy [user]
            {command_prefix}shy [url] --url
            {command_prefix}shy [text]

        A shy girl holding something.. OwO what's this ?
        """
        await self.iode_gen(ctx, type='shy', pic=pic)

    @commands.command()
    async def searching(self, ctx, *, pic=None):
        """
            {command_prefix}searching [user]
            {command_prefix}searching [url] --url
            {command_prefix}searching [text]

        Searching...
        """
        await self.iode_gen(ctx, type='search', pic=pic)

    @commands.command(aliases=['blue_neko', 'blu_neko', 'blueneko'])
    async def bluneko(self, ctx, *, pic=None):
        """
            {command_prefix}bluneko [user]
            {command_prefix}bluneko [url] --url
            {command_prefix}bluneko [text]

        A blue neko girl holding something.. OwO what's this ?
        """
        await self.iode_gen(ctx, type='blu_neko', pic=pic)

    async def iode_gen(self, ctx, type, *, pic=None):
        user = None
        url = False
        if pic and '--url' in pic:
            url = True
            pic = pic.replace('--url', '')
        elif not pic:
            pic = str(ctx.author.avatar_url_as(format='png'))
            url = True

        embed = discord.Embed()
        embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar_url)

        if ctx.message.mentions:
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
            url = True
            pic = str(user.avatar_url_as(format='png'))

        pic = pic.strip('<>')

        url = f"{self.lazy_api}/{type}{'?text=' if not url else '?image='}{quote(unidecode(pic)) if not url else pic}&mode=fill"

        embed.set_image(url=url)

        embed.set_footer(text="Powered by iode")

        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.is_owner()
    @commands.command()
    async def weebeval(self, ctx, *, stmt: str):
        """
            {command_prefix}weebeval

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


def setup(bot):
    bot.add_cog(Weeb(bot))
