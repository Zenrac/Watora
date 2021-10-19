import re
import pytz
import json
import discord
import asyncio
import inspect
import traceback
import aiohttp

from lxml import etree
from utils.dataIO import dataIO
from discord.ext import commands
from datetime import datetime, timedelta
from urllib.parse import parse_qs, quote_plus
from bs4 import BeautifulSoup
from jikanpy import AioJikan
from utils.watora import get_str, Jikan
from jikanpy.exceptions import JikanException


class Mal(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession(loop=self.bot.loop)
        self.bot.jikan = AioJikan()
        self.temp = None

    def cog_unload(self):
        asyncio.ensure_future(self.bot.jikan.close())
        asyncio.ensure_future(self.session.close())

    def remove_html(self, arg):
        arg = arg.replace("&quot;", "\"").replace(
            "<br />", "").replace("[i]", "*").replace("[/i]", "*")
        arg = arg.replace("&ldquo;", "\"").replace(
            "&rdquo;", "\"").replace("&#039;", "'").replace("&mdash;", "—")
        arg = arg.replace("&ndash;", "–")
        return arg

    @commands.cooldown(rate=1, per=5.0, type=commands.BucketType.user)
    @commands.command(aliases=["infoanime", "animeinfo"])
    async def anime(self, ctx, *, anime: str):
        """
            {command_prefix}anime [anime_title]

        {help}
        """
        fetch = await ctx.send(get_str(ctx, "is-searching"))
        await ctx.trigger_typing()
        found = await self.google_results('anime', anime)
        if not found:
            return await ctx.send(get_str(ctx, "no-result"))
        try:
            selection = await self.bot.jikan.anime(found)
            selection = Jikan(selection)
        except (JikanException, aiohttp.ClientError):
            return await ctx.send(get_str(ctx, "no-result"))

        em = discord.Embed(colour=0x0066CC)
        synopsis = selection.synopsis
        if synopsis:
            synopsis = self.remove_html(synopsis)
            if len(synopsis) > 300:
                em.description = " ".join(synopsis.split(
                    " ")[0:40]) + "[ Read more»](%s)" % selection.url
        em.set_author(name=selection.title, url=selection.url,
                      icon_url='https://i.imgur.com/vEy5Zaq.png')
        if selection.title_english:
            if selection.title_english.lower() not in selection.title.lower():
                em.add_field(name=get_str(ctx, "cmd-anime-english-title"),
                             value=selection.title_english, inline=False)
        try:
            em.add_field(name="{}".format(get_str(ctx, "cmd-anime-episodes") if int(selection.episodes)
                                          > 1 else get_str(ctx, "cmd-anime-episode")), value=selection.episodes)
        except TypeError:
            pass
        em.add_field(name=get_str(ctx, "cmd-anime-type"), value=selection.type)
        em.add_field(name=get_str(ctx, "cmd-anime-ranked"),
                     value=("#" + str(selection.rank)) if selection.rank else 'N/A')
        em.add_field(name=get_str(ctx, "cmd-anime-popularity"), value=("#" +
                                                                       str(selection.popularity)) if selection.popularity else 'N/A')
        score = round((selection.score or 0), 2)
        if score == 0:
            score = "N/A"
        em.add_field(name=get_str(ctx, "cmd-anime-score"), value=score)
        em.set_thumbnail(url=selection.image_url)
        status = selection.status
        em.add_field(name=get_str(ctx, "cmd-anime-status"), value=status)
        aired = selection.aired
        a = getattr(aired, 'from').split('T')[0]
        if aired.to:
            b = getattr(aired, 'to').split('T')[0]
        else:
            b = '?'
        aired = get_str(ctx, "cmd-anime-aired-from", can_owo=False) + " " + \
            a + " " + get_str(ctx, "cmd-anime-to", can_owo=False) + " " + b
        em.set_footer(text=aired)
        try:
            await fetch.delete()
        except discord.HTTPException:
            pass
        try:
            await ctx.send(embed=em)
        except discord.Forbidden:
            return await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.cooldown(rate=1, per=5.0, type=commands.BucketType.user)
    @commands.command(aliases=['airing'])
    async def schedule(self, ctx, day: str = None):
        """
            {command_prefix}schedule (day)

        Returns which animes are scheduled for a day.
        """
        await ctx.trigger_typing()
        days = ('monday', 'tuesday', 'wednesday',
                'thursday', 'friday', 'saturday', 'sunday')
        embed = discord.Embed()
        if not day or day.lower() not in days:
            day = days[datetime.now().day % 7]
        try:
            result = await self.bot.jikan.schedule(day=day)
        except (JikanException, aiohttp.ClientError):
            return await ctx.send(get_str(ctx, "no-result"))
        animes = []
        for a in result[day.lower()]:
            animes.append(f"**[{a['title']}]({a['url']})**")
        animes = '\n'.join(animes)
        day_name = str(day[0].upper() + day[1:])
        embed.description = animes
        embed.title = day_name
        await ctx.send(embed=embed)

    @commands.cooldown(rate=1, per=5.0, type=commands.BucketType.user)
    @commands.command()
    async def mal(self, ctx, username: str = None):
        """
            {command_prefix}mal (username)

        Returns information about a MyAnimeList user.
        """
        if not username:
            username = ctx.author.name
        await ctx.trigger_typing()
        try:
            result = await self.bot.jikan.user(username=username)
        except (JikanException, aiohttp.ClientError):
            return await ctx.send(get_str(ctx, "no-result"))
        result = Jikan(result)
        embed = discord.Embed()
        stats = result.anime_stats
        embed.add_field(name='Completed', value=stats.completed)
        embed.add_field(name='Watching', value=stats.watching)
        embed.add_field(name='On hold', value=stats.on_hold)
        embed.add_field(name='Dropped', value=stats.dropped)
        embed.add_field(name='Plan to Watch', value=stats.plan_to_watch)
        embed.add_field(name='Rewatched', value=stats.rewatched)
        embed.add_field(name='Mean Score', value=stats.mean_score)
        embed.add_field(name='Total', value=stats.total_entries)
        embed.add_field(name='Episodes Watched', value=stats.episodes_watched)
        embed.add_field(name='Days Watched', value=stats.days_watched)

        embed.set_author(name=result.username, url=result.url,
                         icon_url='https://i.imgur.com/vEy5Zaq.png')
        embed.set_thumbnail(url=result.image_url)
        await ctx.send(embed=embed)

    @commands.cooldown(rate=1, per=5.0, type=commands.BucketType.user)
    @commands.command()
    async def manga(self, ctx, *, manga: str):
        """
            {command_prefix}manga [manga_title]

        {help}
        """
        fetch = await ctx.send(get_str(ctx, "is-searching"))
        await ctx.trigger_typing()
        found = await self.google_results('manga', manga)
        if not found:
            return await ctx.send(get_str(ctx, "no-result"))
        try:
            selection = await self.bot.jikan.manga(found)
            selection = Jikan(selection)
        except (JikanException, aiohttp.ClientError):
            return await ctx.send(get_str(ctx, "no-result"))

        em = discord.Embed(colour=0x0066CC)
        synopsis = selection.synopsis
        if synopsis:
            synopsis = self.remove_html(synopsis)
            if len(synopsis) > 300:
                em.description = " ".join(synopsis.split(
                    " ")[0:40]) + "[ Read more»](%s)" % selection.url
        em.set_author(name=selection.title, url=selection.url,
                      icon_url='https://i.imgur.com/vEy5Zaq.png')
        if selection.title_english:
            if selection.title_english.lower() not in selection.title.lower():
                em.add_field(name=get_str(ctx, "cmd-anime-english-title"),
                             value=selection.title_english, inline=False)
        try:
            em.add_field(name="{}".format(get_str(ctx, "cmd-manga-chapters") if int(selection.chapters)
                                          > 1 else get_str(ctx, "cmd-manga-chapter")), value=selection.chapters)
        except TypeError:
            pass
        try:
            em.add_field(name="{}".format(get_str(ctx, "cmd-manga-volumes") if selection.chapters >
                                          1 else get_str(ctx, "cmd-manga-volume")), value=selection.volumes)
        except TypeError:
            pass
        em.add_field(name=get_str(ctx, "cmd-anime-ranked"),
                     value=("#" + str(selection.rank)) if selection.rank else 'N/A')
        em.add_field(name=get_str(ctx, "cmd-anime-popularity"), value=("#" +
                                                                       str(selection.popularity)) if selection.popularity else 'N/A')
        score = round((selection.score or 0), 2)
        if score == 0:
            score = "N/A"
        em.add_field(name=get_str(ctx, "cmd-anime-score"), value=score)
        em.set_thumbnail(url=selection.image_url)
        status = selection.status
        em.add_field(name=get_str(ctx, "cmd-anime-status"), value=status)
        published = selection.published
        if getattr(published, 'from'):
            a = getattr(published, 'from').split('T')[0]
            if published.to:
                b = getattr(published, 'to').split('T')[0]
            else:
                b = '?'
            published = get_str(ctx, "cmd-manga-published-from", can_owo=False) + \
                " " + a + " " + \
                get_str(ctx, "cmd-anime-to", can_owo=False) + " " + b
            em.set_footer(text=published)
        try:
            await fetch.delete()
        except discord.HTTPException:
            pass
        try:
            await ctx.send(embed=em)
        except discord.Forbidden:
            return await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.cooldown(rate=1, per=5.0, type=commands.BucketType.user)
    @commands.command(name="char", aliases=["character", "chara"])
    async def chara(self, ctx, *, chara: str):
        """
            {command_prefix}char [char_name]

        {help}
        """
        fetch = await ctx.send(get_str(ctx, "is-searching"))
        await ctx.trigger_typing()
        found = await self.google_results('character', chara)
        if not found:
            return await ctx.send(get_str(ctx, "no-result"))
        try:
            selection = await self.bot.jikan.character(found)
            selection = Jikan(selection)
        except (JikanException, aiohttp.ClientError):
            return await ctx.send(get_str(ctx, "no-result"))

        em = discord.Embed(colour=0x0066CC)
        try:
            em.add_field(
                name='Anime', value=selection.animeography[0].name, inline=False)
        except (IndexError, AttributeError):
            try:
                em.add_field(
                    name='Manga', value=selection.mangaography[0].name, inline=False)
            except (IndexError, AttributeError):
                pass
        try:
            lenght = len(list(selection.voice_actors))
            va = list(selection.voice_actors)[0].name
            for m in selection.voice_actors:
                if m.language == "Japanese":
                    va = m.name
                    break
        except (IndexError, AttributeError):
            va = "No info"

        em.add_field(name=get_str(ctx, "cmd-char-seiyuu"), value=va)

        try:
            em.add_field(name="{}".format(get_str(ctx, "cmd-char-favorites") if selection.member_favorites >
                                          1 else get_str(ctx, "cmd-char-favorite")), value=selection.member_favorites, inline=False)
        except (IndexError, AttributeError):
            pass
        em.set_image(url=selection.image_url)
        em.set_author(name=selection.name, url=selection.url,
                      icon_url='https://i.imgur.com/vEy5Zaq.png')
        try:
            await fetch.delete()
        except discord.HTTPException:
            pass
        try:
            await ctx.send(embed=em)
        except discord.Forbidden:
            return await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.cooldown(rate=1, per=5.0, type=commands.BucketType.user)
    @commands.command(aliases=["nextepisode", "episodenext"])
    async def nextep(self, ctx, *, anime: str):
        """
            {command_prefix}nextep [anime_title]

        {help}
        """
        search = await ctx.send(get_str(ctx, "is-searching"))
        await ctx.trigger_typing()
        found = await self.google_results('anime', anime)
        if not found:
            return await ctx.send(get_str(ctx, "no-result"))
        try:
            selection = await self.bot.jikan.anime(found)
            anime = Jikan(selection)
        except (JikanException, aiohttp.ClientError):
            return await ctx.send(get_str(ctx, "no-result"))

        if anime.status == "Finished Airing":
            aired = anime.aired
            a = getattr(aired, 'from').split('T')[0]
            if aired.to:
                b = getattr(aired, 'to').split('T')[0]
            else:
                b = '?'
            aired = get_str(ctx, "cmd-anime-aired") + \
                f" : **{a}** " + get_str(ctx, "cmd-anime-to") + f" **{b}**"
            remaining = get_str(ctx, "cmd-nextep-not-airing") + f"\n{aired}"
        else:
            try:
                remaining = await self.get_remaining_time(anime, ctx)
            except ValueError:
                remaining = '?'
        embed = discord.Embed(title=get_str(
            ctx, "cmd-nextep"), description=remaining, color=0x0066CC)
        embed.set_author(name='{}'.format(anime.title), url=anime.url,
                         icon_url='https://i.imgur.com/vEy5Zaq.png')
        embed.set_thumbnail(url=anime.image_url)

        embed.set_footer(text=get_str(ctx, "cmd-anime-aired",
                                      can_owo=False) + " : " + (anime.broadcast or '?'))
        try:
            await search.delete()
        except discord.HTTPException:
            pass
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            return await ctx.send(get_str(ctx, "need-embed-permission"))

    @commands.command()
    @commands.is_owner()
    async def maleval(self, ctx, *, stmt: str):
        """
            {command_prefix}maleval

        Evals something.
        """
        try:
            result = eval(stmt)
            if inspect.isawaitable(result):
                result = await result
                self.temp = result
        except Exception:
            exc = traceback.format_exc().splitlines()
            result = exc[-1]
        return await ctx.send("```py\n--- In ---\n{}\n--- Out ---\n{}\n```".format(stmt, result))

    async def google_results(self, type, query, scd: bool = False):
        """Searchs the id on myanimelist for the query according to its type"""
        try:
            mal_id = await self.bot.jikan.search(search_type=type, query=query)
            mal_id = mal_id['results'][0]['mal_id']
        except (JikanException, KeyError, IndexError):
            if 'manga' in type:
                # This is a custom search including only myanimelist/manga website
                google_key = self.bot.tokens['MANGA']
            elif 'character' in type:
                # This is a custom search key including only myanimelist/character website
                google_key = self.bot.tokens['CHARACTER']
            else:
                # This is a custom search key including only myanimelist/anime website
                google_key = self.bot.tokens['ANIME']

            try:
                search_url = "https://www.googleapis.com/customsearch/v1/{}?q=site:myanimelist.net {} {} ".format('siterestrict' if scd else '', type, query) + "&start=" + '1' + "&key=" + \
                             self.bot.tokens['GOOGLE'] + "&cx=" + google_key
                async with self.session.get(search_url) as r:
                    result = await r.json()
                    result = result['items'][0]['link']
                    mal_id = re.findall(f'/{type}/(\d+)/', result)
                    mal_id = mal_id[0]
            except Exception:
                if not scd:
                    return await self.google_results(type=type, query=query, scd=True)
                return False

        return int(mal_id)

    @staticmethod
    async def get_next_weekday(startdate, day):
        days = {
            "Monday": 0,
            "Tuesday": 1,
            "Wednesday": 2,
            "Thursday": 3,
            "Friday": 4,
            "Saturday": 5,
            "Sunday": 6
        }
        weekday = days[day]
        d = datetime.strptime(startdate, '%Y-%m-%d')
        t = timedelta((7 + weekday - d.weekday()) % 7)
        return (d + t).strftime('%Y-%m-%d')

    async def get_remaining_time(self, anime, ctx):
        if not anime.broadcast:
            return "?"
        time = datetime.strptime(anime.broadcast, '%As at %H:%M (JST)')
        day = anime.broadcast.split(' ')[0][:-1]
        hour = anime.broadcast.split(' (JST)')[0].split(' ')[-1]
        jp_time = datetime.now(pytz.timezone("Japan"))
        air_date = await self.get_next_weekday(jp_time.strftime('%Y-%m-%d'), day)
        time_now = jp_time.replace(tzinfo=None)
        try:
            show_airs = datetime.strptime(
                '{} - {}'.format(air_date, hour), '%Y-%m-%d - %H:%M')
        except ValueError:
            show_airs = datetime.strptime(
                '{} - {}'.format(air_date, hour), '%Y-%m-%d - %H')
        remaining = show_airs - time_now
        if remaining.days < 0:
            return '6 {} {} {} {} {} {}.'.format(get_str(ctx, "cmd-nextep-days"),
                                                 remaining.seconds // 3600, get_str(ctx, "cmd-nextep-hour") if (
                                                     remaining.seconds // 3600) < 2 else get_str(ctx, "cmd-nextep-hours"),
                                                 get_str(ctx, "cmd-nextep-and"), (remaining.seconds // 60) % 60, get_str(ctx, "cmd-nextep-minute") if (remaining.seconds // 3600) < 2 else get_str(ctx, "cmd-nextep-minutes"))
        else:
            return '{} {} {} {} {} {} {}.'.format(remaining.days, get_str(ctx, "cmd-nextep-day") if remaining.days < 2 else get_str(ctx, "cmd-nextep-days"),
                                                  remaining.seconds // 3600, get_str(ctx, "cmd-nextep-hour") if (
                                                      remaining.seconds // 3600) < 2 else get_str(ctx, "cmd-nextep-hours"),
                                                  get_str(ctx, "cmd-nextep-and"), (remaining.seconds // 60) % 60, get_str(ctx, "cmd-nextep-minute") if (remaining.seconds // 60) % 60 < 2 else get_str(ctx, "cmd-nextep-minutes"))

    def partition(self, lst, n):
        if n > 1:
            division = len(lst) / n
            return [lst[round(division * i):round(division * (i + 1))] for i in range(n)]
        else:
            return [lst]

    def french_time_converter(self, date):
        if not date:
            return "?"
        date = date.strftime("%d-%m-%Y")
        return date


def setup(bot):
    bot.add_cog(Mal(bot))
