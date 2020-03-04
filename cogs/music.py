import re
import os
import bs4
import sys
import math
import shlex
import difflib
import random
import asyncio
import inspect
import aiohttp
import discord
import logging
import lavalink
import traceback

from lavalink.events import PlayerUpdateEvent
from jikanpy.exceptions import JikanException
from time import time as current_time
from itertools import islice
from discord.ext import commands
from datetime import datetime
from async_timeout import timeout as ac_timeout
from collections import Counter, OrderedDict

from utils import checks
from utils.db import SettingsDB
from utils.youtube_api import YoutubeAPI
from utils.spotify import SpotifyError, Spotify
from utils.chat_formatting import Paginator, Equalizer, Lazyer, split_str_lines
from utils.watora import log, owner_id, is_alone, get_server_prefixes, get_image_from_url, is_basicpatron, is_admin, is_patron, is_voter, is_lover, sweet_bar, get_str, format_mentions, def_v, def_time, def_vote, match_local, match_url, time_rx, illegal_char, NoVoiceChannel, Jikan


class BlindTestSong:
    def __init__(self, jikan=None, url: str = None, title: str = None, id: int = None, image_url: str = None):
        self.jikan = jikan
        self.title = title
        self.id = id
        self._titles = [self.title]
        self.url = url
        self.image_url = image_url
        self.alternative_added = False
        self.found = False
        self.found_reason = None
        self.video_url = None
        self.video_name = None

        self.invalid_words = ('tv', 'openings', 'opening', 'part', 'ending', 'op', 'ed', 'full',
                              'lyrics', 'hd', 'official', 'feat', '1080p', '60fps', 'version', 'season')

        self.invalid_separators = [
            ';', ':', '|', '(', ')', '{', '}', '[', ']', '「', '」', ' -', ' -']

    @property
    def is_anime(self):
        return (self.id is not None)

    @property
    def titles(self):
        return self._titles

    async def add_alternative_titles(self, optional=[]):
        if optional:
            if isinstance(optional, list):
                self._titles += optional
            else:
                self._titles += [optional]
        if self.is_anime:
            if not self.alternative_added:
                settings = await SettingsDB.get_instance().get_glob_settings()
                if str(self.id) in settings.cachedanimes:
                    self._titles += settings.cachedanimes[str(self.id)]
                    self.alternative_added = True
                else:
                    for m in range(6):
                        try:
                            selection = await asyncio.wait_for(self.jikan.anime(self.id), timeout=m + 2)
                            break
                        except (asyncio.TimeoutError, JikanException, aiohttp.ClientError):
                            selection = False

                    if selection:
                        selection = Jikan(selection)
                        altenatives = [
                            selection.title, selection.title_english, selection.title_japanese]
                        altenatives += selection.title_synonyms
                        settings.cachedanimes[str(self.id)] = altenatives
                        await SettingsDB.get_instance().set_glob_settings(settings)
                        self._titles += altenatives
                        self.alternative_added = True

        self._titles += [self.title]
        titles = self._titles.copy()

        for m in range(10):
            new_titles = self.generate_anwers(titles)
            if new_titles == titles:
                break
            titles = new_titles

        self._titles = titles

    def generate_anwers(self, titles):
        titles = filter(None, titles)
        titles = [x.lower() for x in titles]
        new_titles = titles.copy()

        for m in titles:

            for separator in self.invalid_separators:
                if separator in m:
                    if len(m.split(separator)[0]) > 2:
                        new_titles.append(m.split(separator)[0].strip())
            for word in m.split(' '):
                if word in self.invalid_words:
                    new_titles.append(m.replace(word, '').strip())
            digit = [int(s) for s in m.split() if s.isdigit()]
            if digit:
                if len(m.split(str(digit[0]))[0]) > 2:
                    new_titles.append(m.split(str(digit[0]))[0].strip())

        titles = new_titles.copy()
        for m in new_titles:
            without = re.sub(r'\W+', ' ', m).strip()
            titles.append(without)

        titles = filter(None, titles)
        return list(set(titles))  # bye bye duplicates


class BlindTest:
    def __init__(self, player):
        self.bot = player.node._manager._lavalink.bot
        self.jikan = self.bot.jikan
        self.player = player
        self.songs = []
        self.points = {}
        self.severity = 100
        self.channel = None
        self.current_song = None
        self.next_song = None
        self.accept_longest_word = False
        self.listening_mode = False
        self.current_task = []
        self.timeout = 120
        self.percentage = '100,0,0'
        self.wait = 5
        self.source = 'ytsearch'

    @property
    def is_running(self):
        return bool(self.songs) or bool(self.next_song and (self.current_song != self.next_song))

    @property
    def partition(self):
        values = [abs(int(m)) for m in self.percentage.split(',')]
        while len(values) < 3:
            values.append(0)
        return ['opening'] * values[0] + ['ending'] * values[1] + ['ost'] * values[2]

    @property
    def bt_channel(self):
        return self.bot.get_channel(int(self.channel))

    @property
    def guild(self):
        return self.bot.get_guild(int(self.player.guild_id))

    def clean_tasks(self):
        for task in self.current_task:
            task.cancel()
        self.current_task = []

    async def stop(self, bypass=False, send_final=True):
        if self.is_running or bypass:
            embed = await self.get_classement()
            if embed.fields:
                embed.title = get_str(
                    self.guild, "cmd-blindtest-final-rank", bot=self.bot)
                await self.bt_channel.send(embed=embed)
            if send_final:
                await self.send_final_embed()
        self.clean_tasks()
        settings = await SettingsDB.get_instance().get_guild_settings(int(self.player.guild_id))
        for k, v in self.points.items():
            settings.points[k] = settings.points.get(k, 0) + v
        await SettingsDB.get_instance().set_guild_settings(settings)
        self.songs = []
        self.points = {}

    async def send_final_embed(self):
        e = discord.Embed(description=get_str(
            self.guild, "cmd-blindtest-enjoyed", bot=self.bot))
        e.description += "\n\n**[{}](https://www.patreon.com/watora)** {}".format(
            get_str(self.guild, "support-watora", bot=self.bot), get_str(self.guild, "support-watora-end", bot=self.bot))
        e.description += '\n' + get_str(self.guild, "suggest-features", bot=self.bot).format(
            f"`{get_server_prefixes(self.bot, self.guild)}suggestion`")
        await self.bt_channel.send(embed=e)

    def pop(self, next=False):
        song = self.songs.pop(random.randrange(len(self.songs)))
        if next:
            self.next_song = song
        else:
            self.current_song = song
        return song

    def get_song_keywords(self):
        if self.current_song.is_anime:
            search_end = ' ' + random.choice(self.partition)
            parts = self.current_song.title.split(':')
            if len(parts) > 1 and len(self.current_song.title.split(':')[0]) > 2:
                if len(self.current_song.title.split(':')[1]) > 40:
                    # Holy shit this is too long.
                    search_beg = self.current_song.title.split(':')[0]
                else:
                    search_beg = self.current_song.title
            else:
                search_beg = self.current_song.title
            return search_beg + search_end
        return self.current_song.url

    def remaining_song(self):
        return len(self.songs)

    async def get_classement(self, embed=None):
        if not embed:
            embed = discord.Embed()
        counter = Counter(self.points)
        classement = OrderedDict(counter.most_common())
        for i, user in enumerate(classement, start=1):
            if len(embed.fields) > 10:
                break
            u = await self.bot.safe_fetch('member', int(user), guild=self.guild)
            if u:
                embed.add_field(name=f'{i}. {u}', value=self.points[user])
        return embed

    def answer_is_valid(self, *, query):
        query = query.lower()
        naked_query = re.sub(r'\W+', ' ', query).strip()
        title = self.current_song.title
        titles = self.current_song.titles

        if query in titles or naked_query in titles:
            return True
        for ti in titles:
            if ti in query or ti in naked_query:
                return True

        if self.accept_longest_word:
            longest = sorted(title.split(' '), key=len)[-1]
            if longest in query or longest in naked_query:
                return True

        for m in titles:
            if (len(m) * (self.severity / 100)) <= len(query):
                if query in m:
                    return True

        for m in titles:
            if ''.join(m.split()) in ''.join(query.split()):
                return True
            if ''.join(m.split()) in ''.join(naked_query.split()):
                return True
        return False


class CustomPlayer(lavalink.DefaultPlayer):
    def __init__(self, guild_id: int, node):
        super().__init__(guild_id, node)

        self.channel_id = None
        self.previous = None
        self.description = None

        self.stop_votes = set()
        self.skip_votes = set()
        self.clear_votes = set()
        self.already_played = set()

        self.auto_paused = False
        self.autoplaylist = None
        self.list = None
        self.authorplaylist = None
        self.npmsg = None
        self.now = None
        self.channel = None
        self.timer_value = def_time  # can be edited in settings.json

        self.blindtest = BlindTest(self)

        asyncio.ensure_future(self.init_with_db(guild_id))

    async def init_with_db(self, guild_id):
        settings = await SettingsDB.get_instance().get_guild_settings(int(guild_id))
        await self.set_volume(settings.volume)

        if settings.timer != def_time:
            if settings.timer or await self.node._manager._lavalink.bot.server_is_claimed(int(guild_id)):
                self.timer_value = settings.timer
            elif not settings.timer:
                del settings.timer
                await SettingsDB.get_instance().set_guild_settings(settings)

        if settings.channel:
            self.channel = settings.channel

    async def play(self, track=None, **kwargs):
        if self.repeat and self.current:
            self.queue.append(self.current)

        self.current = None
        self.last_update = 0
        self.last_position = 0
        self.position_timestamp = 0
        self.paused = False

        if not track:
            if not self.queue:
                await self.stop()
                await self.node._dispatch_event(lavalink.events.QueueEndEvent(self))
                return

            if self.shuffle:
                track = self.queue.pop(randrange(len(self.queue)))
            else:
                track = self.queue.pop(0)

        self.current = track
        if not kwargs:
            kwargs = await self.optional_parameters(track.uri)
        await self.node._send(op='play', guildId=self.guild_id, track=track.track, **kwargs)
        await self.node._dispatch_event(lavalink.events.TrackStartEvent(self, track))

    async def optional_parameters(self, url):
        kwargs = {}
        start_time = re.findall('[&?](t|start|starts|s)=(\d+)', url)
        if start_time:
            kwargs['startTime'] = str(int(start_time[-1][-1]) * 1000)
        end_time = re.findall('[&?](e|end|ends)=(\d+)', url)
        if end_time:
            kwargs['endTime'] = str(int(end_time[-1][-1]) * 1000)

        return kwargs

    async def update_state(self, state: dict):
        """
        Updates the position of the player.
        Parameters
        ----------
        state: dict
            The state that is given to update.
        """
        self.last_update = current_time() * 1000
        self.last_position = state.get('position', 0)
        self.position_timestamp = state.get('time', 0)

        try:
            await self.update_title()
        except Exception:  # I don't want the task to finish because of a stupid thing
            pass

        event = PlayerUpdateEvent(
            self, self.last_position, self.position_timestamp)
        await self.node._dispatch_event(event)

    async def update_title(self):
        music_cog = self.node._manager._lavalink.bot.cogs.get('Music')
        if self.current:
            timestamps = self.current.extra.get('timestamps', [])
            for timestamp in reversed(timestamps):
                time, title = timestamp
                milliseconds = (
                    sum(x * int(t) for x, t in zip([1, 60, 3600], reversed(time.split(":")))) * 1000)
                if self.last_position >= milliseconds:
                    title = title.strip()
                    if self.current.title != title:
                        self.current.title = title
                        if music_cog:
                            await music_cog.reload_np_msg(self)
                    break

    async def stop(self):
        """ Stops the player. Overrided to remove the eq reset"""
        await self.node._send(op='stop', guildId=self.guild_id)
        self.current = None


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.temp = None
        self.timeout_tasks = {}
        self.inact_tasks = {}
        self._cd = commands.CooldownMapping.from_cooldown(
            1.0, 600.0, commands.BucketType.user)
        self._skip_cd = commands.CooldownMapping.from_cooldown(
            1.0, 1.5, commands.BucketType.guild)
        self.session = aiohttp.ClientSession(loop=self.bot.loop)
        self.youtube_api = YoutubeAPI(
            youtube_token=self.bot.tokens['YT_KEY'], loop=self.bot.loop, aiosession=self.session)

        self.list_radiolist = {
            'Monstercat': 'https://www.twitch.tv/monstercat',
            'RelaxBeats': 'https://www.twitch.tv/relaxbeats',
            'Listen Moe': 'https://listen.moe/fallback',
            'Listen Moe K-POP': 'https://listen.moe/kpop/fallback'
        }

        self.bassboost_levels = {
            'OFF': [(0, 0), (1, 0)],
            'LOW': [(0, 0.25), (1, 0.15)],
            'MEDIUM': [(0, 0.50), (1, 0.25)],
            'HIGH': [(0, 0.75), (1, 0.50)],
            'INSANE': [(0, 1), (1, 0.75)],
            'WTF': [(0, 1), (1, 1)]
        }

        self.parameters = {
            'difficulty': '[0-6]',
            'mal': '\S+',
            'argument': 'all|completed|watching|onhold|dropped|ptw',
            'remove': lambda m: all([c in ('completed', 'watching', 'onhold', 'dropped', 'ptw', 'nothing') for c in m.split(',')]),
            'autoplaylist': '\S+',
            'longestword': 'true|false',
            'listening': 'true|false',
            'timeout': lambda m: 2 < int(m) and int(m) <= 300,
            'severity': lambda m: 0 < int(m) and int(m) <= 100,
            'percentage': lambda m: sum((abs(int(c)) for c in m.split(','))) == 100,
            'wait': lambda m: 0 <= int(m) and int(m) <= 30,
            'source': '\S+'
        }

        self.anime_status = (
            'all', 'watching', 'completed', 'onhold', 'dropped', 'plantowatch', 'ptw', 'nothing'
        )

        # Lavalink
        if not hasattr(bot, 'lavalink'):
            asyncio.ensure_future(self.prepare_lavalink())
        else:
            self.bot.lavalink.add_event_hook(self.track_hook)  # restarting cog

        if not hasattr(bot, 'top_animes'):
            self.bot.top_animes = {}
            asyncio.ensure_future(self.prepare_bt_difficulties())

        # Spotify
        asyncio.ensure_future(self.prepare_spotify_integration())

    def cog_unload(self):
        asyncio.ensure_future(self.session.close())
        self.bot.lavalink._event_hooks.clear()

    # TODO: Move it to utils
    def get_timestamps(self, desc):
        """ Extract timestamps from a description and removes extra timestamps """
        ts = re.findall(r'(.*?((?:\d{1,2}:){1,}\d\d)\b.*)', desc)
        newTimestamps = []
        for a, b in ts:
            if newTimestamps:
                before_seconds = seconds
                seconds = self.get_seconds(b)
                if before_seconds >= seconds:
                    break
            else:
                seconds = self.get_seconds(b)
            title = ' '.join(a.replace(b, '').split())
            newTimestamps.append((b, title))
        return newTimestamps

    # TODO: Move it to utils
    def get_seconds(self, ts):
        return sum(x * int(t) for x, t in zip([1, 60, 3600], reversed(ts.split(":"))))

    async def prepare_spotify_integration(self):
        if self.bot.tokens['SPOTIFY_SECRET'] and self.bot.tokens['SPOTIFY_ID']:
            try:
                self.bot.spotify = Spotify(
                    self.bot.tokens['SPOTIFY_ID'], self.bot.tokens['SPOTIFY_SECRET'], aiosession=self.bot.session)
                await self.bot.spotify.get_token()  # validate token
            except aiohttp.ClientError:
                log.warning('Your Spotify credentials could not be validated. Please make sure your client ID and client secret '
                            'in the config file are correct. Disabling Spotify integration for this session.')
                self.bot.spotify = None
            else:
                if not self.bot.spotify.token:
                    log.warning('Your Spotify credentials could not be validated. Please make sure your client ID and client secret '
                                'in the config file are correct. Disabling Spotify integration for this session.')
                    self.bot.spotify = None
                else:
                    log.info(
                        'Authenticated with Spotify successfully using client ID and secret.')

    async def prepare_bt_difficulties(self):
        top_animes = {}
        top_animes['top'] = []
        difficulty = 1
        log.info('Preparing anime to the cache...')
        while difficulty < 20:
            for m in range(10):
                try:
                    anime_list = await asyncio.wait_for(self.bot.jikan.top(type='anime', page=difficulty), timeout=m + 2)
                except (asyncio.TimeoutError, aiohttp.ClientError, JikanException):
                    await asyncio.sleep(m)
                else:
                    to_add = [m for m in anime_list['top']
                              if m['type'] == 'TV']
                    top_animes['top'].extend(to_add)
                    difficulty += 1
                    break
        if not self.bot.top_animes or len(self.bot.top_animes['top']) > len(top_animes['top']):
            self.bot.top_animes = top_animes
            log.info(
                f'{len(top_animes["top"])} songs have been added to the cache.')

        settings = await SettingsDB.get_instance().get_glob_settings()
        if not settings.animes or (len(settings.animes['top']) < len(self.bot.top_animes['top'])):
            settings.animes = self.bot.top_animes
            await SettingsDB.get_instance().set_glob_settings(settings)
            log.info(
                f'{len(top_animes["top"])} songs have been added to the database.')
        else:
            self.bot.top_animes = settings.animes

    async def prepare_lavalink(self):
        await self.bot.wait_until_ready()
        log.info("Preparing lavalink...")

        self.bot.lavalink = lavalink.Client(
            bot=self.bot, loop=self.bot.loop, player=CustomPlayer, shard_count=self.bot.shard_count, user_id=self.bot.user.id)

        eu = self.bot.tokens['NODE_EU']
        us = self.bot.tokens['NODE_US']
        asia = self.bot.tokens['NODE_ASIA']
        premium = self.bot.tokens['NODE_PREMIUM']

        resume_config = {
            'resume_key': self.bot.tokens["LAVALINK_RESUME_KEY"] + str(sum(self.bot.shards.keys())),
            'resume_timeout': 600
        }

        # Main Nodes

        # self.bot.lavalink.add_node(region='asia', host=asia['HOST'], password=asia['PASSWORD'], name='Asia', **resume_config)
        # self.bot.lavalink.add_node(
        #     region='eu', host=eu['HOST'], password=eu['PASSWORD'], name='Europe', port=2333, **resume_config)
        self.bot.lavalink.add_node(
            region='us', host=us['HOST'], password=us['PASSWORD'], name='America', port=2333, **resume_config)

        # Premium Nodes
        self.bot.lavalink.add_node(
            region='us', host=premium['HOST'], password=premium['PASSWORD'], name='Premium', port=2333, is_perso=True, **resume_config)

        self.bot.add_listener(
            self.bot.lavalink.voice_update_handler, 'on_socket_response')

        self.bot.lavalink.add_event_hook(self.track_hook)

        # self.prepare_lavalink_logger(level_console=logging.INFO, level_file=logging.WARNING)
        log.info("Lavalink is ready.")

    async def ensure_node_connection(self, ip, port, password):
        headers = {
            'Authorization': password,
            'Num-Shards': str(self.bot.shard_count),
            'User-Id': str(self.bot.user.id)
        }

        try:
            ws = await asyncio.wait_for(self.session.ws_connect('ws://{}:{}'.format(str(ip), str(port)), headers=headers), timeout=2)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return False

        await ws.close()
        return True

    async def add_custom_node(self, name, info=None, settings=None):
        node = self.bot.lavalink.node_manager.get_node_by_name(name, True)
        if not node:
            if not info:
                if not settings:
                    settings = await SettingsDB.get_instance().get_glob_settings()
                info = settings.custom_hosts.get(name, False)
                if not info:
                    return

            if not await self.ensure_node_connection(info['host'], info['port'], info['password']):
                return False

            resume_config = {
                'resume_key': name + str(sum(self.bot.shards.keys())),
                'resume_timeout': 600
            }

            self.bot.lavalink.add_node(
                region=None, host=info['host'], password=info['password'], name=name, port=info['port'], is_perso=True, **resume_config)

        return True

    async def track_hook(self, event):
        if isinstance(event, lavalink.events.TrackStartEvent):

            # Clear votes
            event.player.stop_votes.clear()
            event.player.clear_votes.clear()
            event.player.skip_votes.clear()

            event.player.previous = event.player.now
            event.player.now = event.player.current

            # Send now playing message
            channel = self.bot.get_channel(event.player.channel)
            gid = int(event.player.guild_id)

            # cancel inact task
            if gid in self.inact_tasks:
                self.inact_tasks[gid].cancel()
                self.inact_tasks.pop(gid)

            if not event.player.blindtest.is_running or event.player.blindtest.listening_mode:
                thumb = await self.get_thumbnail(event.track, event.player, new=True)

            if not channel:
                return

            if "listen.moe" in event.track.uri.lower():
                if 'kpop' in event.track.uri.lower():
                    color = int("3CA4E9", 16)
                    title = self.get_current_listen_moe(kpop=True)
                else:
                    color = int("FF015B", 16)
                    title = self.get_current_listen_moe()
            elif 'monstercat' in event.track.uri.lower() and 'twitch' in event.track.uri.lower():
                color = int("FF015B", 16)
                title = self.get_current_mc()
            else:
                color = self.get_color(channel.guild)
                title = event.track.title

            embed = discord.Embed(colour=color, title=f"**{title}**")

            embed.url = event.track.uri

            if thumb:
                embed.set_image(url=thumb)

            requester = await self.bot.safe_fetch('member', event.track.requester, guild=channel.guild)
            duration = lavalink.utils.format_time(
                event.track.duration).lstrip('0').lstrip(':')

            if not event.track.stream:
                embed.description = f'{"🔁 " if event.player.repeat else ""}{get_str(channel.guild, "music-duration", bot=self.bot)}: {duration}'

            if requester:
                embed.set_author(
                    name=requester.name, icon_url=requester.avatar_url or requester.default_avatar_url, url=event.track.uri)

            if event.player.node.is_perso:
                name = await self.bot.safe_fetch('user', event.player.node.name) or event.player.node.name
                # TODO: Translations
                embed.set_footer(text=f"Hosted by {name}")

            asyncio.ensure_future(self.send_new_np_msg(
                event.player, channel, new_embed=embed))

        elif isinstance(event, lavalink.events.QueueEndEvent):
            # TODO: Rewrite this
            if not await self.blindtest_loop(event.player, check=True):
                if not await self.autoplaylist_loop(event.player):
                    if not await self.autoplay_loop(event.player):
                        if event.player.timer_value is not False:  # Can be 0
                            gid = int(event.player.guild_id)
                            if gid not in self.inact_tasks:
                                task = asyncio.ensure_future(
                                    self.inact_task(event.player))
                                self.inact_tasks[gid] = task

        elif isinstance(event, lavalink.events.TrackEndEvent):
            pass

        elif isinstance(event, lavalink.events.TrackExceptionEvent):
            pass

        elif isinstance(event, lavalink.events.TrackStuckEvent):
            log.warning(f"{event.player.guild_id} is stuck !")

    async def delete_old_npmsg(self, player):
        """Deletes the old np messages or not without raison a discord exception"""
        if player.npmsg:
            try:
                await player.npmsg.delete()
            except discord.HTTPException:
                pass

    async def connect_player(self, ctx, player, channel_id: int, settings=None):
        """ Connects a player to a channel. """
        if not settings:
            settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        if settings.channel:
            player.channel = ctx.guild.get_channel(
                settings.channel).id if ctx.guild.get_channel(settings.channel) else ctx.channel.id
        elif settings.channel is None:
            player.channel = ctx.channel.id
        else:
            player.channel = None

        await player.connect(channel_id)

    async def estimate_time_until(self, player, position):
        """
            Estimates the time till the queue will 'position'
        """
        estimated_time = sum(e.duration for e in islice(
            player.queue, position - 1) if not e.stream)

        # When the player plays a song, it eats the first playlist item, so we just have to add the time back
        if player.is_playing and player.current and not player.current.stream:
            # avoid stream to returns neg values
            estimated_time += max(player.current.duration - player.position, 0)

        return estimated_time

    async def get_position_in_queue(self, ctx, player):
        """Gets a song position in queue"""
        time_until = None
        if not player.queue:
            if player.is_playing:
                position = 1
            else:
                position = get_str(ctx, "music-upnext")
        else:
            position = len(player.queue) + 1

        if type(position) != str:
            time_until = await self.estimate_time_until(player, position)
            time_until = lavalink.utils.format_time(
                time_until).lstrip('0').lstrip(':')

        return position, time_until

    async def get_thumbnail(self, track, player, new: bool = False):
        """Gets the best thumbnail for a song"""
        if track != player.current:
            return player.current.artwork if player.current else track.artwork

        if not new:
            return player.current.artwork if player.current else track.artwork

        thumb = track.artwork
        uri = track.uri.lower()

        if 'youtube' in uri:
            new_thumb, desc = await self.youtube_api.get_youtube_infos(track.identifier)
            if player.current and desc:
                player.current.extra['timestamps'] = self.get_timestamps(desc)
            if new_thumb:  # Do not replace if it's None.
                thumb = new_thumb
        elif 'twitch' in uri:
            if 'monstercat' in uri:
                thumb = 'https://s.put.re/5E4pWAe.jpg'
            elif 'relaxbeats' in uri:
                thumb = 'https://s.put.re/DJ9X959.gif'
        elif 'listen.moe' in uri:
            thumb = 'https://s.put.re/SBvKRzf.png'
            if 'kpop' in uri:
                thumb = 'https://s.put.re/hqkaco3.png'
        elif 'soundcloud' in uri:
            thumb = track.artwork.replace('large', 't250x250')
        if not thumb:
            thumb = 'https://s.put.re/Jkrar3b.jpg'

        if player.current:
            player.current.artwork = thumb
        return thumb

    async def cog_command_error(self, ctx, error):
        """A local error handler for all errors arising from commands in this cog"""
        if isinstance(error, NoVoiceChannel):
            try:
                return await ctx.send(error, delete_after=20)
            except discord.HTTPException:
                pass

    async def cog_check(self, ctx):
        """A check which applies to all commands in Music"""
        if 'hostconfig' in str(ctx.command):  # TODO: Remove this after moving commands to an other cog
            return True
        if isinstance(ctx.channel, discord.abc.PrivateChannel) and not ctx.author.id == owner_id:
            await ctx.send('```py\n{}\n```'.format(get_str(ctx, "music-not-in-dm")))
            raise commands.errors.CommandNotFound  # because it avoid a checkfailure message
        return True

    async def prepare_url(self, query, node=None, source='ytsearch'):
        """Prepares the url if it's an url or not etc... Ensures dict."""
        settings = await SettingsDB.get_instance().get_glob_settings()
        default_source = settings.source

        if source == 'ytsearch' and (not node or not node.is_perso):
            source = default_source

        if not match_url(query):
            if query.lower().startswith(('listen.moe', 'listen moe', 'listenmoe')):
                if 'k' in query.lower():
                    return await self.prepare_url(query=self.list_radiolist['Listen Moe K-POP'], node=node)
                return await self.prepare_url(query=self.list_radiolist['Listen Moe'], node=node)
            if query.lower() == 'monstercat':
                return await self.prepare_url(query=self.list_radiolist['Monstercat'], node=node)
            query = self.remove_optional_parameter(query)
            if match_local(query):
                new = query.replace('/', '\\')  # local file
            else:
                new = f'{source}:{query}'
            results = await self.bot.lavalink.get_tracks(query=new, node=node)
            if not results or not isinstance(results, dict) or not results['tracks']:
                songs = await self.youtube_api.youtube_search(query)
                if songs:
                    log.debug(
                        f'Found result from youtube-api : {songs} for query: {query}')
                    try:
                        results = await self.bot.lavalink.get_tracks(songs[0]['uri'], node=node)
                    except asyncio.TimeoutError:
                        results = {'playlistInfo': {},
                                   'loadType': 'NO_MATCHES', 'tracks': []}
        else:
            if 'listen.moe' in query.lower() and 'fallback' not in query.lower():
                if 'kpop' in query.lower():
                    return await self.prepare_url(query=self.list_radiolist['Listen Moe K-POP'], node=node)
                return await self.prepare_url(query=self.list_radiolist['Listen Moe'], node=node)

            # if the user selected a song, don't load the whole playlist
            if "&list" in query.lower() and "&index" in query.lower():
                query = query.split('&')[0]
            try:
                results = await self.bot.lavalink.get_tracks(query, node=node)
            except asyncio.TimeoutError:
                results = {'playlistInfo': {},
                           'loadType': 'NO_MATCHES', 'tracks': []}
        if isinstance(results, dict):
            return results

        return {'playlistInfo': {}, 'loadType': 'NO_MATCHES', 'tracks': []}

    async def prepare_spotify(self, ctx, query, node=None, infinite_loop=False, max_tracks: int = 100):
        """ Prepares a Spotify URI or URL to be played with lavalink"""
        # Convert URL to URI
        if match_url(query) and 'open.spotify' in query:
            query += "?"  # To difficult/long to explain why
            base = "spotify:"
            for m in ''.join(query.split('spotify.com/')[1:]).split("/"):
                base += f"{m}:"
            query = base.split("?")[0]
        results = {'playlistInfo': {}, 'loadType': 'NO_MATCHES', 'tracks': []}

        if query.startswith('spotify:'):  # probably a spotify URI
            if self.bot.spotify:
                original_query = query
                query = query.split(":", 1)[1]
                if query.startswith('track:'):
                    query = query.split(":", 1)[1]
                    res = await self.bot.spotify.get_track(query)
                    query = res['artists'][0]['name'] + ' ' + res['name']
                    song = await self.prepare_url(query=query, node=node)
                    if song and song['tracks']:
                        results['tracks'].append(song['tracks'][0])
                        results['loadType'] = "TRACK_LOADED"

                elif query.startswith('album:'):
                    query = query.split(":", 1)[1]
                    res = await self.bot.spotify.get_album(query)
                    procmesg = await ctx.send(get_str(ctx, "music-spotify-processing-a").format(f"`{res['name']}`"))
                    base_content = procmesg.content
                    tracks_found = len(res['tracks']['items'])
                    for num, i in enumerate(res['tracks']['items'][:max_tracks], start=1):
                        try:
                            query = i['name'] + ' ' + i['artists'][0]['name']
                            log.debug('Processing {0}'.format(query))
                            song = await self.prepare_url(query=query, node=node)
                            results['tracks'].append(song['tracks'][0])
                            results['loadType'] = "PLAYLIST_LOADED"
                            results['playlistInfo'] = {
                                'selectedTrack': -1, 'name': res['name']}
                        except (KeyError, IndexError, TypeError):
                            tracks_found -= 1
                        if len(res['tracks']['items']) != tracks_found:
                            results['failed'] = len(
                                res['tracks']['items']) - tracks_found

                        if num % 5 == 0 or num == tracks_found:
                            await procmesg.edit(content=f"`{num}/{tracks_found}` - {base_content}")

                    try:
                        await procmesg.delete()
                    except discord.HTTPException:
                        pass
                    if tracks_found == 0:
                        raise SpotifyError(
                            get_str(ctx, "music-spotify-all-failed"))

                elif query.startswith('artist:') and not infinite_loop:
                    query = query.split(":", 1)[1]
                    res = await self.bot.spotify.get_artist_albums(query)
                    items = res['items']
                    albums = [
                        item for item in items if item['album_type'] == 'album']
                    if albums:
                        album = random.choice(albums)
                    elif items:
                        album = random.choice(items)
                    else:
                        raise SpotifyError(
                            get_str(ctx, "music-spotify-not-supported"))
                    return await self.prepare_spotify(ctx, album['uri'], infinite_loop=True)

                elif query.startswith('user:') and 'playlist:' in query:
                    user = query.split(":",)[1]
                    query = query.split(":", 3)[3]
                    res = await self.bot.spotify.get_playlist(user, query)
                    procmesg = await ctx.send(get_str(ctx, "music-spotify-processing-p").format(f"`{res['name']}`"))
                    base_content = procmesg.content
                    tracks_found = len(res['tracks']['items'])
                    for num, i in enumerate(res['tracks']['items'][:max_tracks], start=1):
                        try:
                            query = i['track']['name'] + ' ' + \
                                i['track']['artists'][0]['name']
                            log.debug('[Spotify] Processing {0}'.format(query))
                            song = await self.prepare_url(query=query, node=node)
                            results['tracks'].append(song['tracks'][0])
                            results['loadType'] = "PLAYLIST_LOADED"
                            results['playlistInfo'] = {
                                'selectedTrack': -1, 'name': res['name']}
                            log.debug(
                                '[Spotify] Processing finished for {0}'.format(query))
                        except (KeyError, IndexError, TypeError):
                            tracks_found -= 1
                        if len(res['tracks']['items']) != tracks_found:
                            results['failed'] = len(
                                res['tracks']['items']) - tracks_found

                        if num % 5 == 0 or num == tracks_found:
                            await procmesg.edit(content=f"`{num}/{tracks_found}` - {base_content}")

                    try:
                        await procmesg.delete()
                    except discord.HTTPException:
                        pass
                    if tracks_found == 0:
                        raise SpotifyError(
                            get_str(ctx, "music-spotify-all-failed"))
                elif query.startswith('playlist:') and not infinite_loop:
                    query = query.split(":", 1)[1]
                    res = await self.bot.spotify.get_playlist_tracks(query)
                    author = res['items'][0]['added_by']['uri']
                    query = original_query.replace('spotify:', f'{author}:')
                    return await self.prepare_spotify(ctx, query, infinite_loop=True)
                else:
                    raise SpotifyError(
                        get_str(ctx, "music-spotify-not-supported"))

                log.debug('[Spotify] Process finished.')
                return results
            else:
                raise SpotifyError(get_str(ctx, "music-spotify-disabled"))
        else:
            raise SpotifyError(get_str(ctx, "music-spotify-not-supported"))

    async def autoplaylist_loop(self, player, error_count=0):
        """Autoplaylist auto-add song loop"""
        if player.connected_channel and player.is_connected and not player.is_playing and player.autoplaylist and not player.queue:
            # if not sum(1 for m in player.connected_channel.members if not (m.voice.deaf or m.bot or m.voice.self_deaf)):
            #     log.info("[Autoplaylist] Disabling autoplaylist cus I'm alone.")
            #     player.autoplaylist = None
            #     return False
            if not player.list:
                player.list = player.autoplaylist['songs'].copy()
                player.list.reverse()
            if player.list:
                if len(player.list) > 1 and player.autoplaylist['shuffle']:
                    random.shuffle(player.list)
                    song_url = player.list.pop()
                    if player.now and player.now.uri == song_url:  # avoid the same song to be played twice in a row
                        new = player.list.pop()
                        player.list.append(song_url)
                        song_url = new
                else:
                    song_url = player.list.pop()
                results = await self.prepare_url(query=song_url, node=player.node)
                if results and results['tracks']:
                    track = results['tracks'][0]
                    track = self.prepare_track(track)
                    player.add(requester=player.authorplaylist.id, track=track)
                    if not player.is_playing:  # useless check but who knows ?
                        await self.player_play(player, song_url)
                    return True
                else:
                    try:
                        player.autoplaylist['songs'].remove(song_url)
                    except ValueError:
                        pass
                    if 'removed' in results.get('exception', {}).get('message', '').lower():
                        return await self.autoplaylist_loop(player)
                    if error_count < 3:  # if 3 fails in a row.. stop trying.
                        return await self.autoplaylist_loop(player, error_count=error_count + 1)
        return False

    def find_best_result(self, results):
        not_good = ('amv', ' ep', ' ép', 'trailer', 'openings',
                    'all opening', 'endings', 'scene')
        is_good = ('opening', 'ending', 'ost', 'op', 'ed', 'end')
        best_results = results['tracks'].copy()
        for result in results['tracks']:
            title = result['info']['title']

            if any(m in title.lower() for m in not_good):
                best_results.remove(result)
                continue

            for word in title.split(' '):
                if word.lower() in is_good:
                    return result

            if any(m in title.lower() for m in is_good):
                return result

        return best_results[0]

    async def blindtest_loop(self, player, check=False, error_count=0):
        """Blindtest auto-add song loop"""
        if not player.blindtest.channel:
            return False

        channel = self.bot.get_channel(int(player.blindtest.channel))

        if check and not player.blindtest.listening_mode:
            if player.blindtest.current_song and not player.blindtest.current_song.found:
                player.blindtest.current_song.found = True
                if channel and player.blindtest.current_task:
                    await self.blindtest_embed(p=player, channel=channel)
                    if not player.blindtest.is_running:
                        await player.blindtest.stop(bypass=True)

            player.blindtest.clean_tasks()

        if player.blindtest.is_running and player.is_connected and player.connected_channel and not player.is_playing and not player.queue:
            if not player.blindtest.listening_mode:
                asyncio.ensure_future(self.delete_old_npmsg(player))
                player.channel = None
            if not sum(1 for m in player.connected_channel.members if not (m.voice.deaf or m.bot or m.voice.self_deaf)):
                log.debug("[Blintest] Disabling blindtest cus I'm alone on {}.".format(
                    player.connected_channel.guild.name))
                await player.blindtest.stop()
                return False
            if player.blindtest.next_song:
                song = player.blindtest.next_song
                player.blindtest.current_song = player.blindtest.next_song
            else:
                song = player.blindtest.pop()
            player.blindtest.next_song = None
            song_url = player.blindtest.get_song_keywords()
            results = await self.prepare_url(query=song_url, node=player.node, source=player.blindtest.source)
            if results and results['tracks']:
                track = self.find_best_result(results)
                # not sure if it's usefull for blindtest lul
                track = self.prepare_track(track)
                if not song.title:
                    song.title = track['info']['title']
                player.blindtest.current_song.video_url = track['info']['uri']
                player.blindtest.current_song.video_name = track['info']['title']
                if not player.blindtest.listening_mode:
                    await song.add_alternative_titles(track['info']['title'])
                    track['info']['title'] = "Blindtest"
                    track['info']['uri'] = "https://watora.xyz/"
                    track['info']['artwork'] = None
                if player not in self.bot.lavalink.players.players.values():
                    return False  # Who knows at it could take some times before being here
                player.add(
                    requester=player.node._manager._lavalink.bot.user.id, track=track)
                if not player.is_playing:  # useless check but who knows ?
                    await self.player_play(player, song_url)
                if channel and not player.blindtest.listening_mode:
                    await channel.send(get_str(channel.guild, 'cmd-blindtest-next-song', bot=self.bot))
                    player.blindtest.current_task.append(asyncio.ensure_future(
                        self.wait_blindtest_answer(player, channel)))
                return True
            elif error_count < 5:
                return await self.blindtest_loop(player, error_count=error_count + 1)
        return False

    async def wait_blindtest_answer(self, player, channel):
        """ Waits for the right answer to happen """
        def check(m):
            if m.channel.id != player.blindtest.channel:
                return False
            if m.author.bot:
                return False
            if not channel:
                return False
            if not m.content:
                return False
            if not player.is_connected:
                return False
            if len(m.content) > 120:
                return False
            return player.blindtest.answer_is_valid(query=m.content)

        scd_embed = discord.Embed(title=get_str(
            channel.guild, "cmd-blindtest-rank", bot=self.bot))
        response_message = None
        point = 0
        player.blindtest.current_song.started_at = current_time()

        try:
            # Why it would wait more than 5 mins ??
            response_message = await self.bot.wait_for('message', timeout=max(3, min(player.blindtest.timeout, 300)), check=check)
        except asyncio.TimeoutError:
            if player not in self.bot.lavalink.players.players.values():
                return
            if player.blindtest.songs and not player.blindtest.next_song:
                player.blindtest.pop(next=True)
                await player.blindtest.next_song.add_alternative_titles()
            player.blindtest.current_song.found_reason = get_str(
                channel.guild, "cmd-blindtest-timeout", bot=self.bot)
            asyncio.ensure_future(player.skip())
            # no await here cus otherwise it'll be cancelled
            # while loading the shit.. anyway, just keep it
            return
        else:
            if player not in self.bot.lavalink.players.players.values():
                return

            cid = str(response_message.author.id)
            mega_bonus = (response_message.content ==
                          player.blindtest.current_song.title)
            naked_query = re.sub(
                r'\W+', ' ', player.blindtest.current_song.title).strip()
            bonus = (response_message.content.lower() in [
                     player.blindtest.current_song.title.lower(), naked_query])
            point = 3 if mega_bonus else (2 if bonus else 1)
            if cid in player.blindtest.points:
                player.blindtest.points[cid] += point
            else:
                player.blindtest.points[cid] = point
            player.blindtest.current_song.found = True

        await self.blindtest_embed(p=player, channel=channel, msg=response_message, bonus=point)

        scd_embed = await player.blindtest.get_classement(embed=scd_embed)

        if player.blindtest.songs:
            await channel.send(embed=scd_embed)
            if not player.blindtest.next_song:
                player.blindtest.pop(next=True)
                await player.blindtest.next_song.add_alternative_titles()
            if player.blindtest.wait:
                await asyncio.sleep(min(30, max(0, int(player.blindtest.wait))))
            asyncio.ensure_future(player.skip())
            # no await here cus otherwise it'll be cancelled by itself
            # while loading the shit.. anyway, just keep it
            return
        asyncio.ensure_future(player.blindtest.stop(bypass=True))

    async def blindtest_embed(self, p, channel, msg=None, bonus=0):
        guild = self.bot.get_guild(int(p.guild_id))
        color = self.get_color(msg.guild if msg else guild)
        embed = discord.Embed(
            colour=color, title=f"**{p.blindtest.current_song.title}**", url=p.blindtest.current_song.url)
        embed.description = f'{get_str(channel.guild, "cmd-blindtest-video", bot=self.bot)} : **[{p.blindtest.current_song.video_name}]({p.blindtest.current_song.video_url})**'
        if bonus:
            embed.description += '\n' + get_str(channel.guild, 'cmd-blindtest-{}'.format(
                ['good', 'very-good', 'perfect'][bonus - 1]), bot=self.bot)
        if p.blindtest.current_song.image_url:
            embed.set_thumbnail(url=p.blindtest.current_song.image_url)
        else:
            thumb = await self.get_thumbnail(p.now, p)
            if thumb:
                embed.set_thumbnail(url=thumb)
        if msg:
            embed.set_footer(text=get_str(channel.guild, "cmd-blindtest-found-in", bot=self.bot,
                                          can_owo=False).format(round(current_time() - p.blindtest.current_song.started_at, 2)))
            requester = msg.author
            embed.set_author(
                name=requester.name, icon_url=requester.avatar_url or requester.default_avatar_url)
        else:
            if not p.blindtest.current_song.found_reason:
                p.blindtest.current_song.found_reason = get_str(
                    channel.guild, "cmd-blindtest-not-found", bot=self.bot)
            embed.set_author(name=p.blindtest.current_song.found_reason)
        await channel.send(embed=embed)

    async def autoplay_loop(self, player, attempt=0):
        """Auto play related son when queue ends."""
        settings = await SettingsDB.get_instance().get_guild_settings(int(player.guild_id))
        if player.is_connected and player.connected_channel and not player.is_playing and settings.autoplay and not player.queue and (attempt < 10):
            if not sum(1 for m in player.connected_channel.members if not (m.voice.deaf or m.bot or m.voice.self_deaf)):
                return False
            previous = player.now or player.previous or player.current
            if not previous:
                return False
            if 'yout' not in previous.uri.lower():
                return False
            url = await self.youtube_api.get_recommendation(previous.identifier, player=player)
            if not url:
                return False
            url = f"https://www.youtube.com/watch?v={url}"
            results = await self.prepare_url(query=url, node=player.node)
            if results and results['tracks']:
                track = results['tracks'][0]
                track = self.prepare_track(track)
                player.add(requester=previous.requester, track=track)
                if not player.is_playing:
                    await player.play()
                return True
            else:
                # No idea if it's useful, but prevent from infinite loop.
                await self.autoplay_loop(player, attempt=attempt + 1)
                return True

        return False

    async def update_all_listen_moe_players(self, kpop=False):
        """Updates all listen moe players to display the new current song"""
        playing = self.bot.lavalink.players.find_all(
            lambda p: p.is_playing)  # maybe useless to check p.current but who knows ?
        for p in playing:
            if p.current and 'listen.moe' in p.current.uri.lower():
                if 'kpop' in p.current.uri.lower() and not kpop:  # basic checks to ignore useless updates
                    continue
                elif 'kpop' not in p.current.uri.lower() and kpop:
                    continue
                log.debug(f'[Player] Updating listen.moe on {p.guild_id}')
                await self.update_msg_radio(p)

    async def update_all_mc_players(self):
        """Updates all monstercat players to display the new current song"""
        await asyncio.sleep(15)  # Twitch radio stream with API is a little bit before twitch live
        # maybe useless to check p.current but who knows ?
        playing = self.bot.lavalink.players.find_all(lambda p: p.is_playing)
        for p in playing:
            if p.current and 'monstercat' in p.current.uri.lower() and 'twitch' in p.current.uri.lower():
                log.debug(f'[Player] Updating monstercat on {p.guild_id}')
                await self.update_msg_radio(p)

    async def update_msg_radio(self, p):
        """Updates the now playing message according to the radio current song"""
        self.radio_update(p.current)
        c = self.bot.get_channel(p.channel)
        if c:
            if 'kpop' in p.current.uri.lower():
                color = int("3CA4E9", 16)
            else:
                color = int("FF015B", 16)
            thumb = await self.get_thumbnail(p.current, p)
            embed = discord.Embed(
                colour=color, title=f"**{p.current.title}**", url=p.current.uri)
            if thumb:
                embed.set_image(url=thumb)
            requester = await self.bot.safe_fetch('member', p.current.requester, guild=c.guild)
            if requester:
                embed.set_author(
                    name=requester.name, icon_url=requester.avatar_url or requester.default_avatar_url, url=p.current.uri)

            await self.send_new_np_msg(p, c, new_embed=embed)

    async def get_title(self, ctx, *, query: str):
        """Gets title from url or query"""
        results = await self.prepare_url(query)

        if not results or not results['tracks']:
            return None

        return results['tracks'][0]['info']['title']

    async def get_track_info(self, ctx, *, query: str):
        """Gets every info from the first result or return None"""
        results = await self.prepare_url(query)

        if not results or not results['tracks']:
            return None

        return results['tracks'][0]['info']

    async def disconnect_player(self, player):
        """Disconnects a player and clean some stuffs"""
        guild = self.bot.get_guild(int(player.guild_id))
        if guild:  # maybe it's from on_guild_remove
            gid = guild.id
        else:
            gid = int(player.guild_id)

        # Removes the player first to avoid multiple occurences
        self.bot.lavalink.players.remove(gid)

        # Cleaning some stuffs
        if player.blindtest.is_running:
            await player.blindtest.stop(send_final=False)
        await player.reset_equalizer()
        await player.disconnect()
        await self.delete_old_npmsg(player)

        guild_info = f"{guild.id}/{guild.name}" if guild else f"{gid}"
        log.debug(f"[Player] Cleaned {guild_info}")

    async def get_lyrics(self, query, token):
        """Gets lyrics from genius API"""
        url = "https://api.genius.com/search"
        params = {"q": query, "page": 1}
        headers = {"Authorization": f"Bearer {token}"}

        async with self.session.get(url, params=params, headers=headers) as response:
            data = await response.json()
            results = data["response"]["hits"]

        if len(results) < 1:
            return {"error": f"No results found for \"{query}\""}

        result = results[0]["result"]
        response = await self.session.get(result["url"])
        bs = bs4.BeautifulSoup(await response.text(), "html.parser")

        for script_tag in bs.find_all("script"):
            script_tag.extract()

        lyrics = bs.find("div", class_="lyrics").get_text()

        return {
            "title": result["title"],
            "url": result["url"],
            "path": result["path"],
            "thumbnail": result.get("thumbnail"),
            "header_image_url": result["song_art_image_thumbnail_url"],
            "primary_artist": result["primary_artist"],
            "lyrics": lyrics
        }

    async def reload_np_msg(self, player):
        # Idk, it's too fast when first timestamp is 0:00
        await asyncio.sleep(1)
        if not player.npmsg:
            return
        channel = player.npmsg.channel
        if not channel:
            return

        try_edit = False
        current = player.current

        color = self.get_color(channel.guild)
        pos = lavalink.utils.format_time(
            player.position).lstrip('0').lstrip(':')
        dur = lavalink.utils.format_time(
            current.duration).lstrip('0').lstrip(':')
        thumb = await self.get_thumbnail(current, player)
        requester = await self.bot.safe_fetch('member', current.requester, guild=channel.guild)
        prog_bar_str = sweet_bar(player.position, current.duration)
        embed = discord.Embed(colour=color, title=f"**{current.title}**",
                              description=f"{'⏸' if player.paused else '🔁' if player.repeat else ''}`[{pos}/{dur}]` {prog_bar_str}")
        embed.url = current.uri
        if requester:
            embed.set_author(
                name=requester.name, icon_url=requester.avatar_url or requester.default_avatar_url, url=current.uri)
        if thumb:
            embed.set_image(url=thumb)

        if player.node.is_perso:
            name = await self.bot.safe_fetch('user', player.node.name) or player.node.name
            embed.set_footer(text=f"Hosted by {name}")

        async for entry in channel.history(limit=3):
            if not entry or not player.npmsg:  # idk
                continue
            if entry.id == player.npmsg.id:
                try_edit = True
                break
            if len(entry.content) > 500:  # if msg too long
                break
            elif entry.attachments or entry.embeds:  # if there are embeds or attchments
                break

        # Send or edit the old message
        if try_edit:
            try:
                await player.npmsg.edit(embed=embed, content=None)
                return
            except discord.HTTPException:
                pass

        await self.delete_old_npmsg(player)

        try:
            player.npmsg = await channel.send(embed=embed)
        except discord.Forbidden:
            try:
                return await channel.send(get_str(channel.guild, "need-embed-permission", self.bot), delete_after=20)
            except discord.Forbidden:
                pass

    async def send_new_np_msg(self, player, channel, new_embed, message=None, force_send: bool = False):
        """Sends a new np msg and maybe delete the old one / or edit it"""
        # Check if it is worth to edit instead
        try_edit = False
        if player.npmsg and not force_send:
            try:
                async for entry in channel.history(limit=3):
                    if not entry or not player.npmsg:  # idk
                        continue
                    if entry.id == player.npmsg.id:
                        try_edit = True
                        break
                    if len(entry.content) > 500:  # if msg too long
                        break
                    elif entry.attachments or entry.embeds:  # if there are embeds or attchments
                        break
            except discord.HTTPException:
                pass

        # Send or edit the old message
        if try_edit:
            try:
                await player.npmsg.edit(embed=new_embed, content=None)
                return
            except discord.HTTPException:
                pass

        if force_send and message and player.npmsg:  # from np
            now = message.created_at
            diff = now - player.npmsg.created_at
            if diff.total_seconds() < 1.5:  # don't spam new np msg REEE
                return

        await self.delete_old_npmsg(player)

        try:
            settings = await SettingsDB.get_instance().get_guild_settings(channel.guild.id)
            if settings.lazy:
                log.debug(
                    '[Lazy] Creating a Lazyer instance for {}/{}.'.format(channel.guild.id, channel.guild.name))
                lazy = Lazyer(channel, self.bot, player)
                lazy.embed = new_embed
                await lazy.send_to_channel()
            else:
                player.npmsg = await channel.send(embed=new_embed)
        except discord.Forbidden:
            try:
                return await channel.send(get_str(channel.guild, "need-embed-permission", self.bot), delete_after=20)
            except discord.Forbidden:
                pass

    async def get_player(self, guild, create: bool = False, user_id: int = None):
        """Gets the player if the bot is connected, or create it if needed"""
        player = self.bot.lavalink.players.get(guild.id)
        if player and not player.is_connected:
            if player.channel_id:
                await player.connect(int(player.channel_id))
            elif create:
                return player
            else:
                log.warning(
                    f"[Player] Found without connected channel.. disconnecting from {guild.id}/{guild.name}.")
                await self.disconnect_player(player)
                raise NoVoiceChannel(
                    get_str(guild, "not-connected", bot=self.bot))
        if not player:
            if create:
                node = None
                settings = await SettingsDB.get_instance().get_guild_settings(guild.id)
                if settings.defaultnode and guild.get_member(int(settings.defaultnode)):
                    node = self.bot.lavalink.node_manager.get_node_by_name(
                        str(settings.defaultnode))
                if not node:
                    # Allows to do 1 call for both server_is_claimed and add_custom_node
                    glob_settings = await SettingsDB.get_instance().get_glob_settings()
                    if await self.bot.server_is_claimed(guild.id, glob_settings):
                        node = self.bot.lavalink.node_manager.get_node_by_name(
                            'Premium')
                    if not node and str(user_id) in glob_settings.custom_hosts.keys():
                        node = self.bot.lavalink.node_manager.get_node_by_name(
                            user_id)
                        if not node:
                            if await self.add_custom_node(str(user_id), settings=glob_settings):
                                node = self.bot.lavalink.node_manager.get_node_by_name(
                                    str(user_id), True)
                player = self.bot.lavalink.players.create(
                    guild_id=guild.id, endpoint=str(guild.region), node=node)
                log.debug(f'[Player] Creating {guild.id}/{guild.name}')
            else:
                raise NoVoiceChannel(
                    get_str(guild, "not-connected", bot=self.bot))

        return player

    async def player_play(self, player, query, start_time=None, end_time=None):
        """Starts a song with or without optional parameters find or not with regex"""
        kwargs = {}
        if not start_time:
            start_time = re.findall('[&?](t|start|starts|s)=(\d+)', query)
            if start_time:
                kwargs['startTime'] = str(int(start_time[-1][-1]) * 1000)
        if not end_time:
            end_time = re.findall('[&?](e|end|ends)=(\d+)', query)
            if end_time:
                kwargs['endTime'] = str(int(end_time[-1][-1]) * 1000)

        await player.play(**kwargs)

    def remove_optional_parameter(self, query):
        start_time = re.findall('([&?])(t|start|starts|s)=(\d+)', query)
        for m in start_time:
            query = query.replace(f'{m[0] + m[1] + "=" + m[2]}', '')
        end_time = re.findall('([&?])(e|end|ends)=(\d+)', query)
        for m in end_time:
            query = query.replace(f'{m[0] + m[1] + "=" + m[2]}', '')

        return query.strip()

    def get_color(self, guild=None):
        """Gets the top role color otherwise select the Watora's main color"""
        if not guild or str(guild.me.color) == "#000000":
            return int("FF015B", 16)
        return guild.me.color

    def prepare_track(self, track, embed=None):
        """Prepares a track before adding it to queue"""
        if "listen.moe" in track['info']['uri'].lower():  # sweet listen.me integration
            track['info']['title'] = "LISTEN.moe J-POP"
            if 'kpop' in track['info']['uri'].lower():
                track['info']['title'] = "LISTEN.moe K-POP"
                track['info']['uri'] = 'https://listen.moe/kpop'
                if embed is not None:
                    embed.color = int("3CA4E9", 16)
            else:
                track['info']['uri'] = 'https://listen.moe'
                if embed is not None:
                    embed.color = int("FF015B", 16)
        elif 'monstercat' in track['info']['uri'].lower() and 'twitch' in track['info']['uri'].lower():
            if embed is not None:
                embed.color = int("FF015B", 16)
        if not match_url(track['info']['uri']):
            track['info']['title'] = track['info']['uri']
            track['info']['uri'] = ""
        if embed is not None:
            return track, embed
        return track

    def radio_update(self, current):
        """Updates radio current songs titles in current players"""
        if "listen.moe" in current.uri.lower():
            if 'kpop' in current.uri.lower():
                current.title = self.get_current_listen_moe(kpop=True)
            else:
                current.title = self.get_current_listen_moe()
        elif 'monstercat' in current.uri.lower() and 'twitch' in current.uri.lower():
            current.title = self.get_current_mc()

    def get_current_mc(self):
        """Returns the current song title on MonsterCat FM"""
        now = self.bot.mcnow
        if now:
            return f"{now[0]} - {now[1]}"
        return "Monstercat Radio - 24/7 Music Stream - live.monstercat.com"

    def get_current_listen_moe(self, kpop=False):
        """Returns the current song title on LISTEN.moe"""
        now = self.bot.now
        if kpop:
            now = self.bot.nowkpop
        if now:
            if not isinstance(now, dict):
                if now.artists:
                    return f"{now.artists[0].name_romaji or now.artists[0].name} - {now.title}"
                else:
                    return f"{now.title}"
            else:  # if now = msg.raw
                try:
                    title = now['d']['song']['title']
                except (KeyError, IndexError):
                    pass
                else:
                    try:
                        artists = now['d']['song']['artists'][0]
                    except (KeyError, IndexError):
                        return f"{title}"

                    if 'nameRomaji' in artists:
                        artist = artists['nameRomaji']
                    else:
                        artist = artists['name']

                    return f"{artist} - {title}"

        return f"LISTEN.moe {'K-POP' if kpop else 'J-POP'}"

    async def is_dj(self, ctx):  # TODO: Remove it from this cog
        """Checks if a user is DJ or not"""
        if ctx.guild:
            if is_alone(ctx.author):
                return True
            if is_admin(ctx.author, ctx.channel):
                return True
            if ctx.channel.permissions_for(ctx.author).manage_guild:
                return True
            settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
            for r in ctx.author.roles:
                if r.name.lower() == "dj":
                    return True
                if r.id in settings.djs or "all" in settings.djs:
                    return True
        return False

    async def is_perso(self, guild, name):
        """Checks if an autoplaylist is personal or not"""
        if name.isdigit() and 20 > len(name) > 16:  # To change after 2090 cus ID will be longer or equal than 20.
            member = await self.bot.safe_fetch('member', int(name), guild=guild)
            if member:
                return member
        return False

    def is_spotify(self, name):
        """Checks if a query is a spotify URL or URI. (maybe not accurate)"""
        if match_url(name) and 'open.spotify' in name:
            return True
        if name.startswith('spotify:'):
            return True
        return False

    async def get_animes(self, player, difficulty: int = 0, mal: str = None, argument: str = None, remove: str = None, alone: bool = True):
        """ Allows to get an anime list based on parameter """
        if mal:
            anime_list = await self.bot.jikan.user(username=mal, request='animelist', argument=argument)
            if alone:
                stop = False
                i = 2
                # Max 3 requests
                while ((len(anime_list['anime']) % 300) == 0 and not stop) and len(anime_list['anime']) != 900:
                    next_list = await self.bot.jikan.user(username=mal, request='animelist', argument=argument, page=i)
                    anime_list['anime'].extend(next_list['anime'])
                    if (len(next_list['anime']) % 300) == 0:
                        i += 1
                    else:
                        stop = True
        else:
            difficulty = int(difficulty)
            if not difficulty:
                if self.bot.top_animes:
                    anime_list = self.bot.top_animes.copy()
                else:
                    anime_list = await self.bot.jikan.top(type='anime')
            else:
                if self.bot.top_animes:
                    top_anime_list = self.bot.top_animes['top'][:int(
                        difficulty * 100)].copy()
                    anime_list = {
                        'top': top_anime_list
                    }
                else:
                    anime_list = await self.bot.jikan.top(type='anime', page=difficulty)
        animes = []
        anime_list = Jikan(anime_list)

        for anime in getattr(anime_list, 'anime', []):
            if anime.type == 'TV':
                if remove and (int(anime.watching_status) in [self.anime_status.index(m) for m in remove.split(',') if m in self.anime_status]):
                    continue
                animes.append(BlindTestSong(jikan=self.bot.jikan, title=anime.title,
                                            id=anime.mal_id, url=anime.url, image_url=anime.image_url))
        for anime in getattr(anime_list, 'top', []):
            if anime.type == 'TV':
                animes.append(BlindTestSong(jikan=self.bot.jikan, title=anime.title,
                                            id=anime.mal_id, url=anime.url, image_url=anime.image_url))

        return animes

    async def prepare_blindtest(self, ctx, player, difficulty: int = None, mal: str = None, argument: str = 'all',
                                autoplaylist: str = None, longestword: str = 'false', timeout: int = 120, severity: int = 100,
                                listening: str = 'false', percentage='100,0,0', wait=5, remove: str = 'ptw', source: str = 'y'):
        """Prepares the blindtest before starting it."""
        songs = []
        if autoplaylist:
            file_name = autoplaylist
            if ctx.message.mentions:
                user = ctx.message.mentions[-1]
                if user.mention not in file_name:  # It was a prefix
                    user = None
                    if len(ctx.message.mentions) > 1:
                        user = ctx.message.mentions[0]
                if user:
                    file_name = str(user.id)

            settings = await SettingsDB.get_instance().get_glob_settings()

            if str(file_name.lower()) not in settings.autoplaylists:
                perso = await self.is_perso(ctx.guild, name=file_name)
                if perso:
                    return await ctx.send(get_str(ctx, "music-plstart-dont-have"))
                file_name = format_mentions(file_name)
                return await ctx.send(get_str(ctx, "music-plstart-doesnt-exists").format(f"**{file_name}**", "`{}plnew`".format(get_server_prefixes(ctx.bot, ctx.guild))), delete_after=30)

            if not settings.autoplaylists[str(file_name.lower())]['songs']:
                return await ctx.send(get_str(ctx, "cmd-blindtest-empty"))
            for url in settings.autoplaylists[str(file_name.lower())]['songs']:
                songs.append(BlindTestSong(url=url))

        elif mal:
            mals = mal.split(',')
            nb = len(mals)
            if nb > 5:
                return await ctx.send(get_str(ctx, "cmd-blindtest-max-animelist"))
            else:
                max_mal = 5 if (await self.bot.server_is_claimed(ctx.guild.id)) else 2
                if nb > max_mal:
                    if await is_patron(self.bot, ctx.author.id):
                        e = discord.Embed(description=get_str(
                            ctx, "music-autoleave-need-claim").format(f"`{get_server_prefixes(ctx.bot, ctx.guild)}claim`"))
                    else:
                        e = discord.Embed(description=get_str(ctx, "cmd-blindtest-mal-same-time").format(
                            f"`{max_mal}`") + "\n\n" + "**[Patreon](https://www.patreon.com/watora)**")
                    try:
                        return await ctx.send(embed=e)
                    except discord.Forbidden:
                        return await ctx.send(get_str(ctx, "cmd-blindtest-mal-same-time").format(f"`{max_mal}`"))
            ids = []
            for mal in mals:
                results = await self.get_animes(player, mal=mal.strip(), argument=argument, remove=remove, alone=(len(mals) == 1))
                for result in results:
                    if result.id not in ids:
                        songs.append(result)
                        ids.append(result.id)

        elif difficulty is not None:  # can be 0
            songs.extend(await self.get_animes(player, difficulty=difficulty))
        else:
            return await ctx.send(get_str(ctx, "cmd-blindtest-no-enough-param"))

        if longestword == 'true':
            player.blindtest.accept_longest_word = True
        else:
            player.blindtest.accept_longest_word = False
        if listening == 'true':
            player.blindtest.listening_mode = True
        else:
            player.blindtest.listening_mode = False
            player.channel = None

        if source.lower().startswith('s'):
            player.blindtest.source = 'scsearch'
        else:
            player.blindtest.source = 'ytsearch'  # TODO: Remove this later

        player.blindtest.severity = int(severity)
        player.blindtest.timeout = int(timeout)
        player.blindtest.songs = songs
        player.blindtest.channel = int(ctx.channel.id)
        player.blindtest.percentage = percentage
        player.blindtest.wait = int(wait)
        return songs

    @commands.cooldown(rate=1, per=3, type=commands.BucketType.user)
    @commands.command(aliases=['btpoints', 'btrank', 'btranking', 'blindtestrank', 'blindtestranking', 'btpoint', 'blindtestpoint', 'blindtestpoints', 'btscore', 'blindtestscores', 'btscores', 'btclassement', 'blindtestclassement'])
    async def blindtestscore(self, ctx):
        """
            {command_prefix}blindtestscore

        {help}
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        embed = discord.Embed()
        points = settings.points
        author_in = False

        player = self.bot.lavalink.players.players.get(ctx.guild.id, False)

        if player and player.blindtest.is_running:
            for k, v in player.blindtest.points.items():
                points[k] = settings.points.get(k, 0) + v

        counter = Counter(points)
        classement = OrderedDict(counter.most_common())
        for i, user in enumerate(classement, start=1):
            if len(embed.fields) > 10:
                break
            u = await self.bot.safe_fetch('member', int(user), guild=ctx.guild)
            if u:
                if u == ctx.author:
                    author_in = True
                embed.add_field(name=f'{i}. {u}', value=points[user])

        if not author_in and str(ctx.author.id) in counter:
            user = ctx.author
            pos = list(counter).index(str(user.id)) + 1
            if pos == 11:
                embed.add_field(name=f'{pos}. {user}', value=points[user])
            else:
                embed.set_footer(
                    text=f"{pos}. {user} : {nb} {points[user]}", icon_url=user.avatar_url)

        if not embed.fields:
            return await ctx.send(get_str(ctx, "cmd-blindtestscore-no-saved").format(f'`{get_server_prefixes(ctx.bot, ctx.guild)}bt`'))

        embed.color = self.get_color(ctx.guild)
        embed.set_author(
            name=f'{ctx.guild.name} - {get_str(ctx, "cmd-blindtest-rank")}', icon_url=ctx.guild.icon_url)

        return await ctx.send(embed=embed)

    @commands.cooldown(rate=1, per=60, type=commands.BucketType.guild)
    @commands.command(aliases=['bt'])
    async def blindtest(self, ctx, *, user_options=None):
        """
            {command_prefix}blindtest anime (other_options)
            {command_prefix}blindtest [mal=username,username_two,...] (other_options)
            {command_prefix}blindtest [autoplaylist=name] (other_options)
            {command_prefix}blindtest [difficulty=[0-6]] (other_options)

        {help}
        """
        if user_options in ('score', 'point', 'points', 'ranking', 'scores', 'classement', 'rank'):
            ctx.command.reset_cooldown(ctx)
            return await ctx.invoke(self.blindtestscore)

        if not ctx.me.voice or ctx.guild.id not in self.bot.lavalink.players.players:
            try:
                player = await ctx.invoke(self.voice_connect)
            except NoVoiceChannel:
                ctx.command.reset_cooldown(ctx)
                return await ctx.send(get_str(ctx, "music-join-no-channel"))
            except lavalink.NodeException:
                ctx.command.reset_cooldown(ctx)
                return await ctx.send(get_str(ctx, "music-nodes-unavailable"))
            if not player:
                ctx.command.reset_cooldown(ctx)
                return
        else:
            player = await self.get_player(ctx.guild)

        if not ctx.guild.me.voice:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

        my_vc = ctx.guild.me.voice.channel

        if not await self.is_dj(ctx):
            if ctx.author not in my_vc.members or (ctx.author.voice.self_deaf or ctx.author.voice.deaf):
                ctx.command.reset_cooldown(ctx)
                return await ctx.send(get_str(ctx, "music-not-my-channel").format(f"**{my_vc}**"), delete_after=30)

        if not user_options or user_options in ('stop', 'leave', 'cancel'):
            if not ctx.channel.permissions_for(ctx.author).manage_guild and not ctx.author.id == owner_id:
                ctx.command.reset_cooldown(ctx)
                raise commands.errors.CheckFailure
            if player.blindtest.is_running:
                await player.blindtest.stop()
                await ctx.send(get_str(ctx, "cmd-blindtest-stop-blindtest"))
            else:
                await self.bot.send_cmd_help(ctx)
            return ctx.command.reset_cooldown(ctx)

        if player.is_playing or player.blindtest.is_running:
            if player.blindtest.is_running:
                confirm_message = await ctx.send(get_str(ctx, "cmd-blindtest-is-running"))

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
                    return await ctx.send(get_str(ctx, 'music-search-no-answer'))

                if not response_message.content.lower().startswith('y'):
                    ctx.command.reset_cooldown(ctx)
                    return await ctx.send(get_str(ctx, 'music-search-stopping'))

                if not ctx.channel.permissions_for(ctx.author).manage_guild and not ctx.author.id == owner_id:
                    ctx.command.reset_cooldown(ctx)
                    raise commands.errors.CheckFailure

            ctx.command.reset_cooldown(ctx)
            await player.blindtest.stop()

        if user_options.split(' ')[0] in ('anime', 'topanime'):
            user_options = 'difficulty=0' + ' ' + \
                ' '.join(user_options.split(' ')[1:])
        options = {}
        matchs = re.findall('(\S+)[:=](\S+)', user_options)

        for m in matchs:
            if m[0] not in self.parameters:
                ctx.command.reset_cooldown(ctx)
                return await ctx.send(get_str(ctx, "cmd-blindtest-invalid-param").format(f'`{m[0]}`'))
            if inspect.isfunction(self.parameters[m[0]]):
                try:
                    if not self.parameters[m[0]](m[1]):
                        ctx.command.reset_cooldown(ctx)
                        return await ctx.send(get_str(ctx, "cmd-blindtest-invalid-value").format(f'`{m[1]}`', f'`{m[0]}`'))
                except ValueError:
                    ctx.command.reset_cooldown(ctx)
                    return await ctx.send(get_str(ctx, "cmd-blindtest-invalid-value").format(f'`{m[1]}`', f'`{m[0]}`'))
            else:
                if not re.match(self.parameters[m[0]], m[1]):
                    ctx.command.reset_cooldown(ctx)
                    return await ctx.send(get_str(ctx, "cmd-blindtest-invalid-value").format(f'`{m[1]}`', f'`{m[0]}`'))
            options[m[0]] = m[1]

        info = get_str(ctx, "cmd-blindtest-blindtest-info")
        load = result = None
        timer_bonus = 1 if 'mal' not in options else len(
            options['mal'].split(','))
        tries = 5
        if 'argument' in options and 'remove' in options:
            if options['argument'] == options['remove']:
                ctx.command.reset_cooldown(ctx)
                return await ctx.send(get_str(ctx, "cmd-blindtest-same-remove"))
        if options.get('argument', '') == 'ptw':
            options['remove'] = 'nothing'
        all_real = ['watching', 'completed', 'onhold', 'dropped', 'ptw']
        if 'remove' in options:
            for m in options['remove'].split(','):
                if m in all_real:
                    all_real.remove(m)
            if len(all_real) == 1:
                options['argument'] = all_real[0]
                options['remove'] = 'nothing'
        for m in range(tries):
            try:
                result = await asyncio.wait_for(self.prepare_blindtest(ctx, player, **options), timeout=timer_bonus * m + 5)
            except (asyncio.TimeoutError, aiohttp.ClientError, JikanException):
                if not load:
                    load = await ctx.send(info)
                else:
                    await load.edit(content=info + f"({get_str(ctx, 'cmd-blindtest-fail')} `{m}/{tries}`)")
                continue
            break
        if load:
            await load.delete()
        if isinstance(result, list):
            await ctx.send(get_str(ctx, "cmd-blindtest-start").format(f'`{len(player.blindtest.songs)}`'))
            asyncio.ensure_future(self.blindtest_loop(player))
        elif isinstance(result, discord.Message):
            pass
        else:
            await ctx.send(get_str(ctx, "cmd-blindtest-mal-fail"))

        ctx.command.reset_cooldown(ctx)

    @checks.has_permissions(manage_guild=True)
    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.guild)
    @commands.command(aliases=['playauto', 'autoplaymod'])
    async def autoplay(self, ctx):
        """
            {command_prefix}autoplay

        {help}
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        settings.autoplay = not settings.autoplay
        await SettingsDB.get_instance().set_guild_settings(settings)

        await ctx.send(get_str(ctx, "music-autoplay-{}".format(['disabled', 'enabled'][settings.autoplay])))

    @commands.cooldown(rate=1, per=3, type=commands.BucketType.user)
    @commands.command(aliases=['related', 'rq', 'rs', 'playrelated'])
    async def relatedsong(self, ctx, *, url=None):
        """
            {command_prefix}relatedsong
            {command_prefix}relatedsong [song|key_words]

        {help}
        """
        player = None

        if ctx.guild.id in self.bot.lavalink.players.players:
            player = await self.get_player(ctx.guild)

        if not url:
            player = await self.get_player(ctx.guild)

            if not player.is_connected:
                return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

            if player.current:
                if "youtube" not in player.current.uri.lower():
                    return await ctx.send(get_str(ctx, "music-download-only"))
                id = player.current.identifier
                title = player.current.title
            else:
                return await ctx.send(get_str(ctx, "not-playing"), delete_after=30)
        else:
            url = await self.get_track_info(ctx, query=url)
            if not url:  # No result, displays the current song download
                return await ctx.invoke(self.relatedsong)
            id = url['identifier']
        url = await self.youtube_api.get_recommendation(id, player=player)
        if not url:
            return await ctx.send(":exclamation: " + get_str(ctx, "cmd-nextep-error"), delete_after=20)
        url = f"https://www.youtube.com/watch?v={url}"
        return await ctx.invoke(self.play_song, query=url)

    @commands.command(name='play', aliases=['p', "stream", 'spotify', "playstream", "playsong", "sing", "start"])
    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.user)
    async def play_song(self, ctx, *, query: str = None):
        """
            {command_prefix}play [key_words]
            {command_prefix}play [url]

        {help}
        """
        if not ctx.me.voice or ctx.guild.id not in self.bot.lavalink.players.players:
            try:
                player = await ctx.invoke(self.voice_connect)
            except NoVoiceChannel:
                ctx.command.reset_cooldown(ctx)
                return await ctx.send(get_str(ctx, "music-join-no-channel"))
            except lavalink.NodeException:
                return await ctx.send(get_str(ctx, "music-nodes-unavailable"))
            if not player:
                return
        else:
            player = await self.get_player(ctx.guild)

        if not ctx.guild.me.voice:
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

        my_vc = ctx.guild.me.voice.channel

        if not await self.is_dj(ctx):
            if ctx.author not in my_vc.members or (ctx.author.voice.self_deaf or ctx.author.voice.deaf):
                return await ctx.send(get_str(ctx, "music-not-my-channel").format(f"**{my_vc}**"), delete_after=30)

        if not query and player.paused:
            return await ctx.invoke(self.pause_song)
        elif not query:
            return await self.bot.send_cmd_help(ctx)

        query = query.strip('<>')

        if self.is_spotify(query):
            try:
                results = await self.prepare_spotify(ctx, query, node=player.node)
            except SpotifyError as e:
                return await ctx.send(e)
        else:
            results = await self.prepare_url(query=query, node=player.node)

        if not results or not results['tracks']:
            if results['loadType'] == "LOAD_FAILED":
                if 'mix' in results.get('exception', {}).get('message'):
                    # Skip YouTube mixes
                    return await ctx.invoke(self.play_song, query=query.split('&list')[0])
                if 'yout' in query:
                    settings = await SettingsDB.get_instance().get_glob_settings()
                    claimed_server = await self.bot.server_is_claimed(ctx.guild.id, settings)

                    if not claimed_server and await is_patron(self.bot, ctx.author.id):
                        return await ctx.send(embed=discord.Embed(description=get_str(
                            ctx, "music-autoleave-need-claim").format(f"`{get_server_prefixes(ctx.bot, ctx.guild)}claim`")))
                    if str(ctx.author.id) not in settings.custom_hosts.keys():  # TODO: Translations
                        embed = discord.Embed(title="YouTube videos are disabled!",
                                              description="In order to play YouTube videos either [**become a Patron**](https://www.patreon.com/watora).\nOtherwise, you have to host your own server.\nPlease setup one with `{}hostconfig` in DMs".format(get_server_prefixes(ctx.bot, ctx.guild)))
                        return await ctx.send(embed=embed)
                    else:
                        await ctx.send('Either your credentials aren\'t valid anymore or your server isn\'t running. You can use `{}hostconfig` to edit your configuration in DMs.'.format(get_server_prefixes(ctx.bot, ctx.guild)))
                else:
                    await ctx.send(get_str(ctx, "music-load-failed").format("`{}search`".format(get_server_prefixes(ctx.bot, ctx.guild))))
            elif results['loadType'] == "NO_MATCHES":
                await ctx.send(get_str(ctx, "music-no-result").format("`{}search`".format(get_server_prefixes(ctx.bot, ctx.guild))))
            return

        embed = discord.Embed(colour=self.get_color(ctx.guild))

        if results['playlistInfo']:
            tracks = results['tracks']

            for track in tracks:
                player.add(requester=ctx.author.id, track=track)

            embed.title = get_str(ctx, "music-p-enqueued")
            embed.description = f"{results['playlistInfo']['name']} - {len(tracks)} {get_str(ctx, 'music-songs') if len(tracks) > 1 else get_str(ctx, 'music-song')}"
            if 'failed' in results:
                embed.description += f" ({get_str(ctx, 'music-spotify-songs-failed').format(results['failed']) if results['failed'] > 1 else get_str(ctx, 'music-spotify-song-failed').format(results['failed'])})"
            try:
                await ctx.send(embed=embed)
            except discord.Forbidden:
                await ctx.send(get_str(ctx, "need-embed-permission"), delete_after=20)

        else:
            track = results['tracks'][0]
            if query and match_url(query):
                track['info']['uri'] = query
            track, embed = self.prepare_track(track, embed)
            embed.title = get_str(ctx, "music-enqueued")
            embed.description = f'**[{track["info"]["title"]}]({track["info"]["uri"]})**'
            position, time_until = await self.get_position_in_queue(ctx, player)
            bottom = get_str(ctx, "music-position-in-queue",
                             can_owo=False).format(f"{position}")
            if time_until and time_until != "00:00":
                bottom += " - " + \
                    get_str(ctx, "music-estimated-time",
                            can_owo=False).format(f"{time_until}")
            embed.set_footer(text=bottom)
            try:
                await ctx.send(embed=embed)
            except discord.Forbidden:
                try:
                    await ctx.send(get_str(ctx, "need-embed-permission"), delete_after=20)
                except discord.Forbidden:
                    pass
            player.add(requester=ctx.author.id, track=track)

        if not player.is_playing:
            await self.player_play(player, query)

    @commands.command(aliases=['prev', 'pv', 'lastsong', 'back', 'before'])
    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.user)
    async def previous(self, ctx):
        """
            {command_prefix}previous

        {help}
        """
        player = await self.get_player(ctx.guild)

        if not ctx.guild.me.voice:
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

        my_vc = ctx.guild.me.voice.channel

        if not await self.is_dj(ctx):
            if ctx.author not in my_vc.members or (ctx.author.voice.self_deaf or ctx.author.voice.deaf):
                return await ctx.send(get_str(ctx, "music-not-my-channel").format(f"**{my_vc}**"), delete_after=30)

        if player.previous:
            await ctx.invoke(self.play_song, query=player.previous.uri)
        else:
            await ctx.send(get_str(ctx, "music-previous-no-previous"), delete_after=30)

    @commands.command(aliases=['pvn', 'prevnow', 'lastsongnow', 'backnow', 'beforenow'])
    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.user)
    async def previousnow(self, ctx):
        """
            {command_prefix}previousnow

        {help}
        """
        player = await self.get_player(ctx.guild)

        if not player.is_connected:
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

        if not await self.is_dj(ctx):
            raise commands.errors.CheckFailure

        if player.previous:
            await ctx.invoke(self.playnow, query=player.previous.uri)
        else:
            await ctx.send(get_str(ctx, "music-previous-no-previous"), delete_after=30)

    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.user)
    @commands.command(aliases=['rp', 'rplay', "playagain", "playre", "restart", "playanew", "replayit", "replaycurrent"])
    async def replay(self, ctx):
        """
            {command_prefix}replay

        {help}
        """
        player = await self.get_player(ctx.guild)

        if not ctx.guild.me.voice:
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

        my_vc = ctx.guild.me.voice.channel

        if not await self.is_dj(ctx):
            if ctx.author not in my_vc.members or (ctx.author.voice.self_deaf or ctx.author.voice.deaf):
                return await ctx.send(get_str(ctx, "music-not-my-channel").format(f"**{my_vc}**"), delete_after=30)

        if not player.current:
            return await ctx.send(get_str(ctx, "not-playing"), delete_after=30)

        await ctx.invoke(self.play_song, query=player.current.uri)

    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.user)
    @commands.command(aliases=['rpnow', 'rplaynow', "playagainnow", "playrenow", "restartnow", "playanewnow", "replayitnow", "replaycurrentnow"])
    async def replaynow(self, ctx):
        """
            {command_prefix}replaynow

        {help}
        """
        player = await self.get_player(ctx.guild)

        if not ctx.guild.me.voice:
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

        my_vc = ctx.guild.me.voice.channel

        if not await self.is_dj(ctx):
            if ctx.author not in my_vc.members or (ctx.author.voice.self_deaf or ctx.author.voice.deaf):
                return await ctx.send(get_str(ctx, "music-not-my-channel").format(f"**{my_vc}**"), delete_after=30)

        if not player.current:
            return await ctx.send(get_str(ctx, "not-playing"), delete_after=30)

        await ctx.invoke(self.playnow, query=player.current.uri)

    @commands.cooldown(rate=1, per=2.0, type=commands.BucketType.user)
    @commands.command(aliases=["pass", "foward", "seek", "passto"])
    async def moveto(self, ctx, *, time):
        """
            {command_prefix}moveto +[seconds]
            {command_prefix}moveto -[seconds]
            {command_prefix}moveto [min:seconds]
            {command_prefix}moveto next
            {command_prefix}moveto previous

        {help}
        """
        if not await self.is_dj(ctx):
            raise commands.errors.CheckFailure

        player = await self.get_player(ctx.guild)

        if not player.is_connected:
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

        if not player.current:
            return await ctx.send(get_str(ctx, "not-playing"), delete_after=20)

        if player.current.stream:
            return await ctx.send(get_str(ctx, "music-moveto-stream"), delete_after=20)

        if str(time).lower().startswith(('p', 'n')):
            timestamps = player.current.extra.get('timestamps')
            if not timestamps:
                return await ctx.send('No timestamps found in video description! Perform a manual seek by providing a time value instead.')
            current_timestamp = None
            for timestamp in reversed(timestamps):
                time_val, title = timestamp
                milliseconds = self.get_seconds(time_val) * 1000
                if player.position >= milliseconds:
                    current_timestamp = timestamps.index(timestamp)
                    break
            if current_timestamp is None:
                to_go = timestamps[0]
            elif str(time).lower().startswith('p'):
                to_go = timestamps[max(0, current_timestamp - 1)]
            else:
                to_go = timestamps[min(
                    len(timestamps) - 1, current_timestamp + 1)]

            return await ctx.invoke(self.moveto, time=to_go[0])

        seconds = time_rx.search(time)

        if not seconds or '::' in time:
            return await ctx.send(get_str(ctx, "music-moveto-correct"), delete_after=20)

        seconds = int(seconds.group()) * 1000

        if time.startswith('-'):
            seconds = seconds * -1

        track_time = player.position + seconds

        time = time.replace(' ', "")

        if ':' in time or 'moveto' == ctx.invoked_with:  # Hacky but meh.
            parts = time.split(":")
            values = (1, 60, 60 * 60, 60 * 60 * 24)
            track_time = 0
            for i in range(len(parts)):
                try:
                    v = int(parts[i])
                except (IndexError, ValueError):
                    continue

                j = len(parts) - i - 1
                if j >= len(values):  # If I don't have a conversion from this to seconds
                    continue

                track_time += (v * values[j]) * 1000

        if track_time > player.current.duration:
            return await ctx.send(get_str(ctx, "music-moveto-exceeds"), delete_after=20)

        new_duration = lavalink.utils.format_time(
            track_time).lstrip('0').lstrip(':')
        await player.seek(track_time)
        await ctx.send(get_str(ctx, "music-moveto-moved").format(f'**{new_duration}**'))

    @commands.command(name='skip', aliases=['next', 's'])
    async def skip_song(self, ctx):
        """
            {command_prefix}skip

        {help}
        """
        await self.skip_explosion_check(ctx)

        player = await self.get_player(ctx.guild)

        if not ctx.guild.me.voice:
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

        my_vc = ctx.guild.me.voice.channel

        if not await self.is_dj(ctx):
            if ctx.author not in my_vc.members or (ctx.author.voice.self_deaf or ctx.author.voice.deaf):
                return await ctx.send(get_str(ctx, "music-not-my-channel").format(f"**{my_vc}**"), delete_after=30)

        if not player.current:
            return await ctx.send(get_str(ctx, "not-playing"), delete_after=20)

        skip_votes = player.skip_votes
        mbrs = my_vc.members
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        percent = settings.vote
        reqvotes = (
            (len([1 for m in mbrs if not m.bot and not m.voice.self_deaf and not m.voice.deaf])) / (100 / percent))
        voter = ctx.message.author

        if voter.id == player.current.requester:
            await ctx.send(get_str(ctx, "music-skip-success").format(f"**{ctx.author}**"), delete_after=20)
            await player.skip()
        elif voter.id not in skip_votes:
            skip_votes.add(voter.id)
            total_votes = len(skip_votes)
            if total_votes >= math.ceil(reqvotes):
                await ctx.send(get_str(ctx, "music-skip-success").format(f"**{ctx.author}**"), delete_after=20)
                await player.skip()
            else:
                await ctx.send(get_str(ctx, "music-skip-added") + ' **[{}/{}]**'.format(total_votes, math.ceil(reqvotes)))
        else:
            await ctx.send(get_str(ctx, "music-skip-already"))

    @commands.command(name='forceskip', aliases=['forcenext', 'fs', 'fskip', 'instaskip', "skipto", "jumpto", "jump"])
    async def forceskip(self, ctx, after: int = None):
        """
            {command_prefix}forceskip [position_in_queue]
            {command_prefix}forceskip

        {help}
        """
        await self.skip_explosion_check(ctx)

        player = await self.get_player(ctx.guild)

        if not ctx.guild.me.voice:
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

        my_vc = ctx.guild.me.voice.channel

        if not await self.is_dj(ctx):
            if ctx.author not in my_vc.members or (ctx.author.voice.self_deaf or ctx.author.voice.deaf):
                return await ctx.send(get_str(ctx, "music-not-my-channel").format(f"**{my_vc}**"), delete_after=30)

        if not player.current:
            return await ctx.send(get_str(ctx, "not-playing"), delete_after=20)

        if not await self.is_dj(ctx) and (after or ctx.author.id != player.current.requester):
            raise commands.errors.CheckFailure

        if after:
            if after > 1:
                if after > len(player.queue):
                    after = len(player.queue)
                after -= 1
                for index in range(0, after):
                    del player.queue[0]

            await ctx.send(get_str(ctx, "music-forceskip-success-to").format(f"**{ctx.author}**", f"`{after+1}`"))

        else:
            await ctx.send(get_str(ctx, "music-forceskip-success").format(f"**{ctx.author}**", ), delete_after=20)

        await player.skip()

    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.guild)
    @commands.command(aliases=['clearqueue', 'clearsongs', 'queueclear'])
    async def clear(self, ctx):
        """
            {command_prefix}clear

        {help}
        """
        player = await self.get_player(ctx.guild)

        if not ctx.guild.me.voice:
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

        my_vc = ctx.guild.me.voice.channel

        if not await self.is_dj(ctx):
            if ctx.author not in my_vc.members or (ctx.author.voice.self_deaf or ctx.author.voice.deaf):
                return await ctx.send(get_str(ctx, "music-not-my-channel").format(f"**{my_vc}**"), delete_after=30)

        if not player.queue:
            return await ctx.send(get_str(ctx, "music-clear-empty"))

        clear_votes = player.clear_votes

        if not await self.is_dj(ctx):
            mbrs = my_vc.members
            settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
            percent = settings.vote
            reqvotes = (
                (len([1 for m in mbrs if not m.bot and not m.voice.self_deaf and not m.voice.deaf])) / (100 / percent))
            voter = ctx.message.author
            if voter.id not in clear_votes:
                clear_votes.add(voter.id)
                total_votes = len(clear_votes)
                if total_votes < math.ceil(reqvotes):
                    return await ctx.send(get_str(ctx, "music-clear-vote") + ' **[{}/{}]**'.format(total_votes, math.ceil(reqvotes)))
            else:
                return await ctx.send(get_str(ctx, "music-clear-already"))

        player.queue.clear()
        await ctx.send(get_str(ctx, "music-clear-cleared"))

    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.guild)
    @commands.command(name='np', aliases=['currentsong', 'nowplaying', 'nplaying', 'current', 'now'])
    async def current_song(self, ctx):
        """
            {command_prefix}np

        {help}
        """
        player = await self.get_player(ctx.guild)
        # stock it into a var avoid changes between the beg and the end of the command
        current = player.current

        if not current:
            return await ctx.send(get_str(ctx, "not-playing"), delete_after=20)

        if "listen.moe" in current.uri.lower() or ('monstercat' in current.uri.lower() and 'twitch' in current.uri.lower()):
            self.radio_update(current)
            color = int("FF015B", 16)
            if 'kpop' in current.uri.lower():
                color = int("3CA4E9", 16)
        else:
            color = self.get_color(ctx.guild)

        pos = lavalink.utils.format_time(
            player.position).lstrip('0').lstrip(':')
        if current.stream:
            dur = 'LIVE'
        else:
            dur = lavalink.utils.format_time(
                current.duration).lstrip('0').lstrip(':')
        thumb = await self.get_thumbnail(current, player)
        requester = await self.bot.safe_fetch('member', current.requester, guild=ctx.guild)
        prog_bar_str = sweet_bar(player.position, current.duration)
        embed = discord.Embed(colour=color, title=f"**{current.title}**",
                              description=f"{'⏸' if player.paused else '🔁' if player.repeat else ''}`[{pos}/{dur}]` {prog_bar_str}")
        embed.url = current.uri
        if requester:
            embed.set_author(
                name=requester.name, icon_url=requester.avatar_url or requester.default_avatar_url, url=current.uri)
        if thumb:
            embed.set_image(url=thumb)
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        if not settings.channel:
            player.channel = ctx.channel.id
        if player.node.is_perso:
            name = await self.bot.safe_fetch('user', player.node.name) or player.node.name
            # TODO: Translations
            embed.set_footer(text=f"Hosted by {name}")
        await self.send_new_np_msg(player, ctx.channel, new_embed=embed, message=ctx.message, force_send=True)

    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.user)
    @commands.command(aliases=['list', 'q', "songlist", "sl"])
    async def queue(self, ctx, page: int = 1):
        """
            {command_prefix}queue
            {command_prefix}queue [page]

        {help}
        """
        player = await self.get_player(ctx.guild)

        if not player.queue:
            return await ctx.invoke(self.current_song)

        if not player.current:  # it can happen, but not commun
            return await ctx.send(get_str(ctx, "not-playing"), delete_after=20)

        pos = lavalink.utils.format_time(
            player.position).lstrip('0').lstrip(':')

        requester = await self.bot.safe_fetch('member', player.current.requester, guild=ctx.guild)

        if not player.current.stream:
            # prog_bar_str = sweet_bar(player.position, player.current.duration)
            duration = lavalink.utils.format_time(
                player.current.duration).lstrip('0').lstrip(':')

        else:
            if "listen.moe" in player.current.uri.lower() or ('monstercat' in player.current.uri.lower() and 'twitch' in player.current.uri.lower()):
                self.radio_update(player.current)
            duration = 'LIVE'

        msg = f"{'⏸' if player.paused else '🔁' if player.repeat else ''}`[{pos}/{duration}]` " + f" **[{player.current.title}]({player.current.uri})** " + get_str(
            ctx, "music-queue-added-by") + f" **{requester.name}**.\n\n"

        items_per_page = 10
        pages = math.ceil(len(player.queue) / items_per_page)
        if page > pages:
            page = pages
        elif page < 1:
            page = 1
        start = (page - 1) * items_per_page
        end = start + items_per_page

        for i, track in enumerate(player.queue[start:end], start=start):
            max_val = len(str(len(player.queue[start:end]) + start))
            str_index = str(i + 1)
            str_index = "".join(
                [' ' for x in range(max_val - len(str_index))]) + str_index
            # better than having an error
            requester = await self.bot.safe_fetch('member', track.requester, guild=ctx.guild) or ctx.author
            line = "`{}.` **[{}]({})** {} ".format(str_index, track.title.replace('[', '').replace(']', '').replace('*', '')[:40], track.uri,
                                                   get_str(ctx, "music-queue-added-by"))
            msg += line
            available_spaces = 67 - \
                len(line) + len(track.uri) + 8  # cus of the **
            if requester:
                msg += f"**{requester.name[:available_spaces]}**.\n"

        embed = discord.Embed(title=None, description=msg, color=self.get_color(
            ctx.guild))  # Specify title to avoid issue when editing
        bottom = ''

        if pages > 1:
            bottom = f'{page}/{pages}'
            if (items_per_page * page) < len(player.queue):
                rest = len(player.queue) - (items_per_page * page)
                bottom += " ..." + \
                    get_str(ctx, "music-queue-not-displayed",
                            can_owo=False).format(rest) + '. - '

        position, time_until = await self.get_position_in_queue(ctx, player)
        bottom += f'{time_until}'
        embed.set_footer(text=bottom)

        await self.send_new_np_msg(player, ctx.channel, new_embed=embed, message=ctx.message)

    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.guild)
    @commands.command(name='pause', aliases=['resume'])
    async def pause_song(self, ctx):
        """
            {command_prefix}pause

        {help}
        """
        if not await self.is_dj(ctx):
            raise commands.errors.CheckFailure

        player = await self.get_player(ctx.guild)

        if not ctx.guild.me.voice:
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

        my_vc = ctx.guild.me.voice.channel

        if not sum(1 for m in my_vc.members if not (m.voice.deaf or m.bot or m.voice.self_deaf)):
            if ctx.author not in my_vc.members or (ctx.author.voice.self_deaf or ctx.author.voice.deaf):
                return await ctx.send(get_str(ctx, "music-not-my-channel").format(f"**{my_vc}**"), delete_after=30)

        if not player.is_playing:
            return await ctx.send(get_str(ctx, "not-playing"), delete_after=20)

        if player.paused:
            await player.set_pause(False)
            await ctx.send(get_str(ctx, "music-resume-success").format(f"**{ctx.author}**"))
        else:
            await player.set_pause(True)
            await ctx.send(get_str(ctx, "music-pause-success").format(f"**{ctx.author}**"))

    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.guild)
    @commands.command(name='volume', aliases=['vol', 'v'])
    async def volume(self, ctx, new_volume=None):
        """
            {command_prefix}volume (+/-)[volume]
            {command_prefix}volume

        {help}
        """
        player = await self.get_player(ctx.guild)
        original_content = new_volume

        if not player.is_connected:
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

        if not await self.is_dj(ctx):
            raise commands.errors.CheckFailure

        channel = ctx.channel
        claimed_server = await self.bot.server_is_claimed(ctx.guild.id)

        if claimed_server:
            max_volume = 1000
        else:
            # Keep the result: Smart way to only do 1 api call.
            fetched_member = await is_voter(self.bot, ctx.author, fetch=True)
            if fetched_member:
                max_volume = 150
                if await is_basicpatron(self.bot, ctx.author, resp=fetched_member):
                    max_volume = 200
                    if await is_patron(self.bot, ctx.author, resp=fetched_member):
                        max_volume = 1000
            else:
                max_volume = 100

        if not new_volume:
            prog_bar_str = sweet_bar(player.volume, max_volume)
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(f'`🔈 {player.volume}%` {prog_bar_str}')

        relative = False

        try:
            while new_volume[-1] in '%':
                new_volume = new_volume[:-1]
        except IndexError:
            return await ctx.send(get_str(ctx, "music-volume-invalid-number").format(f"`{original_content}`"))

        if new_volume[0] in '+-':
            relative = True

        try:
            new_volume = int(new_volume)
        except ValueError:
            return await ctx.send(get_str(ctx, "music-volume-invalid-number").format(f"`{new_volume}`"))

        if relative:
            vol_change = new_volume
            new_volume += player.volume

        old_volume = int(player.volume)

        if 0 <= new_volume <= max_volume:
            prog_bar_str = sweet_bar(new_volume, max_volume)
            if old_volume == new_volume:
                ctx.command.reset_cooldown(ctx)
                return await ctx.send('`🔈 %d%%` {progress_bar}'.format(progress_bar=prog_bar_str) % (player.volume))
            await player.set_volume(new_volume)
            return await channel.send(get_str(ctx, "music-volume-updated", can_owo=False).format(f"**{old_volume}%**", f"**{new_volume}%**") + '\n`🔈 {}%` {progress_bar}'.format(new_volume, progress_bar=prog_bar_str))
        else:
            if 9000 < new_volume:
                return await ctx.send("OMG IT'S OVER NINE THOUSAND !!!")
            if 100 <= new_volume <= 1000:
                e = discord.Embed(description=get_str(ctx, "music-volume-higher-than-100") + "\n\n" +
                                  "**[Patreon](https://www.patreon.com/watora)**\n**[Vote (volume up to 150)](https://discordbots.org/bot/220644154177355777)**")
                try:
                    await ctx.send(embed=e)
                except discord.Forbidden:
                    await ctx.send(content=get_str(ctx, "music-volume-higher-than-100") + "\n<https://www.patreon.com/watora>\nVolume up to 150 : <https://discordbots.org/bot/220644154177355777>")

            elif relative:
                await ctx.send(get_str(ctx, "music-volume-unreasonable-volume-relative").format(old_volume, vol_change, old_volume + vol_change, 0 - old_volume, max_volume - old_volume), delete_after=20)
            else:
                if await is_patron(self.bot, ctx.author):
                    await ctx.send(get_str(ctx, "music-volume-unreasonable-volume-patreon").format(new_volume, max_volume), delete_after=20)
                else:
                    await ctx.send(get_str(ctx, "music-volume-unreasonable-volume").format(new_volume, max_volume), delete_after=20)

    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.guild)
    @commands.command()
    async def shuffle(self, ctx):
        """
            {command_prefix}shuffle

        {help}
        """
        if not await self.is_dj(ctx):
            raise commands.errors.CheckFailure

        player = await self.get_player(ctx.guild)

        if not player.is_connected:
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

        if not player.queue:
            return await ctx.send(get_str(ctx, "music-shuffle-empty"))

        random.shuffle(player.queue)

        # useless but fun part from now
        cards = [':spades:', ':clubs:', ':hearts:', ':diamonds:']
        hand = await ctx.send(' '.join(cards))
        await asyncio.sleep(0.6)

        for x in range(4):
            random.shuffle(cards)
            await hand.edit(content=' '.join(cards))
            await asyncio.sleep(0.6)
        try:
            await hand.delete()
        except discord.HTTPException:
            pass
        await ctx.send(get_str(ctx, "music-shuffle-shuffled"))

    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.guild)
    @commands.command(name='repeat', aliases=['loopqueue', 'loop', 'queueloop'])
    async def repeat(self, ctx):
        """
            {command_prefix}repeat

        {help}
        """
        player = await self.get_player(ctx.guild)

        if not player.is_connected:
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

        if not await self.is_dj(ctx):
            raise commands.errors.CheckFailure

        if not player.current:
            return await ctx.send(get_str(ctx, "not-playing"), delete_after=20)

        player.repeat = not player.repeat
        if player.repeat:
            await ctx.send(get_str(ctx, "music-repeat-enabled"))
        else:
            await ctx.send(get_str(ctx, "music-repeat-disabled"))

    @commands.command(name='remove', aliases=["rem"])
    async def remove_from_playlist(self, ctx, position: int = None, after: int = None):
        """
            {command_prefix}remove [first_position_in_queue] [second_position_in_queue]
            {command_prefix}remove [position_in_queue]
            {command_prefix}remove

        {help}
        """
        player = await self.get_player(ctx.guild)

        if not ctx.guild.me.voice:
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

        my_vc = ctx.guild.me.voice.channel

        if not await self.is_dj(ctx):
            if ctx.author not in my_vc.members or (ctx.author.voice.self_deaf or ctx.author.voice.deaf):
                return await ctx.send(get_str(ctx, "music-not-my-channel").format(f"**{my_vc}**"), delete_after=30)

        if not player.queue:
            return await ctx.send(get_str(ctx, "music-remove-empty"))

        removed = 0
        nb = len(player.queue)

        if after and after != position:
            if not await self.is_dj(ctx):
                raise commands.errors.CheckFailure
            if after > 1:
                if after > nb:
                    after = nb
                after -= 1
            if 1 <= position <= nb and 1 <= after <= nb:
                position -= 1
                for index in range(position, (after + 1)):
                    del player.queue[index - removed]
                    removed += 1
            else:
                return await ctx.send(get_str(ctx, "music-promote-error").format(nb))

        if position is None:  # can be 0
            position = nb

        if not removed:
            if 1 <= position <= nb:
                position -= 1
                song = player.queue[position]
                title = song.title
                if not await self.is_dj(ctx):
                    if song.requester != ctx.author.id:
                        raise commands.errors.CheckFailure
                del player.queue[position]
            else:
                return await ctx.send(get_str(ctx, "music-promote-error").format(nb))

            return await ctx.send(get_str(ctx, "music-remove-removed").format(f"**{title}**"))
        else:
            await ctx.send(get_str(ctx, "music-remove-removed-multiples").format(f"**{removed}**"))

    @commands.command(aliases=["up", "mov", "move"])
    async def promote(self, ctx, position: int = None, after: int = None):
        """
            {command_prefix}promote [song_position_in_queue] [position_in_queue_after]
            {command_prefix}promote [song_position_in_queue]
            {command_prefix}promote

        {help}
        """

        player = await self.get_player(ctx.guild)

        nb = len(player.queue)

        if not player.is_connected:
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

        if not player.queue:
            return await ctx.send(get_str(ctx, "music-promote-empty"))

        if not await self.is_dj(ctx):
            raise commands.errors.CheckFailure

        if position is None:
            position = nb

        if 1 <= position <= nb:
            position -= 1
            song = player.queue[position]
            title = song.title

            del player.queue[position]

        else:
            return await ctx.send(get_str(ctx, "music-promote-error").format(nb))
        if after:
            if after < 1:
                after = 0
            else:
                if after > (len(player.queue) + 1):  # we removed an object before
                    after = (len(player.queue) + 1)
                after -= 1
        else:
            after = 0
        player.queue.insert(after, song)
        if after == 0:
            await ctx.send(get_str(ctx, "music-promote-promoted").format(f"**{title}**"))
        else:
            await ctx.send(get_str(ctx, "music-promote-promoted-to").format(f"**{title}**", f"`{after+1}`"))

    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.guild)
    @commands.command(name='stop', aliases=['disconnect', 'fuckoff', 'leave', 'deco', 'quit', "voicedisconnect", "voiceleave", "leavevoice", "deconnexion"])
    async def stop_player(self, ctx, force=None):
        """
            {command_prefix}stop

        {help}
        """
        player = await self.get_player(ctx.guild)

        if not ctx.guild.me.voice:
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

        stop_votes = player.stop_votes

        if not await self.is_dj(ctx):
            my_vc = ctx.guild.me.voice.channel
            if ctx.author not in my_vc.members or (ctx.author.voice.self_deaf or ctx.author.voice.deaf):
                return await ctx.send(get_str(ctx, "not-the-right-channel"))
            if player.is_playing:
                mbrs = my_vc.members
                settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
                percent = settings.vote
                reqvotes = (
                    (len([1 for m in mbrs if not m.bot and not m.voice.self_deaf and not m.voice.deaf])) / (100 / percent))
                voter = ctx.message.author
                if voter.id not in stop_votes:
                    stop_votes.add(voter.id)
                    total_votes = len(stop_votes)
                    if total_votes < math.ceil(reqvotes):
                        if total_votes == 1:
                            await ctx.send(get_str(ctx, "music-stop-song-running"))
                        return await ctx.send(get_str(ctx, "music-stop-vote") + ' **[{}/{}]**'.format(total_votes, math.ceil(reqvotes)))
                else:
                    return await ctx.send(get_str(ctx, "music-stop-already"))

        await self.disconnect_message(player, ctx.guild, channel=ctx.channel, inactivity=False)
        await self.disconnect_player(player)

    @commands.command(name='join', aliases=['summon', 'fuckon', 'connect', 'come', 'spawn'])
    async def voice_connect(self, ctx, *, channel: discord.VoiceChannel = None):
        """
            {command_prefix}join
            {command_prefix}join [voice_channel]

        {help}
        """
        if not channel:
            try:
                channel = ctx.author.voice.channel
            except AttributeError:
                try:
                    channel = ctx.me.voice.channel
                except AttributeError:
                    raise NoVoiceChannel(get_str(ctx, "music-join-no-channel"))

        if not channel.permissions_for(ctx.me).connect:
            raise NoVoiceChannel(get_str(ctx, "need-connect-permission"))
        if not channel.permissions_for(ctx.me).speak:
            raise NoVoiceChannel(get_str(ctx, "need-speak-permission"))

        player = await self.get_player(ctx.guild, True, ctx.author.id)

        if not ctx.guild.me.voice:
            await self.connect_player(ctx, player, channel.id)
            try:
                await ctx.message.add_reaction("☑")
            except discord.Forbidden:
                await ctx.send(get_str(ctx, "music-join-success").format(f"**{channel}**"), delete_after=15)
        else:
            my_vc = ctx.guild.me.voice.channel
            if my_vc == channel:
                if player.connected_channel:
                    return
            elif not await self.is_dj(ctx):
                if my_vc != ctx.author.voice.channel:
                    if (player.is_playing or player.queue) and not player.paused:
                        if sum(1 for m in player.connected_channel.members if not (m.voice.deaf or m.bot or m.voice.self_deaf)):
                            raise NoVoiceChannel(
                                get_str(ctx, "music-join-playing-a-song"))

            await player.connect(channel.id)
            await ctx.send(get_str(ctx, "music-join-moved-success").format(f"**{channel}**"), delete_after=15)

        tries = 0

        while not ctx.guild.me.voice and tries < 5:
            # Wait till the player connects to discord.. REE..
            await asyncio.sleep(tries)
            tries += 0.5

        return player

    @commands.command(aliases=['lyric', 'l', 'lyc', 'paroles', 'parole'])
    @commands.cooldown(rate=1, per=5.0, type=commands.BucketType.guild)
    async def lyrics(self, ctx, *, song_url=None):
        """
            {command_prefix}lyrics [key_words]
            {command_prefix}lyrics [url]
            {command_prefix}lyrics

        {help}
        """
        if not song_url:
            player = await self.get_player(ctx.guild)
            if not player.is_connected:
                return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)
        matchUrl = False
        if song_url:
            matchUrl = match_url(song_url)
        if song_url and matchUrl:
            title = await self.get_title(ctx, query=song_url)
            if not title:
                return await ctx.send(get_str(ctx, "music-lyrics-title-not-find"))
        elif song_url and not matchUrl:
            title = song_url
        elif song_url is None and player.is_playing:
            title = player.current.title
        else:
            return await ctx.send(get_str(ctx, "not-playing"), delete_after=20)

        await ctx.trigger_typing()

        if "opening" in title.lower() or "ending" in title.lower():  # fucking weebs
            try:
                if "opening" not in title.lower().split(":")[1] and "ending" not in title.lower().split(":")[1]:
                    title = title.split(":")[1]
                else:
                    title = title.split(":")[0]
            except IndexError:
                try:
                    if "opening" not in title.lower().split("-")[1] and "ending" not in title.lower().split("-")[1]:
                        title = title.split("-")[1]
                    else:
                        title = title.split("-")[0]
                except IndexError:
                    pass
        title = re.sub(r'\([^)]*\)', '', title)  # remove (text)
        title = re.sub(r'\[[^\]]*\]', '', title)  # remove [text]

        data = await self.get_lyrics(title, self.bot.tokens['GENIUS'])
        error = data.get("error")

        if error:
            return await ctx.send(get_str(ctx, "music-lyrics-not-found"))

        lyrics_paginator = Paginator(ctx=ctx, items=split_str_lines(
            data["lyrics"]), items_per_page=1, data=data)
        await lyrics_paginator.send_to_channel()

    @commands.command(aliases=['eq'])
    async def equalizer(self, ctx, band: int = None, gain: float = None):
        """
            {command_prefix}equalizer [band] [gain]
            {command_prefix}equalizer

        {help}
        """
        player = await self.get_player(ctx.guild)

        if not player.is_connected:
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

        if not await self.is_dj(ctx):
            raise commands.errors.CheckFailure

        if band is not None and gain is not None:  # cus can be 0
            gain = max(min(gain, 1.0), -0.25)
            band = max(min(band, 14), 0)
            await player.set_gain(band, gain)
            await ctx.send(get_str(ctx, "music-equalizer-set").format(f'`{band}`', f'`{"+" if gain >= 0 else "-"}{gain}`'))
            embed = Equalizer(ctx, player).embed
            return await ctx.send(embed=embed, delete_after=5)

        eq = Equalizer(ctx, player)
        await eq.send_to_channel()

    @commands.group(aliases=['playlist', 'autoplaylist', "ap", "apl"], invoke_without_command=True)
    async def pl(self, ctx, *, name=None):
        """
            {command_prefix}pl new
            {command_prefix}pl start
            {command_prefix}pl add
            {command_prefix}pl remove
            {command_prefix}pl now
            {command_prefix}pl off
            {command_prefix}pl repair
            {command_prefix}pl info
            {command_prefix}pl clear
            {command_prefix}pl clone
            {command_prefix}pl settings
            {command_prefix}pl find
            {command_prefix}pl upvote

        {help}
        """
        if not ctx.invoked_subcommand:
            await ctx.invoke(self.plstart, file_name=name)

    @pl.command(name='off', aliases=['stop', 'o', 'not', "end"])
    async def pl_off(self, ctx):
        """
            {command_prefix}pl off

        {help}
        """
        await ctx.invoke(self.ploff)

    @commands.command(aliases=['plstop', 'plnot', "plend"])
    async def ploff(self, ctx):
        """
            {command_prefix}ploff

        {help}
        """
        player = await self.get_player(ctx.guild)

        if not ctx.guild.me.voice:
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

        my_vc = ctx.guild.me.voice.channel

        if not await self.is_dj(ctx):
            if ctx.author not in my_vc.members or (ctx.author.voice.self_deaf or ctx.author.voice.deaf):
                return await ctx.send(get_str(ctx, "music-not-my-channel").format(f"**{my_vc}**"), delete_after=30)

        player.autoplaylist = None
        await ctx.send(get_str(ctx, "music-ploff-disabled"), delete_after=20)

    @pl.command(name='now', aliases=['atm', 'current'])
    async def pl_now(self, ctx):
        """
            {command_prefix}pl now

        {help}
        """
        await ctx.invoke(self.plnow)

    @commands.command(aliases=['platm', 'plcurrent'])
    async def plnow(self, ctx):
        """
            {command_prefix}plnow

        {help}
        """
        player = await self.get_player(ctx.guild)

        if not player.is_connected:
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

        if not player.autoplaylist:
            return await ctx.send(get_str(ctx, "music-plnow-no-pl").format("`{}pl start`".format(get_server_prefixes(ctx.bot, ctx.guild))))

        settings = await SettingsDB.get_instance().get_glob_settings()

        try:
            settings.autoplaylists[player.autoplaylist['name'].lower()]
        except KeyError:  # can happen after plclear
            return await ctx.send(get_str(ctx, "music-plsettings-got-deleted"))

        if player.autoplaylist['is_personal']:
            id = int(player.autoplaylist['name'].lower())
            user = await self.bot.safe_fetch('member', id, guild=ctx.guild)
            if user:
                user = user.name
            else:
                user = player.autoplaylist['created_by_name']
            if player.list:
                await ctx.send(get_str(ctx, "music-plnow-now-user-auto").format(f"**{user}**", len(player.autoplaylist['songs']) - len(player.list), len(player.autoplaylist['songs'])))
            else:
                await ctx.send(get_str(ctx, "music-plnow-now-user").format(f"**{user}**"))
        else:
            if player.list:
                await ctx.send(get_str(ctx, "music-plnow-now-auto").format(f"**{player.autoplaylist['name']}**", len(player.autoplaylist['songs']) - len(player.list), len(player.autoplaylist['songs'])))
            else:
                await ctx.send(get_str(ctx, "music-plnow-now").format(f"**{player.autoplaylist['name']}**"))

    @pl.command(name='start', aliases=['s', 'launch', 'p', 'play'])
    async def pl_start(self, ctx, *, file_name=None):
        """
            {command_prefix}pl start [name]
            {command_prefix}pl start [@user]
            {command_prefix}pl start

        {help}
        """
        await ctx.invoke(self.plstart, file_name=file_name)

    @commands.command(aliases=['boost', 'bass', 'bb'])
    async def bassboost(self, ctx, level: str = None):
        """
            {command_prefix}bassboost [level]
            {command_prefix}bassboost

        {help}
        """
        player = await self.get_player(ctx.guild)

        if not player.is_connected:
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

        if not await self.is_dj(ctx):
            raise commands.errors.CheckFailure

        if not level:
            for k, v in self.bassboost_levels.items():
                if [(0, player.equalizer[0]), (1, player.equalizer[1])] == v:
                    level = k
            await ctx.send(get_str(ctx, "music-bass-boost-now").format(f'`{level}`' if level else '`CUSTOM`'))
            embed = Equalizer(ctx, player).embed
            return await ctx.send(embed=embed, delete_after=5)

        gain = None

        for k in self.bassboost_levels.keys():
            if k.startswith(level.upper()):
                gain = self.bassboost_levels[k]
                break

        if not gain:
            return await ctx.send(get_str(ctx, "command-invalid-usage").format(f'{get_server_prefixes(ctx.bot, ctx.guild)}help bassboost'))

        await player.reset_equalizer()
        await player.set_gains(*gain)

        await ctx.send(get_str(ctx, "music-bass-boost-set").format(f'`{k}`'))
        embed = Equalizer(ctx, player).embed
        return await ctx.send(embed=embed, delete_after=5)

    @commands.command(aliases=['pls', 'pllaunch', 'plplay', 'plp'])
    async def plstart(self, ctx, *, file_name=None):
        """
            {command_prefix}plstart [name]
            {command_prefix}plstart [@user]
            {command_prefix}plstart

        {help}
        """
        if file_name and file_name.lower() == 'help':  # this is stupid
            return await self.bot.send_cmd_help(ctx)

        if not ctx.me.voice or ctx.guild.id not in self.bot.lavalink.players.players:
            try:
                player = await ctx.invoke(self.voice_connect)
            except NoVoiceChannel:
                ctx.command.reset_cooldown(ctx)
                return await ctx.send(get_str(ctx, "music-join-no-channel"))
            except lavalink.NodeException:
                return await ctx.send(get_str(ctx, "music-nodes-unavailable"))
            if not player:
                return
        else:
            player = await self.get_player(ctx.guild)

        if not ctx.guild.me.voice:
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

        my_vc = ctx.guild.me.voice.channel

        if not await self.is_dj(ctx):
            if ctx.author not in my_vc.members or (ctx.author.voice.self_deaf or ctx.author.voice.deaf):
                return await ctx.send(get_str(ctx, "music-not-my-channel").format(f"**{my_vc}**"), delete_after=30)

        if ctx.message.mentions:
            user = ctx.message.mentions[-1]
            if user.mention not in file_name:  # It was a prefix
                user = None
                if len(ctx.message.mentions) > 1:
                    user = ctx.message.mentions[0]
            if user:
                file_name = str(user.id)

        settings = await SettingsDB.get_instance().get_glob_settings()

        # Verify file name was provided
        if file_name:
            file_name_original = file_name
            file_name = str(file_name.lower())

            perso = await self.is_perso(ctx.guild, name=file_name)

            if str(file_name) not in settings.autoplaylists:
                if perso:
                    return await ctx.send(get_str(ctx, "music-plstart-dont-have"))
                file_name = format_mentions(file_name_original)
                return await ctx.send(get_str(ctx, "music-plstart-doesnt-exists").format(f"**{file_name}**", "`{}plnew`".format(get_server_prefixes(ctx.bot, ctx.guild))), delete_after=30)

            player.autoplaylist = settings.autoplaylists[file_name]
            player.list = None
            player.authorplaylist = ctx.author

            if perso:
                if perso != ctx.author:
                    await ctx.send(get_str(ctx, "music-plstart-loaded-user").format(f"**{perso.name}**"))
                else:
                    await ctx.send(get_str(ctx, "music-plstart-your-loaded"))
            else:
                await ctx.send(get_str(ctx, "music-plstart-loaded").format(f"**{player.autoplaylist['name']}**"))

            await ctx.invoke(self.plsettings, name=file_name)
            await self.autoplaylist_loop(player)

        else:
            if str(ctx.author.id) not in settings.autoplaylists:
                await ctx.invoke(self.plnew, file_name=str(ctx.author.id))
            await ctx.invoke(self.plstart, file_name=str(ctx.author.id))

    @pl.command(name='new', aliases=['create'])
    async def pl_new(self, ctx, *, file_name):
        """
            {command_prefix}pl new [name]

        {help}
        """
        await ctx.invoke(self.plnew, file_name=file_name)

    @commands.command(aliases=['plcreate'])
    async def plnew(self, ctx, *, file_name):
        """
            {command_prefix}plnew [name]

        {help}
        """
        file_name_original = file_name
        file_name = str(file_name.lower())

        if illegal_char(file_name):
            return await ctx.send(get_str(ctx, "music-plnew-special-char"))

        is_perso = await self.is_perso(ctx.guild, name=file_name)

        if str(file_name).isdigit() and 20 > len(file_name) > 16:
            if int(file_name) != ctx.author.id and ctx.author.id != owner_id:
                return await ctx.send(get_str(ctx, "music-plnew-try-to-hack"))

        settings = await SettingsDB.get_instance().get_glob_settings()

        if file_name in settings.autoplaylists:
            file_name = format_mentions(file_name)
            return await ctx.send(get_str(ctx, "music-plnew-already-exists").format(f"**{file_name}**"))

        settings.autoplaylists[file_name] = {}
        settings.autoplaylists[file_name]['songs'] = []
        settings.autoplaylists[file_name]['name'] = file_name_original
        settings.autoplaylists[file_name]['created_by'] = str(ctx.author.id)
        settings.autoplaylists[file_name]['created_by_name'] = str(ctx.author)
        settings.autoplaylists[file_name]['created_date'] = datetime.today().strftime(
            "%d %b %Y")
        settings.autoplaylists[file_name]['private'] = True
        settings.autoplaylists[file_name]['shuffle'] = True
        settings.autoplaylists[file_name]['whitelist'] = []
        if is_perso:
            settings.autoplaylists[file_name]['is_personal'] = True
        else:
            settings.autoplaylists[file_name]['is_personal'] = False
            file_name = format_mentions(file_name_original)
            await ctx.send(get_str(ctx, "music-plnew-created").format(f"**{file_name_original}**"))

        await SettingsDB.get_instance().set_glob_settings(settings)

    @pl.command(name='clear', aliases=['erase', 'removeall', 'deleteall', 'reset'])
    async def pl_clear(self, ctx, *, file_name=None):
        """
            {command_prefix}pl clear [name]
            {command_prefix}pl clear

        {help}
        """
        await ctx.invoke(self.plclear, file_name=file_name)

    @commands.command(aliases=['plerase', 'plremoveall', 'pldeleteall', 'plreset'])
    async def plclear(self, ctx, *, file_name=None):
        """
            {command_prefix}plclear [name]
            {command_prefix}plclear

        {help}
        """
        settings = await SettingsDB.get_instance().get_glob_settings()

        if not file_name:
            player = await self.get_player(ctx.guild)
            if not player.is_connected:
                return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)
            if not player.autoplaylist:
                return await ctx.send(get_str(ctx, "music-pl-disabled").format("`{}plstart`".format(get_server_prefixes(ctx.bot, ctx.guild))))

            try:
                settings.autoplaylists[player.autoplaylist['name'].lower()]
            except KeyError:  # can happen after plclear
                return await ctx.send(get_str(ctx, "music-plsettings-got-deleted"))

            file_name = player.autoplaylist['name'].lower()

        if ctx.message.mentions:
            user = ctx.message.mentions[-1]
            if user.mention not in file_name:  # It was a prefix
                user = None
                if len(ctx.message.mentions) > 1:
                    user = ctx.message.mentions[0]
            if user:
                file_name = str(user.id)

        file_name = str(file_name.lower())

        if illegal_char(file_name):
            return await ctx.send(get_str(ctx, "music-plnew-special-char"))

        perso = await self.is_perso(ctx.guild, name=file_name)

        if perso:
            if int(file_name) != ctx.author.id and ctx.author.id != owner_id:
                return await ctx.send(get_str(ctx, "music-plrepair-someone"))

        if file_name not in settings.autoplaylists:
            file_name = format_mentions(file_name)
            return await ctx.send(get_str(ctx, "music-plstart-doesnt-exists").format(f"**{file_name}**", "`{}plnew`".format(get_server_prefixes(ctx.bot, ctx.guild))), delete_after=30)

        if settings.autoplaylists[file_name]['private']:
            if int(settings.autoplaylists[file_name]['created_by']) != ctx.author.id and ctx.author.id != owner_id:
                return await ctx.send(get_str(ctx, "music-autoplaylist-noten-perms"))

        if perso:
            msg_name = get_str(ctx, "music-plclear-your-p-a")
        else:
            msg_name = file_name

        confirm_message = await ctx.send(get_str(ctx, "music-plclear-confirmation").format(msg_name))

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
            return await ctx.send(get_str(ctx, "music-plclear-cancelled"), delete_after=30)

        if response_message.content.lower().startswith('y'):
            del settings.autoplaylists[file_name]
            await SettingsDB.get_instance().set_glob_settings(settings)
            await ctx.send(get_str(ctx, "music-plclear-cleared").format(msg_name))
        else:
            await ctx.send(get_str(ctx, "music-plclear-cancelled"), delete_after=30)

    @pl.command(name='clone', aliases=['copy'])
    async def pl_clone(self, ctx, *, file_name=None):
        """
            {command_prefix}pl clone [name]
            {command_prefix}pl clone

        {help}
        """
        await ctx.invoke(self.plclone, file_name=file_name)

    @commands.command(aliases=['copy'])
    async def plclone(self, ctx, *, file_name=None):
        """
            {command_prefix}plclear [name]
            {command_prefix}plclear

        {help}
        """
        if not file_name:
            player = await self.get_player(ctx.guild)
            if not player.is_connected:
                return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)
            if not player.autoplaylist:
                return await ctx.send(get_str(ctx, "music-pl-disabled").format("`{}plstart`".format(get_server_prefixes(ctx.bot, ctx.guild))))
            file_name = player.autoplaylist['name'].lower()

        if ctx.message.mentions:
            user = ctx.message.mentions[-1]
            if user.mention not in file_name:  # It was a prefix
                user = None
                if len(ctx.message.mentions) > 1:
                    user = ctx.message.mentions[0]
            if user:
                file_name = str(user.id)

        perso = await self.is_perso(ctx.guild, name=file_name)

        file_name = str(file_name.lower())

        if illegal_char(file_name):
            return await ctx.send(get_str(ctx, "music-plnew-special-char"))

        settings = await SettingsDB.get_instance().get_glob_settings()

        if file_name not in settings.autoplaylists:
            file_name = format_mentions(file_name)
            return await ctx.send(get_str(ctx, "music-plstart-doesnt-exists").format(f"**{file_name}**", "`{}plnew`".format(get_server_prefixes(ctx.bot, ctx.guild))), delete_after=30)

        if perso:
            msg_name = get_str(ctx, "music-plclear-your-p-a")
            # as this is the first word
            msg_name = msg_name[0].upper() + msg_name[1:]
        else:
            msg_name = file_name

        confirm_message = await ctx.send(get_str(ctx, "music-plclone-confirmation").format(msg_name))

        def check(m):
            if m.author.bot or m.author != ctx.author:
                return False
            if m.channel != ctx.channel:
                return False
            if m.content:
                return True
            return False

        try:
            response_message = await self.bot.wait_for('message', timeout=30, check=check)
        except asyncio.TimeoutError:
            try:
                await confirm_message.delete()
            except discord.HTTPException:
                pass
            return await ctx.send(get_str(ctx, "music-plclone-cancelled"), delete_after=30)

        if not response_message.content.startswith(get_server_prefixes(ctx.bot, ctx.guild)) or response_message.content.lower().startswith('exit'):
            if response_message.mentions:
                if response_message.mentions:
                    mentio = response_message.mentions[-1]
                if mentio.id != ctx.author.id and ctx.author.id != owner_id:
                    return await ctx.send(get_str(ctx, "music-plnew-try-to-hack"))
                response_message.content = str(mentio.id)

            if illegal_char(response_message.content):
                return await ctx.send(get_str(ctx, "music-plnew-special-char"))

            fileName = response_message.content.lower()

            # Check to make sure there isn't already a file with the same name
            if fileName in settings.autoplaylists:
                return await ctx.send(get_str(ctx, "music-plnew-already-exists").format(f"**{response_message.content}**"))

            if await self.is_perso(ctx.guild, name=fileName):
                if int(fileName) != ctx.author.id and ctx.author.id != owner_id:
                    return await ctx.send(get_str(ctx, "music-plrepair-someone"))

            if response_message.content:
                await ctx.invoke(self.plnew, file_name=fileName)
                settings = await SettingsDB.get_instance().get_glob_settings()
                settings.autoplaylists[fileName]['songs'] = settings.autoplaylists[file_name]['songs']
                await SettingsDB.get_instance().set_glob_settings(settings)
                await ctx.send(get_str(ctx, "music-plclone-cloned").format(msg_name, response_message.content))
        else:
            await ctx.send(get_str(ctx, "music-plclone-cancelled"), delete_after=30)

    async def explosion_check(self, ctx):
        bucket = self._cd.get_bucket(ctx.message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            raise commands.errors.CommandOnCooldown(bucket, retry_after)
        return True

    async def skip_explosion_check(self, ctx):
        bucket = self._skip_cd.get_bucket(ctx.message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            raise commands.errors.CommandOnCooldown(bucket, retry_after)
        return True

    @pl.command(name='info', aliases=["about", "content", "songlist", "queue"])
    async def pl_info(self, ctx, *, name=None):
        """
            {command_prefix}pl info [@user]
            {command_prefix}pl info [autoplaylist_name]
            {command_prefix}pl info

        {help}
        """
        await ctx.invoke(self.plinfo, name=name)

    @commands.command(aliases=['infopl'])
    async def plinfo(self, ctx, *, name=None):
        """
            {command_prefix}plinfo [@user]
            {command_prefix}plinfo [autoplaylist_name]
            {command_prefix}plinfo

        {help}
        """
        await self.explosion_check(ctx)

        settings = await SettingsDB.get_instance().get_glob_settings()

        if not name:
            try:
                player = await self.get_player(ctx.guild)
            except NoVoiceChannel:
                self._cd.get_bucket(ctx.message).reset()
                raise NoVoiceChannel(get_str(ctx, "not-connected"))
            if not player.is_connected:
                self._cd.get_bucket(ctx.message).reset()
                return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)
            if not player.autoplaylist:
                self._cd.get_bucket(ctx.message).reset()
                return await ctx.send(get_str(ctx, "music-pl-disabled").format("`{}plstart`".format(get_server_prefixes(ctx.bot, ctx.guild))))
            name = player.autoplaylist['name'].lower()
            try:
                settings.autoplaylists[name]
            except KeyError:  # can happen after plclear
                return await ctx.send(get_str(ctx, "music-plsettings-got-deleted"))

        total = ""
        name = str(name.lower())
        banane = []
        dead = 0
        already_send = False

        if ctx.message.mentions:
            user = ctx.message.mentions[-1]
            if user.mention not in name:  # It was a prefix
                user = None
                if len(ctx.message.mentions) > 1:
                    user = ctx.message.mentions[0]
            if user:
                name = str(user.id)

        if name not in settings.autoplaylists:
            self._cd.get_bucket(ctx.message).reset()
            return await ctx.send(get_str(ctx, "music-plinfo-not-found"))

        is_perso = await self.is_perso(ctx.guild, name=name)

        if is_perso:
            user_name = is_perso.name

        n = len(settings.autoplaylists[name]['songs'])
        if n >= 1000:
            return await ctx.send(f'Your playlist has too many songs ! `{n}/1000` I can\'t display it! Remove some song if you want to use this command.')

        load_content = get_str(ctx, "music-plinfo-loading")
        load = await ctx.send(load_content)

        if n == 0:
            self._cd.get_bucket(ctx.message).reset()
            return await load.edit(content=get_str(ctx, "music-plinfo-empty-auto").format("`{}pladd`".format(get_server_prefixes(ctx.bot, ctx.guild))))

        if n <= 15:
            youtube_ids = []
            already_find = {}
            for url in settings.autoplaylists[name]['songs']:
                if 'youtu' in url:
                    id = url.split('?v=')[-1].split('?')[0].split('/')[-1]
                    youtube_ids.append(id)
            if youtube_ids:
                already_find = await self.youtube_api.get_youtube_title(id=youtube_ids)

            for r, url in enumerate(settings.autoplaylists[name]['songs'], start=1):
                title = ''
                if 'youtu' in url:
                    id = url.split('?v=')[-1].split('?')[0].split('/')[-1]
                    if id in already_find:
                        title = already_find[id]

                if not title:
                    title = await self.get_title(ctx, query=url)
                if not title:
                    title = "`" + get_str(ctx, "music-plinfo-not-accessible").format(
                        "{}PLREMOVE".format(get_server_prefixes(ctx.bot, ctx.guild))) + "`"
                    dead += 1
                total += "``{}.`` **{}**\n".format(
                    r, f"[{title.replace('[', '').replace(']', '').replace('*', '')[:70]}]({url})")
                info = get_str(ctx, f"{'music-plinfo-perso-display' if is_perso and user_name else 'music-plinfo-display'}").format(
                    f"**{user_name if is_perso and user_name else name}**", f"**{n}**")
                if (not title and (r % 5 == 0)) or r == n:
                    await load.edit(content=None, embed=discord.Embed(description=f"{info}\n\n{total}"))

            if dead > 1:
                await ctx.send(f"```diff\n- " + get_str(ctx, "music-plinfo-warnings").format(dead, "{}plrepair.\n```".format(get_server_prefixes(ctx.bot, ctx.guild))))
            elif dead == 1:
                await ctx.send("```diff\n- " + get_str(ctx, "music-plinfo-warning").format("{}plremove\n```".format(get_server_prefixes(ctx.bot, ctx.guild))))
        else:
            await ctx.send(get_str(ctx, "music-plinfo-too-much"))
            youtube_ids = []
            already_find = {}
            for url in settings.autoplaylists[name]['songs']:
                if 'youtu' in url:
                    id = url.split('?v=')[-1].split('?')[0].split('/')[-1]
                    youtube_ids.append(id)
            if youtube_ids:
                already_find = await self.youtube_api.get_youtube_title(id=youtube_ids)

            for r, url in enumerate(settings.autoplaylists[name]['songs'], start=1):
                title = ''
                if 'youtu' in url:
                    id = url.split('?v=')[-1].split('?')[0].split('/')[-1]
                    if id in already_find:
                        title = already_find[id]

                if (not title and (r % 5 == 0)) or r == n:
                    await load.edit(content=f"`{r}/{n}` {load_content}")

                if not title:
                    title = await self.get_title(ctx, query=url)

                if not title:
                    title = "âš  `" + get_str(ctx, "music-plinfo-not-accessible").format(
                        "{}PLREMOVE".format(get_server_prefixes(ctx.bot, ctx.guild))) + "`"
                    dead += 1
                total = "``{}.`` **{}**\n".format(
                    r, f"[{title.replace('[', '').replace(']', '').replace('*', '')[:50]}]({url})")
                banane.append(total)
            to_send = ""
            for ban in banane:
                if not already_send:
                    to_send = get_str(ctx, f"{'music-plinfo-perso-display' if is_perso and user_name else 'music-plinfo-display'}").format(
                        f"**{user_name if is_perso and user_name else name}**", f"**{n}**") + "\n\n"
                    already_send = True
                if len(ban) + len(to_send) > 1950:
                    try:
                        await ctx.author.send(embed=discord.Embed(description=to_send))
                    except discord.HTTPException:
                        return await ctx.send(get_str(ctx, "cant-send-pm"))
                    to_send = ""
                to_send += ban
            if to_send:
                try:
                    await ctx.author.send(embed=discord.Embed(description=to_send))
                except discord.HTTPException:
                    return await ctx.send(get_str(ctx, "cant-send-pm"))
            if dead > 1:
                await ctx.author.send("```diff\n- " + get_str(ctx, "music-plinfo-warnings").format(dead, "{}plrepair.\n```".format(get_server_prefixes(ctx.bot, ctx.guild))))
            elif dead == 1:
                await ctx.author.send("```diff\n- " + get_str(ctx, "music-plinfo-warning").format("{}plremove\n```".format(get_server_prefixes(ctx.bot, ctx.guild))))

        self._cd.get_bucket(ctx.message).reset()

    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.user)
    @pl.command(name='settings', aliases=['set', 'sets', 'setting'])
    async def pl_settings(self, ctx, *, name=None):
        """
            {command_prefix}pl settings [@user]
            {command_prefix}pl settings [autoplaylist_name]
            {command_prefix}pl settings [autoplaylist_name] (--edit private True/False)
            {command_prefix}pl settings [autoplaylist_name] (--edit shuffle True/False)
            {command_prefix}pl settings (autoplaylist_name) (--edit whitelist +/- [user_ID])
            {command_prefix}pl settings (autoplaylist_name) (--edit description (text))
            {command_prefix}pl settings (autoplaylist_name) (--edit name [name])
            {command_prefix}pl settings (autoplaylist_name) (--edit avatar (url))
            {command_prefix}pl settings

        {help}
        """
        await ctx.invoke(self.plsettings, name=name)

    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.user)
    @commands.command(aliases=['plset', 'settingspl', 'setpl'])
    async def plsettings(self, ctx, *, name=None):
        """
            {command_prefix}plsettings (@user)
            {command_prefix}plsettings (autoplaylist_name)
            {command_prefix}plsettings (autoplaylist_name) (--edit private True/False)
            {command_prefix}plsettings (autoplaylist_name) (--edit shuffle True/False)
            {command_prefix}plsettings (autoplaylist_name) (--edit whitelist +/- [user_ID])
            {command_prefix}plsettings (autoplaylist_name) (--edit description (text))
            {command_prefix}plsettings (autoplaylist_name) (--edit name [name])
            {command_prefix}plsettings (autoplaylist_name) (--edit avatar (url))
            {command_prefix}plsettings

        {help}
        """
        settings = await SettingsDB.get_instance().get_glob_settings()
        if not name:
            player = await self.get_player(ctx.guild)
            if not player.is_connected:
                return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)
            if not player.autoplaylist:
                return await ctx.send(get_str(ctx, "music-pl-disabled").format("`{}plstart`".format(get_server_prefixes(ctx.bot, ctx.guild))))
            name = player.autoplaylist['name'].lower()
            try:
                autopl = settings.autoplaylists[name]
            except KeyError:  # can happen after plclear
                return await ctx.send(get_str(ctx, "music-plsettings-got-deleted"))

        name_lower = str(name.lower())

        if '--edit' not in name_lower:
            name = name_lower
            if ctx.message.mentions:
                user = ctx.message.mentions[-1]
                if user.mention not in name:  # It was a prefix
                    user = None
                    if len(ctx.message.mentions) > 1:
                        user = ctx.message.mentions[0]
                if user:
                    name = str(user.id)
            try:
                autopl = settings.autoplaylists[name]
            except KeyError:
                return await ctx.send(get_str(ctx, "music-plinfo-not-found"))

            whitelisted = []
            if len(autopl['whitelist']) > 20:
                whitelisted = f"{len(autopl['whitelist'])} {get_str(ctx, 'cmd-serverinfo-users')}"
            elif len(autopl['whitelist']) == 0:
                whitelisted = get_str(ctx, "music-plsettings-nobody")
            else:
                for m in autopl['whitelist']:
                    user = await self.bot.safe_fetch('user', int(m)) or m
                    whitelisted.append(f"`{user}`")
                whitelisted = "**,** ".join(whitelisted)

            perso = await self.is_perso(ctx.guild, name=name)

            if perso:
                username = perso.name
                title = get_str(
                    ctx, "music-plsettings-autopl").format(username)
            else:
                title = f"Autoplaylist : {autopl['name']}"

            desc = autopl.get('description', False)
            avatar = autopl.get('avatar', False)
            votes = autopl.get('upvote', [])
            embed = discord.Embed()

            if avatar:
                embed.set_thumbnail(url=avatar)
            if perso:
                embed.set_author(name=title, icon_url=perso.avatar_url)
            else:
                embed.title = title

            if desc:
                embed.description = desc

            embed.add_field(name=get_str(
                ctx, "music-plsettings-songs"), value=len(autopl['songs']))
            embed.add_field(name=get_str(ctx, "music-plsettings-created-by"), value=await self.bot.safe_fetch('user', int(autopl['created_by'])) or autopl['created_by_name'])
            embed.add_field(name=get_str(
                ctx, "music-plsettings-creation-date"), value=autopl['created_date'])
            embed.add_field(name="Shuffle", value=get_str(
                ctx, "music-plsettings-{}".format(['no', 'yes'][autopl['shuffle']])))
            embed.add_field(name=get_str(ctx, "music-plsettings-private"), value=get_str(
                ctx, "music-plsettings-{}".format(['no', 'yes'][autopl['private']])))
            embed.add_field(name="Upvote{}".format(
                's' if len(votes) != 1 else ''), value=len(votes))
            embed.add_field(name='Whitelist', value=whitelisted)
            await ctx.send(embed=embed)

        else:  # editing permissions
            opt = name.split('--edit')[1].strip()
            name = name.split('--edit')[0].strip()
            name_lower = name.lower()

            if ctx.message.mentions:
                user = ctx.message.mentions[-1]
                if user.mention not in name:  # It was a prefix
                    user = None
                    if len(ctx.message.mentions) > 1:
                        user = ctx.message.mentions[0]
                if user:
                    name_lower = str(user.id)

            if name_lower not in settings.autoplaylists:
                player = await self.get_player(ctx.guild)
                if player.autoplaylist:
                    name_lower = player.autoplaylist['name'].lower()
                else:
                    return await ctx.send(get_str(ctx, "music-pl-disabled").format("`{}plstart`".format(get_server_prefixes(ctx.bot, ctx.guild))))
                try:
                    autopl = settings.autoplaylists[name_lower]
                except KeyError:  # can happen after plclear
                    return await ctx.send(get_str(ctx, "music-plsettings-got-deleted"))
            else:
                try:
                    autopl = settings.autoplaylists[name_lower]
                except KeyError:
                    return await ctx.send(get_str(ctx, "music-plinfo-not-found"))

            if int(autopl['created_by']) != ctx.author.id and ctx.author.id != owner_id:
                return await ctx.send(get_str(ctx, "music-autoplaylist-only-owner"))

            perso = await self.is_perso(ctx.guild, name=name_lower)
            if perso:
                username = perso.name
                title = get_str(
                    ctx, "music-plsettings-autopl").format(f"**{username}**") + "\n"
            else:
                title = f"Autoplaylist : **{autopl['name']}**\n"

            opt = ' '.join(opt.split())  # delete useless spaces

            if not opt.split(' ')[0]:  # need a lot of info
                return await self.bot.send_cmd_help(ctx)

            try:
                if opt.split(' ')[0][0].lower() == "p":  # private
                    if len(opt.split(' ')) > 1:  # args given
                        if opt.split(' ')[1][0].lower() == "f":
                            autopl['private'] = False
                        else:  # assuming true
                            autopl['private'] = True
                    else:  # invert if no args given
                        autopl['private'] = not autopl['private']
                    await ctx.send(embed=discord.Embed(title=title).add_field(name=get_str(ctx, "music-plsettings-private"),
                                                                              value=get_str(ctx, "music-plsettings-yes") if autopl['private']
                                                                              else get_str(ctx, "music-plsettings-no")))
                    await SettingsDB.get_instance().set_glob_settings(settings)

                elif opt.split(' ')[0][0].lower() == "s":  # shuffle
                    if len(opt.split(' ')) > 1:  # args given
                        if opt.split(' ')[1][0].lower() == "f":
                            autopl['shuffle'] = False
                        else:  # assuming true
                            autopl['shuffle'] = True
                    else:  # invert if no args given
                        autopl['shuffle'] = not autopl['shuffle']
                    await ctx.send(embed=discord.Embed(title=title).add_field(name='Shuffle',
                                                                              value=get_str(ctx, "music-plsettings-yes") if autopl['shuffle']
                                                                              else get_str(ctx, "music-plsettings-no")))
                    await SettingsDB.get_instance().set_glob_settings(settings)

                elif opt.split(' ')[0][0].lower() == "w":  # whitelist
                    if len(opt.split(' ')) < 2:  # need a lot of info
                        return await self.bot.send_cmd_help(ctx)
                    # remove a member from whitelist
                    if opt.split(' ')[1][0].lower() == "-":
                        for user_id in opt.split(' ')[1:]:
                            user_id = ''.join([str(s)
                                               for s in user_id if s.isdigit()])
                            if not user_id.isdigit():
                                continue
                            user = await self.bot.safe_fetch('member', int(user_id), guild=ctx.guild)
                            if user and str(user.id) in autopl['whitelist']:
                                autopl['whitelist'].remove(str(user.id))
                    else:  # admit +
                        for user_id in opt.split(' ')[1:]:
                            user_id = ''.join([str(s)
                                               for s in user_id if s.isdigit()])
                            if not user_id.isdigit():
                                continue

                            user = await self.bot.safe_fetch('member', int(user_id), guild=ctx.guild)
                            if user and str(user.id) not in autopl['whitelist']:
                                autopl['whitelist'].append(str(user.id))

                    whitelisted = []
                    if len(autopl['whitelist']) > 20:
                        whitelisted = f"{len(autopl['whitelist'])} {get_str(ctx, 'cmd-serverinfo-users')}"
                    elif len(autopl['whitelist']) == 0:
                        whitelisted = get_str(ctx, "music-plsettings-nobody")
                    else:
                        for m in autopl['whitelist']:
                            user = await self.bot.safe_fetch('member', int(m), guild=ctx.guild) or m
                            whitelisted.append(f"`{user}`")
                        whitelisted = ", ".join(whitelisted)

                    await ctx.send(embed=discord.Embed(title=title).add_field(name='Whitelist', value=whitelisted))
                    await SettingsDB.get_instance().set_glob_settings(settings)

                elif opt.split(' ')[0][0].lower() == "d":  # description
                    if len(opt.split(' ')) > 1:
                        desc = ' '.join(opt.split(' ')[1:])[:1000]
                        autopl['description'] = desc
                    else:
                        autopl.pop('description', None)
                        desc = get_str(ctx, "now-empty")

                    await ctx.send(embed=discord.Embed(title=title).add_field(name='Description', value=desc))
                    await SettingsDB.get_instance().set_glob_settings(settings)

                elif opt.split(' ')[0][0].lower() == "a":  # custom avatar
                    em = discord.Embed(title=title)
                    if len(opt.split(' ')) > 1:
                        desc = ' '.join(opt.split(' ')[1:])
                        pic = get_image_from_url(desc)
                        if pic:
                            autopl['avatar'] = pic
                            em.add_field(name='Avatar', value=pic)
                            em.set_thumbnail(url=pic)
                        else:
                            return await self.bot.send_cmd_help(ctx)
                    else:
                        autopl.pop('avatar', None)
                        desc = get_str(ctx, "now-empty")
                        em.add_field(name='Avatar', value=desc)
                    await ctx.send(embed=em)
                    await SettingsDB.get_instance().set_glob_settings(settings)

                elif opt.split(' ')[0][0].lower() == "n":  # edit name
                    if len(opt.split(' ')) > 1:
                        name = ' '.join(opt.split(' ')[1:])[:100]
                        if name.lower() == autopl['name'].lower():
                            autopl['name'] = name
                        else:
                            return await ctx.send(get_str(ctx, "cmd-plsettings-modify-name"))

                    await ctx.send(embed=discord.Embed(title=title).add_field(name='Name', value=name))
                    await SettingsDB.get_instance().set_glob_settings(settings)

                else:
                    await self.bot.send_cmd_help(ctx)

            except IndexError:  # well, should not happen but in case I missed something, send help.
                await self.bot.send_cmd_help(ctx)

    @pl.command(name='repair', aliases=["rearm", "dead", "fix"])
    async def pl_repair(self, ctx, *, name=None):
        """
            {command_prefix}pl repair [@user]
            {command_prefix}pl repair [autoplaylist_name]
            {command_prefix}pl repair

        {help}
        """
        await ctx.invoke(self.plrepair, name=name)

    @commands.command(name='plrepair', aliases=["plrearm", "pldead", "plfix"])
    async def plrepair(self, ctx, *, name=None):
        """
            {command_prefix}plrepair [@user]
            {command_prefix}plrepair [autoplaylist_name]
            {command_prefix}plrepair

        {help}
        """
        await self.explosion_check(ctx)

        settings = await SettingsDB.get_instance().get_glob_settings()
        if not name:
            try:
                player = await self.get_player(ctx.guild)
            except NoVoiceChannel:
                self._cd.get_bucket(ctx.message).reset()
                raise NoVoiceChannel(get_str(ctx, "not-connected"))
            if not player.is_connected:
                self._cd.get_bucket(ctx.message).reset()
                return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)
            if not player.autoplaylist:
                self._cd.get_bucket(ctx.message).reset()
                return await ctx.send(get_str(ctx, "music-pl-disabled").format("`{}plstart`".format(get_server_prefixes(ctx.bot, ctx.guild))))
            name = player.autoplaylist['name'].lower()
            try:
                settings.autoplaylists[name]
            except KeyError:  # can happen after plclear
                return await ctx.send(get_str(ctx, "music-plsettings-got-deleted"))

        name = str(name.lower())
        banane = []

        if ctx.message.mentions:
            user = ctx.message.mentions[-1]
            if user.mention not in name:  # It was a prefix
                user = None
                if len(ctx.message.mentions) > 1:
                    user = ctx.message.mentions[0]
            if user:
                name = str(user.id)

        if name not in settings.autoplaylists:
            self._cd.get_bucket(ctx.message).reset()
            return await ctx.send(get_str(ctx, "music-plinfo-not-found"))

        if settings.autoplaylists[name]['private']:
            if int(settings.autoplaylists[name]['created_by']) != ctx.author.id and str(ctx.author.id) not in settings.autoplaylists[name]['whitelist'] and ctx.author.id != owner_id:
                self._cd.get_bucket(ctx.message).reset()
                return await ctx.send(get_str(ctx, "music-autoplaylist-noten-perms"))

        n = len(settings.autoplaylists[name]['songs'])
        if n >= 1000:
            return await ctx.send(f'Your playlist has too many songs ! `{n}/1000` I can\'t display it! Remove some song if you want to use this command.')

        load_content = get_str(ctx, "music-plrepair-loading")
        load = await ctx.send(load_content)

        youtube_ids = []
        already_find = {}
        for url in settings.autoplaylists[name]['songs']:
            if 'youtu' in url:
                id = url.split('?v=')[-1].split('?')[0].split('/')[-1]
                youtube_ids.append(id)
        if youtube_ids:
            already_find = await self.youtube_api.get_youtube_title(id=youtube_ids)

        for r, url in enumerate(settings.autoplaylists[name]['songs'], start=1):
            title = ''
            if 'youtu' in url:
                id = url.split('?v=')[-1].split('?')[0].split('/')[-1]
                if id in already_find:
                    title = already_find[id]

            if (not title and (r % 5 == 0)) or r == n:
                await load.edit(content=f"`{r}/{n}` {load_content}")

            if not title:
                title = await self.get_title(ctx, query=url)

            if not title:
                banane.append(url)

        if not banane:
            self._cd.get_bucket(ctx.message).reset()
            return await ctx.send(get_str(ctx, "music-plrepair-all-ok"))

        for song_url in banane:
            settings.autoplaylists[name]['songs'].remove(song_url)

        await SettingsDB.get_instance().set_glob_settings(settings)

        dead = len(banane)
        if dead > 1:
            await ctx.send(get_str(ctx, "music-plrepair-removed-links").format(f"`{dead}`"))
        elif dead == 1:
            await ctx.send(get_str(ctx, "music-plrepair-removed-link"))

        self._cd.get_bucket(ctx.message).reset()

    @pl.command(name='find', aliases=['list', 'liste'])
    @commands.cooldown(rate=1, per=5.0, type=commands.BucketType.user)
    async def pl_find(self, ctx, query: str = None):
        """
            {command_prefix}pl find (query)
            {command_prefix}pl find (user)

        {help}
        """
        await ctx.invoke(self.plfind, query=query)

    @commands.command(aliases=['pllist', 'plist', 'plliste', 'pliste'])
    @commands.cooldown(rate=1, per=5.0, type=commands.BucketType.user)
    async def plfind(self, ctx, query: str = None, page: int = 1):
        """
            {command_prefix}plfind (query) (page)

        {help}
        """
        settings = await SettingsDB.get_instance().get_glob_settings()
        if query:
            matching = []
            if ctx.message.mentions:
                user = ctx.message.mentions[-1]
                if user.mention not in query:  # It was a prefix
                    user = None
                    if len(ctx.message.mentions) > 1:
                        user = ctx.message.mentions[0]
                if user:
                    query = user.id
            try:
                query = int(query)
                if len(str(query)) < 6:
                    return await ctx.invoke(self.plfind, query=None, page=int(query))
            except ValueError:
                pass
            if not isinstance(query, int):
                for m in settings.autoplaylists.values():
                    desc = m.get('description', '')
                    title = m.get('name', '')
                    if query.lower() in desc.lower() or query.lower() in title.lower():
                        matching.append(m)
                        continue
                    for word in query.split(' '):
                        if word.lower() in [c.lower() for c in title.split(' ')] or word in [cc.lower() for cc in desc.split(' ')]:
                            matching.append(m)
                            break
            else:
                for m in settings.autoplaylists.values():
                    if str(query) == m.get('created_by', ''):
                        matching.append(m)
        else:
            matching = settings.autoplaylists.values()

        if not matching:
            return await ctx.send(get_str(ctx, "no-result"))

        newlist = sorted(matching, key=lambda x: len(
            x.get('upvote', [])), reverse=True)
        embed = discord.Embed(colour=self.get_color(ctx.guild))
        embed.description = "**{}**:\n\n".format(
            get_str(ctx, "music-search-result"))
        bottom = '{} {}{}'.format(len(matching), get_str(
            ctx, "music-search-result", can_owo=False).lower(), 's' if len(matching) != 1 else '')
        embed.set_footer(text=bottom)
        page_val = max(1, page) * 10
        max_val = len(newlist)
        page = min(page_val, max_val)

        for i, m in enumerate(newlist[page - 10:page], start=max(1 + page - 10, 1)):
            id = int(m['created_by'])
            if m['is_personal']:
                perso = await self.is_perso(ctx.guild, name=m['name'])
                if perso:
                    name = perso
                    autoplname = get_str(
                        ctx, "music-plsettings-autopl").format(f'**{name}**')
                else:
                    user = await self.bot.safe_fetch('user', id) or id
                    if user:
                        name = user
                    else:
                        name = m['created_by_name']
                    autoplname = m['name']
            else:
                perso = False
                user = await self.bot.safe_fetch('user', id) or id
                if user:
                    name = user
                else:
                    name = m['created_by_name']
                autoplname = m['name']

            nbvote = len(m.get('upvote', []))
            if perso:
                embed.description += f'`{i}.` ' + get_str(ctx, 'plfind-result-vote{}'.format(
                    's' if nbvote != 1 else '')).format(autoplname, '', nbvote) + '\n'
            else:
                embed.description += f'`{i}.` ' + get_str(ctx, 'plfind-result-vote{}'.format('s' if nbvote != 1 else '')).format(
                    f'**{autoplname}**', get_str(ctx, "plfind-result-middle").format(name), nbvote) + '\n'

        await ctx.send(embed=embed)

    @commands.command(aliases=['plvote', 'votepl', 'upvotepl'])
    @commands.cooldown(rate=1, per=1.0, type=commands.BucketType.user)
    async def plupvote(self, ctx, *, name=None):
        """
            {command_prefix}plupvote [autoplaylist]

        {help}
        """
        settings = await SettingsDB.get_instance().get_glob_settings()
        if not name:
            player = await self.get_player(ctx.guild)
            if not player.is_connected:
                return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)
            if not player.autoplaylist:
                return await ctx.send(get_str(ctx, "music-pl-disabled").format("`{}plstart`".format(get_server_prefixes(ctx.bot, ctx.guild))))
            name = player.autoplaylist['name'].lower()
            try:
                autopl = settings.autoplaylists[name]
            except KeyError:  # can happen after plclear
                return await ctx.send(get_str(ctx, "music-plsettings-got-deleted"))
        else:
            name = str(name.lower())

            if ctx.message.mentions:
                user = ctx.message.mentions[-1]
                if user.mention not in name:  # It was a prefix
                    user = None
                    if len(ctx.message.mentions) > 1:
                        user = ctx.message.mentions[0]
                if user:
                    name = str(user.id)
            try:
                autopl = settings.autoplaylists[name]
            except KeyError:
                return await ctx.send(get_str(ctx, "music-plinfo-not-found"))

        perso = await self.is_perso(ctx.guild, name=name)

        if perso:
            username = perso.name
            title = get_str(ctx, "music-plsettings-autopl").format(username)
        else:
            title = f"Autoplaylist : {autopl['name']}"

        embed = discord.Embed(title=title, colour=self.get_color(ctx.guild))

        vote_list = autopl.get('upvote', [])
        if ctx.author.id in vote_list:
            vote_list.remove(ctx.author.id)
            embed.description = get_str(ctx, "upvote-removed")
        else:
            vote_list.append(ctx.author.id)
            embed.description = get_str(ctx, "upvote-added")

        autopl['upvote'] = vote_list

        await SettingsDB.get_instance().set_glob_settings(settings)
        await ctx.send(embed=embed)

    @pl.command(name='upvote', aliases=['vote'])
    @commands.cooldown(rate=1, per=1.0, type=commands.BucketType.user)
    async def pl_upvote(self, ctx, *, file_name=None):
        """
            {command_prefix}pl upvote [autoplaylist]

        {help}
        """
        await ctx.invoke(self.plupvote, name=file_name)

    @pl.command(name='add', aliases=['+', 'a'])
    async def pl_add(self, ctx, *, song_url=None):
        """
            {command_prefix}pl add [url]
            {command_prefix}pl add [key_words]
            {command_prefix}pl add current_queue
            {command_prefix}pl add

        {help}
        """
        await ctx.invoke(self.pladd, song_url=song_url)

    @commands.command(aliases=['pl+', 'pla'])
    async def pladd(self, ctx, *, song_url=None):
        """
            {command_prefix}pladd [url]
            {command_prefix}pladd [key_words]
            {command_prefix}pladd current_queue
            {command_prefix}pladd

        {help}
        """
        player = await self.get_player(ctx.guild)

        if not ctx.guild.me.voice:
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

        my_vc = ctx.guild.me.voice.channel

        if not await self.is_dj(ctx):
            if ctx.author not in my_vc.members or (ctx.author.voice.self_deaf or ctx.author.voice.deaf):
                return await ctx.send(get_str(ctx, "music-not-my-channel").format(f"**{my_vc}**"), delete_after=30)

        if not player.autoplaylist:
            return await ctx.send(get_str(ctx, "music-pl-disabled").format("`{}plstart`".format(get_server_prefixes(ctx.bot, ctx.guild))))

        settings = await SettingsDB.get_instance().get_glob_settings()

        try:
            settings.autoplaylists[player.autoplaylist['name'].lower()]
        except KeyError:  # can happen after plclear
            return await ctx.send(get_str(ctx, "music-plsettings-got-deleted"))

        file_name = player.autoplaylist['name'].lower()

        if settings.autoplaylists[file_name]['private']:
            if int(settings.autoplaylists[file_name]['created_by']) != ctx.author.id and str(ctx.author.id) not in settings.autoplaylists[file_name]['whitelist'] and ctx.author.id != owner_id:
                return await ctx.send(get_str(ctx, "music-autoplaylist-noten-perms"))

        add_current = False

        # IDK, maybe he wants to add c/cu/cur...
        if song_url and 'current_queue'.startswith(song_url.lower()) and len(song_url) > 3:
            if player.queue:
                add_current = True
                results = {'playlistInfo': {},
                           'loadType': 'PLAYLIST_LOADED', 'tracks': []}
                if player.current:
                    current = {'info': {}}
                    current['info']['title'] = player.current.title
                    current['info']['uri'] = player.current.uri
                    results['tracks'].append(current)
                for track in player.queue:
                    current = {'info': {}}
                    current['info']['title'] = track.title
                    current['info']['uri'] = track.uri
                    results['tracks'].append(current)
                results['playlistInfo'] = {
                    'selectedTrack': -1, 'name': 'Current Queue'}
            else:
                return await load.edit(content=get_str(ctx, "music-plinfo-empty-auto").format("`{}pladd`".format(get_server_prefixes(ctx.bot, ctx.guild))))

        if not song_url:
            if player.current:
                song_url = player.current.uri
                title = player.current.title
            else:
                return await ctx.send(get_str(ctx, "not-playing"), delete_after=20)

        elif not match_url(song_url) and not add_current:
            if self.is_spotify(song_url):
                try:
                    data = await self.prepare_spotify(ctx, song_url, node=player.node)
                except SpotifyError as e:
                    return await ctx.send(e)
            else:
                data = await self.prepare_url(query=song_url, node=player.node)
            if not data or not data['tracks']:
                if data['loadType'] == "LOAD_FAILED":
                    await ctx.send(get_str(ctx, "music-load-failed").format("`{}search`".format(get_server_prefixes(ctx.bot, ctx.guild))))
                elif data['loadType'] == "NO_MATCHES":
                    await ctx.send(get_str(ctx, "music-no-result").format("`{}search`".format(get_server_prefixes(ctx.bot, ctx.guild))))
                return
            title = data['tracks'][0]['info']['title']
            song_url = data['tracks'][0]['info']['uri']

        else:
            if self.is_spotify(song_url):
                try:
                    results = await self.prepare_spotify(ctx, song_url, node=player.node)
                except SpotifyError as e:
                    return await ctx.send(e)
            else:
                if not add_current:
                    results = await self.prepare_url(query=song_url, node=player.node)
            if not results or not results['tracks']:
                if results['loadType'] == "LOAD_FAILED":
                    await ctx.send(get_str(ctx, "music-load-failed").format("`{}search`".format(get_server_prefixes(ctx.bot, ctx.guild))))
                elif results['loadType'] == "NO_MATCHES":
                    await ctx.send(get_str(ctx, "music-no-result").format("`{}search`".format(get_server_prefixes(ctx.bot, ctx.guild))))
                return

            if results['playlistInfo']:  # it's a playlist with multiple tracks
                urls = [track['info']['uri'] for track in results['tracks']]
                for url in urls:
                    if url in player.autoplaylist['songs']:
                        urls.remove(url)
                    else:
                        player.autoplaylist['songs'].append(url)
                settings.autoplaylists[player.autoplaylist['name'].lower(
                )] = player.autoplaylist
                await SettingsDB.get_instance().set_glob_settings(settings)
                added = len(urls)
                not_added = len(results['tracks']) - added
                if added and not not_added:
                    content = get_str(
                        ctx, "music-pladd-pl-added").format(added)
                elif added and not_added:
                    content = get_str(
                        ctx, "music-pladd-pls-added").format(added, not_added)
                else:
                    content = get_str(ctx, "music-pladd-all-already")

                if 'failed' in results:
                    content += f" ({get_str(ctx, 'music-spotify-songs-failed').format(results['failed']) if results['failed'] > 1 else get_str(ctx, 'music-spotify-song-failed').format(results['failed'])})"

                return await ctx.send(content)

            else:  # it's just a track
                title = results['tracks'][0]['info']['title']
                start_time = re.findall('[&?](t|start|s)=(\d+)', song_url)
                song_url = results['tracks'][0]['info']['uri'] + \
                    (f'?t={start_time[-1][-1]}' if start_time else '')

        if any(s.split('?t=')[0] == song_url.split('?t=')[0] for s in player.autoplaylist['songs']):
            return await ctx.send(get_str(ctx, "music-pladd-already-present"), delete_after=30)
        else:
            player.autoplaylist['songs'].append(song_url)
            settings.autoplaylists[player.autoplaylist['name'].lower(
            )] = player.autoplaylist
            await SettingsDB.get_instance().set_glob_settings(settings)
            await ctx.send(get_str(ctx, "music-pladd-added").format(f"**{title}**"))

    @pl.command(name='remove', aliases=['-', 'r', 'delete'])
    async def pl_remove(self, ctx, *, song_url=None):
        """
            {command_prefix}plremove [position_in_autoplaylist]
            {command_prefix}plremove [key_words]
            {command_prefix}plremove [url]
            {command_prefix}plremove

        {help}
        """
        await ctx.invoke(self.plremove, song_url=song_url)

    @commands.command(aliases=['pl-', 'plr', 'pldelete'])
    async def plremove(self, ctx, *, song_url=None):
        """
            {command_prefix}plremove [url]
            {command_prefix}plremove [key_words]
            {command_prefix}plremove

        {help}
        """
        player = await self.get_player(ctx.guild)

        if not ctx.guild.me.voice:
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

        my_vc = ctx.guild.me.voice.channel

        if not await self.is_dj(ctx):
            if ctx.author not in my_vc.members or (ctx.author.voice.self_deaf or ctx.author.voice.deaf):
                return await ctx.send(get_str(ctx, "music-not-my-channel").format(f"**{my_vc}**"), delete_after=30)

        if not player.autoplaylist:
            return await ctx.send(get_str(ctx, "music-pl-disabled").format("`{}plstart`".format(get_server_prefixes(ctx.bot, ctx.guild))))

        settings = await SettingsDB.get_instance().get_glob_settings()

        try:
            settings.autoplaylists[player.autoplaylist['name'].lower()]
        except KeyError:  # can happen after plclear
            return await ctx.send(get_str(ctx, "music-plsettings-got-deleted"))

        file_name = player.autoplaylist['name'].lower()

        if settings.autoplaylists[file_name]['private']:
            if int(settings.autoplaylists[file_name]['created_by']) != ctx.author.id and str(ctx.author.id) not in settings.autoplaylists[file_name]['whitelist'] and ctx.author.id != owner_id:
                return await ctx.send(get_str(ctx, "music-autoplaylist-noten-perms"))

        if not song_url:
            if player.current:
                song_url = player.current.uri
                title = player.current.title
            else:
                return await ctx.send(get_str(ctx, "not-playing"), delete_after=20)

        elif not match_url(song_url):
            if song_url.isdigit():
                if int(song_url) <= len(player.autoplaylist['songs']):
                    return await ctx.invoke(self.plremove, song_url=player.autoplaylist['songs'][int(song_url) - 1])
            if self.is_spotify(song_url):
                try:
                    data = await self.prepare_spotify(ctx, song_url, node=player.node)
                except SpotifyError as e:
                    return await ctx.send(e)
            else:
                data = await self.prepare_url(query=song_url, node=player.node)
            if not data or not data['tracks']:
                if data['loadType'] == "LOAD_FAILED":
                    await ctx.send(get_str(ctx, "music-load-failed").format("`{}search`".format(get_server_prefixes(ctx.bot, ctx.guild))))
                elif data['loadType'] == "NO_MATCHES":
                    await ctx.send(get_str(ctx, "music-no-result").format("`{}search`".format(get_server_prefixes(ctx.bot, ctx.guild))))
                return
            title = data['tracks'][0]['info']['title']
            song_url = data['tracks'][0]['info']['uri']

        else:
            if self.is_spotify(song_url):
                try:
                    results = await self.prepare_spotify(ctx, song_url, node=player.node)
                except SpotifyError as e:
                    return await ctx.send(e)
            else:
                results = await self.prepare_url(query=song_url, node=player.node)
            if not results or not results['tracks']:
                if results['loadType'] == "LOAD_FAILED":
                    await ctx.send(get_str(ctx, "music-load-failed").format("`{}search`".format(get_server_prefixes(ctx.bot, ctx.guild))))
                elif results['loadType'] == "NO_MATCHES":
                    await ctx.send(get_str(ctx, "music-no-result").format("`{}search`".format(get_server_prefixes(ctx.bot, ctx.guild))))
                return

            if results['playlistInfo']:  # it's a playlist with multiple tracks
                urls = [track['info']['uri'] for track in results['tracks']]
                for url in urls:
                    if url not in player.autoplaylist['songs']:
                        urls.remove(url)
                    else:
                        player.autoplaylist['songs'].remove(url)
                settings.autoplaylists[player.autoplaylist['name'].lower(
                )] = player.autoplaylist
                await SettingsDB.get_instance().set_glob_settings(settings)
                removed = len(urls)
                not_removed = len(results['tracks']) - removed
                if removed and not not_removed:
                    content = get_str(
                        ctx, "music-plremove-pl-removed").format(removed)
                elif removed and not_removed:
                    content = get_str(
                        ctx, "music-plremove-pls-removed").format(removed, not_removed)
                else:
                    content = get_str(ctx, "music-plremove-all-already")

                if 'failed' in results:
                    content += f" ({get_str(ctx, 'music-spotify-songs-failed').format(results['failed']) if results['failed'] > 1 else get_str(ctx, 'music-spotify-song-failed').format(results['failed'])})"

                return await ctx.send(content)

            else:  # it's just a track
                title = results['tracks'][0]['info']['title']
                song_url = results['tracks'][0]['info']['uri']
                occ = [s for s in player.autoplaylist['songs']
                       if s.split('?t=')[0] == song_url.split('?t=')[0]]
                if occ:
                    song_url = occ[0]

        if song_url not in player.autoplaylist['songs']:
            return await ctx.send(get_str(ctx, "music-plremove-not-found"), delete_after=30)
        else:
            player.autoplaylist['songs'].remove(song_url)
            settings.autoplaylists[player.autoplaylist['name'].lower(
            )] = player.autoplaylist
            await SettingsDB.get_instance().set_glob_settings(settings)
            await ctx.send(get_str(ctx, "music-plremove-removed").format(f"**{title}**"))

    @commands.command(aliases=['nextplay', 'playtop', 'plnext', 'playafter', 'pnext', 'after', 'topplay', 'playt'])
    async def playnext(self, ctx, *, query: str):
        """
            {command_prefix}playnext [url]
            {command_prefix}playnext [key_words]

        {help}
        """
        await ctx.trigger_typing()
        song = await ctx.invoke(self.playnow, query=query, next=True)
        if isinstance(song, lavalink.AudioTrack):
            await ctx.send(get_str(ctx, "music-promote-promoted").format(f"**{song.title}**"))

    @commands.command(aliases=['pnow', 'instaplay', 'pn', 'playn', 'streamnow', 'singnow'])
    async def playnow(self, ctx, *, query: str, next=False):
        """
            {command_prefix}playnow [url]
            {command_prefix}playnow [key_words]

        {help}
        """
        if not ctx.me.voice or ctx.guild.id not in self.bot.lavalink.players.players:
            try:
                player = await ctx.invoke(self.voice_connect)
            except NoVoiceChannel:
                ctx.command.reset_cooldown(ctx)
                return await ctx.send(get_str(ctx, "music-join-no-channel"))
            except lavalink.NodeException:
                return await ctx.send(get_str(ctx, "music-nodes-unavailable"))
            if not player:
                return
        else:
            player = await self.get_player(ctx.guild)

        if not ctx.guild.me.voice:
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

        my_vc = ctx.guild.me.voice.channel

        if not await self.is_dj(ctx):
            if ctx.author not in my_vc.members or (ctx.author.voice.self_deaf or ctx.author.voice.deaf):
                return await ctx.send(get_str(ctx, "music-not-my-channel").format(f"**{my_vc}**"), delete_after=30)

        if (not player.queue and not player.is_playing):
            # why playnow if queue is empty...
            return await ctx.invoke(self.play_song, query=query)

        if not await self.is_dj(ctx):
            raise commands.errors.CheckFailure

        typing = True

        channel = ctx.guild.get_channel(player.channel)
        if channel:
            async for entry in channel.history(limit=5):
                if not entry or not player.npmsg:  # idk
                    continue
                if entry.id == player.npmsg.id:
                    typing = False
                    break
                if entry.content and len(entry.content) > 500:  # if msg too long
                    break
                elif entry.attachments or entry.embeds:  # if there are embeds or attchments
                    break

            if typing:
                await ctx.trigger_typing()
        else:
            try:
                await ctx.message.add_reaction("☑")
            except discord.Forbidden:
                await ctx.send(get_str(ctx, "music-join-success").format(f"**{channel}**"), delete_after=15)

        if self.is_spotify(query):
            matchs = ['/album/', '/playlist/', ':album:', ':playlist:']
            # hacky way to prevent playlist to be loaded in playnow
            if any(match in query.lower() for match in matchs):
                return await ctx.send(get_str(ctx, "music-promote-playlist"))
            try:
                results = await self.prepare_spotify(ctx, query)
            except SpotifyError as e:
                return await ctx.send(e)
        else:
            query = query.split('list=')[0]
            results = await self.prepare_url(query=query, node=player.node)

        if not results or not results['tracks']:
            if results['loadType'] == "LOAD_FAILED":
                await ctx.send(get_str(ctx, "music-load-failed").format("`{}search`".format(get_server_prefixes(ctx.bot, ctx.guild))))
            elif results['loadType'] == "NO_MATCHES":
                await ctx.send(get_str(ctx, "music-no-result").format("`{}search`".format(get_server_prefixes(ctx.bot, ctx.guild))))
            return

        if results['playlistInfo']:
            return await ctx.send(get_str(ctx, "music-promote-playlist"))
        else:
            track = results['tracks'][0]
            track = self.prepare_track(track)

        player.add(requester=ctx.author.id, track=track)

        song = player.queue.pop()
        player.queue.insert(0, song)

        if player.is_playing and not next:
            await self.player_play(player, query)

        if next:
            return song or None  # useful for playnext

    @commands.command(name="search", aliases=["searchsuper", "songsearch", "searchsong", "findsong", "supersearch", "research", "find", "sc", "ssearch"])
    async def search(self, ctx, *, leftover_args):
        """
            {command_prefix}search (service) [query] (--full)

        {help}
        """
        if not ctx.me.voice or ctx.guild.id not in self.bot.lavalink.players.players:
            try:
                player = await ctx.invoke(self.voice_connect)
            except NoVoiceChannel:
                ctx.command.reset_cooldown(ctx)
                return await ctx.send(get_str(ctx, "music-join-no-channel"))
            except lavalink.NodeException:
                return await ctx.send(get_str(ctx, "music-nodes-unavailable"))
            if not player:
                return
        else:
            player = await self.get_player(ctx.guild)

        if not ctx.guild.me.voice:
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

        my_vc = ctx.guild.me.voice.channel

        if not await self.is_dj(ctx):
            if ctx.author not in my_vc.members or (ctx.author.voice.self_deaf or ctx.author.voice.deaf):
                return await ctx.send(get_str(ctx, "music-not-my-channel").format(f"**{my_vc}**"), delete_after=30)

        if not player.is_connected:
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

        original_leftover_args = leftover_args

        try:
            leftover_args = shlex.split(leftover_args)
        except ValueError:
            return await ctx.send(get_str(ctx, "music-search-ensure"))

        services = {
            'youtube': 'ytsearch',
            'soundcloud': 'scsearch',
            'yt': 'ytsearch',
            'sc': 'scsearch',
        }

        settings = await SettingsDB.get_instance().get_glob_settings()
        default_source = settings.source
        try:
            service = list(services.keys())[list(
                services.values()).index(default_source)]
        except (IndexError, KeyError):
            service = 'youtube'

        if leftover_args[0] in services and leftover_args[0] != original_leftover_args:
            service = leftover_args.pop(0)

        if leftover_args[0][0] in '\'"':
            lchar = leftover_args[0][0]
            leftover_args[0] = leftover_args[0].lstrip(lchar)
            leftover_args[-1] = leftover_args[-1].rstrip(lchar)

        if '--full' in leftover_args:
            lenght = 300
            leftover_args.remove('--full')
        else:
            lenght = 55
        search_query = '%s:%s' % (services[service], ' '.join(leftover_args))
        search_msg = await ctx.send(get_str(ctx, "music-search-loading"))

        await ctx.trigger_typing()
        try:
            results = await self.bot.lavalink.get_tracks(search_query, node=player.node)
        except asyncio.TimeoutError:
            results = None

        if not results or not results['tracks']:
            return await ctx.send(get_str(ctx, "music-search-didnt-find"), delete_after=30)
        try:
            await search_msg.delete()
        except discord.HTTPException:
            pass

        tracks = results['tracks']

        def check(m):
            if m.author == ctx.author and m.channel == ctx.channel:
                # Valid if the user wants to abot
                if m.content.lower().strip() in ["exit", "cancel", "c", "e"]:
                    return True
                if m.content.lower().startswith(get_server_prefixes(ctx.bot, ctx.guild)) or m.content.startswith(m.guild.me.mention):
                    return True
                try:
                    ind = int(m.content.strip()) - 1
                except ValueError:
                    return False  # If the sent message is not a number, don't accept it

                # If the index is not in range
                if ind < 0 or ind >= len(tracks):
                    return False

                return True

        results = []
        index = 1

        for e in tracks:
            max_value = len(str(len(tracks)))
            str_index = str(index)
            dur = lavalink.utils.format_time(
                e['info']['length']).lstrip('0').lstrip(':')
            if len(e["info"]['title']) > 40:
                upper = 0
                for m in str(e["info"]['title']):
                    if m.isupper():
                        upper += 1
                if upper > 15:
                    e["info"]['title'] = str(e["info"]['title'])[
                        0] + str(e["info"]['title'])[1:].lower()
            str_index = "".join(
                [' ' for x in range(max_value - len(str_index))]) + str_index
            new = "`{}.` **[{}]({}) [{}]**".format(str_index, e["info"]['title'].replace(
                '[', '').replace(']', '').replace('*', '')[:lenght], e['info']['uri'], dur)
            if len('\n'.join(results)) + len(new) < 1975:
                results.append(new)
                index += 1
        embed = discord.Embed(color=self.get_color(ctx.guild), title=get_str(
            ctx, "music-supersearch-select"), description="\n".join(results))
        result_message = await ctx.send(embed=embed)

        try:
            response_message = await self.bot.wait_for('message', timeout=30, check=check)
        except asyncio.TimeoutError:
            try:
                await result_message.delete()
            except discord.HTTPException:
                pass
            return await ctx.send(get_str(ctx, "music-search-no-answer"), delete_after=30)
        if not response_message:
            try:
                await result_message.delete()
            except discord.HTTPException:
                pass
            return await ctx.send(get_str(ctx, "music-search-no-answer"), delete_after=30)

        # They started a new search query so lets clean up and bugger off
        elif response_message.content.lower().startswith(get_server_prefixes(ctx.bot, ctx.guild)) or response_message.content.startswith(ctx.me.mention):
            try:
                await result_message.delete()
            except discord.HTTPException:
                pass
            return

        if response_message.content.lower().strip() in ["exit", "cancel", "c", "e"]:
            await result_message.delete()
            try:
                await result_message.delete()
            except discord.HTTPException:
                pass
            return await ctx.send(get_str(ctx, "music-search-stopping"), delete_after=30)

        index = int(response_message.content.strip()) - 1

        try:
            await ctx.invoke(self.play_song, query=tracks[index]['info']['uri'])
        except (IndexError, KeyError):
            pass

        return

    @commands.group(aliases=["rad", "radios", "r"], invoke_without_command=True)
    async def radio(self, ctx, radio):
        """
            {command_prefix}radio play [radio_name]
            {command_prefix}radio list

        {help}
        """
        if not ctx.invoked_subcommand:
            if radio in ["monstercat", "mc", "monster", "monster cat", "listen moe", "listen", "moe", "lm", "listen.moe", "relaxbeats", 'kpop', 'jpop', "rb", "beat", "beats", "relax", "relax beat", "relax beats"]:
                return await ctx.invoke(self.radio_play, radio=radio)
            await self.bot.send_cmd_help(ctx)

    @radio.command(name="list", aliases=["all", "view", "l", "display", "stations", "station", "queue"])
    async def radiolist(self, ctx):
        """
            {command_prefix}radio list

        {help}
        """
        try:
            await ctx.send(embed=discord.Embed(title=get_str(ctx, "music-radio-list-title"), description='\n'.join(self.list_radiolist.keys())))
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"), delete_after=20)

    @radio.command(name="play", aliases=["p", "start", "s"])
    async def radio_play(self, ctx, *, radio: str):
        """
            {command_prefix}radio play [radio_name]

        {help}
        """
        if radio.lower() in ["monstercat", "mc", "monster", "monster cat"]:
            entry = self.list_radiolist['Monstercat']
        elif radio.lower() in ["listen moe", "listen", "jpop", "moe", "lm", "listen.moe"]:
            entry = self.list_radiolist['Listen Moe']
        elif "k" in radio.lower():
            entry = self.list_radiolist['Listen Moe K-POP']
        elif radio.lower() in ["relaxbeats", "rb", "beat", "beats", "relax", "relax beat", "relax beats"]:
            entry = self.list_radiolist['RelaxBeats']
        else:
            return await ctx.send(get_str(ctx, "music-radio-invalid-syntax").format("`{}radio list`".format(get_server_prefixes(ctx.bot, ctx.guild))))

        await ctx.invoke(self.play_song, query=entry)

    @commands.command(name='downloads')  # , aliases=['dl', 'downl'])
    async def youtube_download(self, ctx, *, url=None):
        """
            {command_prefix}download [url]
            {command_prefix}download [query]
            {command_prefix}download

        {help}
        """
        if not ctx.message.id == 123 and not ctx.author.id == owner_id:  # hacky way to check if it's from a custom command
            return

        if not url:
            player = await self.get_player(ctx.guild)

            if not player.is_connected:
                await self.bot.send_cmd_help(ctx)
                return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)

            if player.current:
                if "youtube" not in player.current.uri.lower():
                    return await ctx.send(get_str(ctx, "music-download-only"))
                url = player.current.uri
                title = player.current.title
            else:
                await ctx.send(get_str(ctx, "not-playing"), delete_after=30)
                await self.bot.send_cmd_help(ctx)
                return
        else:
            url = await self.get_track_info(ctx, query=url)
            if not url:  # No result, displays the current song download
                return await ctx.invoke(self.youtube_download)
            url = url['uri']
            title = await self.get_title(ctx, query=url)
        url = "https://mpgun.com/youtube-to-mp3.html?yid=" + \
            url.split("?v=")[-1].split("/")[-1]
        embed = discord.Embed(
            title=title, description="[Download]({})".format(url))

        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(get_str(ctx, "need-embed-permission"), delete_after=20)

    @commands.group(aliases=["sd", "djrole", "djroles", "dj", "djs"], invoke_without_command=True)
    async def setdj(self, ctx, *, role):
        """
            {command_prefix}setdj add [role]
            {command_prefix}setdj remove [role]
            {command_prefix}setdj reset
            {command_prefix}setdj now
            {command_prefix}setdj everyone

        {help}
        """
        if not ctx.invoked_subcommand:
            if not ctx.channel.permissions_for(ctx.author).manage_guild and not ctx.author.id == owner_id:
                raise commands.errors.CheckFailure
            return await ctx.invoke(self.setdj_set, name=role)

    @setdj.command(name="now", aliases=["queue", "dj", "djs", "display", "list", "liste", "info"])
    async def setdj_now(self, ctx):
        """
            {command_prefix}setdj now

        {help}
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        if "all" in settings.djs:
            return await ctx.send(get_str(ctx, "music-setdj-everyone"))
        roles = []
        for id in settings.djs:
            role = ctx.guild.get_role(id)
            if role:
                roles.append(role.name)
        if not roles:
            return await ctx.send(get_str(ctx, "music-setdj-no-roles"))
        msg = "`{}`".format("`, `".join(roles))
        await ctx.send(get_str(ctx, "music-setdj-{}".format("are" if len(settings.djs) > 1 else "is")).format(msg))

    @checks.has_permissions(manage_guild=True)
    @setdj.command(name="set", aliases=["add", "+", "are", "config"])
    async def setdj_set(self, ctx, name):
        """
            {command_prefix}setdj set [role]

        {help}
        """
        role = self.bot.get_role(ctx, name)

        if not role:
            return await ctx.send(get_str(ctx, "cmd-joinclan-role-not-found").format(name))

        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        try:
            settings.djs.remove("all")
        except ValueError:
            pass
        if role.id not in settings.djs:
            settings.djs.append(role.id)
        roles = []
        for id in settings.djs:
            role = ctx.guild.get_role(id)
            if role:
                roles.append(role.name)
        await SettingsDB.get_instance().set_guild_settings(settings)
        msg = "`{}`".format("`, `".join(roles))
        await ctx.send(get_str(ctx, "music-setdj-{}-now".format("are" if len(settings.djs) > 1 else "is")).format(msg))

    @checks.has_permissions(manage_guild=True)
    @setdj.command(name="all", aliases=["everyone", "everybody", "full"])
    async def setdj_all(self, ctx):
        """
            {command_prefix}setdj all

        {help}
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        settings.djs = ['all']
        await SettingsDB.get_instance().set_guild_settings(settings)
        await ctx.send(get_str(ctx, "music-setdj-modified"))

    @checks.has_permissions(manage_guild=True)
    @setdj.command(name="remove", aliases=["-"])
    async def setdj_remove(self, ctx, name):
        """
            {command_prefix}setdj remove [role]

        {help}
        """
        role = self.bot.get_role(ctx, name)

        if not role:
            return await ctx.send(get_str(ctx, "cmd-joinclan-role-not-found").format(name))

        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        if role.id in settings.djs:
            settings.djs.remove(role.id)
        roles = []
        for id in settings.djs:
            role = ctx.guild.get_role(id)
            if role:
                roles.append(role.name)
        await SettingsDB.get_instance().set_guild_settings(settings)
        if not roles:
            return await ctx.send(get_str(ctx, "music-setdj-all-removed"))
        msg = "`{}`".format("`, `".join(roles))
        await ctx.send(get_str(ctx, "music-setdj-{}-now".format("are" if len(settings.djs) > 1 else "is")).format(msg))

    @checks.has_permissions(manage_guild=True)
    @setdj.command(name="reset", aliases=["off", "delete", "stop", "rien", "clear", "clean"])
    async def setdj_reset(self, ctx):
        """
            {command_prefix}setdj reset

        {help}
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        settings.djs = []
        await SettingsDB.get_instance().set_guild_settings(settings)
        await ctx.send(get_str(ctx, "music-setdj-all-removed"))

    @commands.group(aliases=["defaultvolume", "defvol", "dv", "defv", "setvol", "setv", "dvolume", "customvol", "customvolume"], invoke_without_command=True)
    async def defvolume(self, ctx, *, leftover_args):
        """
            {command_prefix}defvolume set [number]
            {command_prefix}defvolume reset
            {command_prefix}defvolume now

        {help}
        """
        if not ctx.invoked_subcommand:
            if leftover_args.isdigit():
                return await ctx.invoke(self.defvolume_set, new_volume=int(leftover_args))

            await self.bot.send_cmd_help(ctx)

    @defvolume.command(name="now", aliases=["queue", "display", "list", "liste", "info", "songlist"])
    async def defvolume_list(self, ctx):
        """
            {command_prefix}defvolume now

        {help}
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        await ctx.send(get_str(ctx, "music-defvolume-now").format(f"`{settings.volume}%`"))

    @defvolume.command(name="set", aliases=["add", "are", "config"])
    async def defvolume_set(self, ctx,  *, new_volume: int):
        """
            {command_prefix}defvolume set [number]

        {help}
        """
        if not ctx.channel.permissions_for(ctx.author).manage_guild and not ctx.author.id == owner_id:
            raise commands.errors.CheckFailure

        if new_volume == def_v:
            return await ctx.invoke(self.defvolume_delete)
        if 0 <= new_volume <= 100:
            settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
            settings.volume = new_volume
            await SettingsDB.get_instance().set_guild_settings(settings)
            await ctx.send(get_str(ctx, "music-defvolume-set").format(f"`{new_volume}%`"))
        else:
            await ctx.send(get_str(ctx, "music-volume-unreasonable-volume").format(new_volume), delete_after=20)

    @defvolume.command(name="reset", aliases=["remove", "delete", "stop", "end", "off", "clean", "clear"])
    async def defvolume_delete(self, ctx):
        """
            {command_prefix}defvolume reset

        {help}
        """
        if not ctx.channel.permissions_for(ctx.author).manage_guild and not ctx.author.id == owner_id:
            raise commands.errors.CheckFailure

        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        del settings.volume
        await SettingsDB.get_instance().set_guild_settings(settings)
        await ctx.send(get_str(ctx, "music-defvolume-reset").format(f"`{def_v}%`"))

    @commands.group(aliases=["autodisconnect", "autotime", "autotimer", "leaveafter", "timer", "timerdisconnect", "autoleaveafter", "al", "ad", "customtime"], invoke_without_command=True)
    async def autoleave(self, ctx, *, leftover_args):
        """
            {command_prefix}autoleave set [seconds]
            {command_prefix}autoleave never
            {command_prefix}autoleave reset
            {command_prefix}autoleave now

        {help}
        """
        if not ctx.invoked_subcommand:
            if leftover_args.isdigit():
                return await ctx.invoke(self.autoleave_set, new_time=int(leftover_args))
            await self.bot.send_cmd_help(ctx)

    @autoleave.command(name="now", aliases=["queue", "display", "list", "liste", "info", "songlist"])
    async def autoleave_list(self, ctx):
        """
            {command_prefix}autoleave now

        {help}
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)

        if isinstance(settings.timer, int):
            if settings.timer:
                value = round(settings.timer / 60, 2)
                await ctx.send(get_str(ctx, "music-autoleave-now").format(f"`{settings.timer} {get_str(ctx, 'cmd-nextep-seconds')} ({value} {get_str(ctx, 'cmd-nextep-minutes') if value > 1 else get_str(ctx, 'cmd-nextep-minute')})`"))
            else:
                await ctx.send(get_str(ctx, "music-autoleave-now-never"))
        else:
            await ctx.send(get_str(ctx, "music-autoleave-now").format(f"`{def_time} {get_str(ctx, 'cmd-nextep-seconds')} (3 {get_str(ctx, 'cmd-nextep-minutes')})`"))

    @autoleave.command(name="set", aliases=["add", "are", "config"])
    async def autoleave_set(self, ctx,  *, new_time: int):
        """
            {command_prefix}autoleave set [number]

        {help}
        """
        if not ctx.channel.permissions_for(ctx.author).manage_guild and not ctx.author.id == owner_id:
            raise commands.errors.CheckFailure

        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)

        if new_time == def_time:
            await ctx.invoke(self.autoleave_delete)

        min_val = 0
        max_val = 1800

        if min_val <= new_time <= max_val:
            settings.timer = new_time
            await SettingsDB.get_instance().set_guild_settings(settings)
            if ctx.guild.id in self.bot.lavalink.players.players:
                player = await self.get_player(ctx.guild)
                player.timer_value = new_time
            await ctx.send(get_str(ctx, "music-autoleave-set").format(f"`{settings.timer} {get_str(ctx, 'cmd-nextep-seconds') if new_time > 1 else get_str(ctx, 'cmd-nextep-second')}`"))
        else:
            if (await self.bot.server_is_claimed(ctx.guild.id)):
                return await ctx.send(get_str(ctx, "music-autoleave-unreasonable-patron").format(f"`{max_val}`", "`{}autoleave never`".format(get_server_prefixes(ctx.bot, ctx.guild))), delete_after=20)
            elif await is_patron(self.bot, ctx.author.id):
                e = discord.Embed(description=get_str(
                    ctx, "music-autoleave-need-claim").format(f"`{get_server_prefixes(ctx.bot, ctx.guild)}claim`"))
            else:
                e = discord.Embed(description=get_str(ctx, "music-autoleave-unreasonable").format(
                    f"`{min_val}`", f"`{max_val}`") + "\n\n" + "**[Patreon](https://www.patreon.com/watora)**")
            try:
                await ctx.send(embed=e)
            except discord.Forbidden:
                await ctx.send(get_str(ctx, "music-autoleave-unreasonable").format(f"`{min_val}`", f"`{max_val}`"))

    @autoleave.command(name="reset", aliases=["remove", "delete", "disable", "stop", "end", "off", "clean", "clear"])
    async def autoleave_delete(self, ctx):
        """
            {command_prefix}autoleave reset

        {help}
        """
        if not ctx.channel.permissions_for(ctx.author).manage_guild and not ctx.author.id == owner_id:
            raise commands.errors.CheckFailure

        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)

        del settings.timer
        await SettingsDB.get_instance().set_guild_settings(settings)
        player = None

        if ctx.guild.id in self.bot.lavalink.players.players:
            player = await self.get_player(ctx.guild)
            player.timer_value = def_time

        await ctx.send(get_str(ctx, "music-autoleave-reset").format(f"`{def_time} {get_str(ctx, 'cmd-nextep-seconds')} (3 {get_str(ctx, 'cmd-nextep-minutes')})`"))

    @autoleave.command(name="never", aliases=["jamais", "infinity", "infinite"])
    async def autoleave_never(self, ctx):
        """
            {command_prefix}autoleave never

        {help}
        """
        if not ctx.channel.permissions_for(ctx.author).manage_guild and not ctx.author.id == owner_id:
            raise commands.errors.CheckFailure

        min_val = 0
        max_val = 1800

        if (await self.bot.server_is_claimed(ctx.guild.id)):
            settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
            settings.timer = False
            await SettingsDB.get_instance().set_guild_settings(settings)
            if ctx.guild.id in self.bot.lavalink.players.players:
                player = await self.get_player(ctx.guild)
                player.timer_value = False
            await ctx.send(get_str(ctx, "music-autoleave-set").format(f"`{get_str(ctx, 'music-autoleave-never')}`"))
        else:
            if await is_patron(self.bot, ctx.author.id):
                e = discord.Embed(description=get_str(
                    ctx, "music-autoleave-need-claim").format(f"`{get_server_prefixes(ctx.bot, ctx.guild)}claim`"))
            else:
                e = discord.Embed(description=get_str(ctx, "music-autoleave-unreasonable").format(
                    f"`{min_val}`", f"`{max_val}`") + "\n\n" + "**[Patreon](https://www.patreon.com/watora)**")
            try:
                await ctx.send(embed=e)
            except discord.Forbidden:
                await ctx.send(get_str(ctx, "music-autoleave-unreasonable").format(f"`{min_val}`", f"`{max_val}`"))

    @commands.group(aliases=["autonp", "autonpmsg", "npmsgchannel", "npchannel", "nowplayingmsg", "nowplayingmessage", "anp", "autonowplaying", "autonowplayingmessage", "autonpmessage"], invoke_without_command=True)
    async def npmsg(self, ctx, *, leftover_args):
        """
            {command_prefix}npmsg set [channel]
            {command_prefix}npmsg never
            {command_prefix}npmsg reset
            {command_prefix}npmsg now

        {help}
        """
        if not ctx.invoked_subcommand:
            await ctx.invoke(self.npmsg_set, new_channel=leftover_args)

    @npmsg.command(name="now", aliases=["queue", "display", "list", "liste", "info", "songlist"])
    async def npmsg_list(self, ctx):
        """
            {command_prefix}npmsg now

        {help}
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)

        if settings.channel:
            channel = ctx.guild.get_channel(settings.channel)
            if not channel:
                settings.channel = None
                await SettingsDB.get_instance().set_guild_settings(settings)

                await ctx.send(get_str(ctx, "music-npmsg-now-default"))
            else:
                await ctx.send(get_str(ctx, "music-npmsg-now").format(f"`{channel}`"))
        elif settings.channel is None:
            await ctx.send(get_str(ctx, "music-npmsg-now-default"))
        else:
            await ctx.send(get_str(ctx, "music-npmsg-now-never"))

    @npmsg.command(name="set", aliases=["add", "are", "config"])
    async def npmsg_set(self, ctx,  *, new_channel):
        """
            {command_prefix}npmsg set [channel]

        {help}
        """
        if not ctx.channel.permissions_for(ctx.author).manage_guild and not ctx.author.id == owner_id:
            raise commands.errors.CheckFailure

        try:
            channel = [c for c in ctx.guild.channels if (str(c.id) == new_channel or isinstance(
                new_channel, str) and c.name.lower() == new_channel.lower()) and isinstance(c, discord.TextChannel)][0]
            new_channel = channel.id
        except IndexError:
            return await ctx.send(get_str(ctx, "music-npmsg-not-found").format(f"`{new_channel}`"))

        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        settings.channel = new_channel
        if ctx.guild.id in self.bot.lavalink.players.players:
            player = await self.get_player(ctx.guild)
            player.channel = new_channel

        await SettingsDB.get_instance().set_guild_settings(settings)
        await ctx.send(get_str(ctx, "music-npmsg-set").format(f"`{channel}`"))

    @npmsg.command(name="reset", aliases=["remove", "delete", "enable", "stop", "end", "off", "clean", "clear"])
    async def npmsg_delete(self, ctx):
        """
            {command_prefix}npmsg reset

        {help}
        """
        if not ctx.channel.permissions_for(ctx.author).manage_guild and not ctx.author.id == owner_id:
            raise commands.errors.CheckFailure

        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)

        settings.channel = None
        if ctx.guild.id in self.bot.lavalink.players.players:
            player = await self.get_player(ctx.guild)
            player.channel = ctx.channel.id

        await SettingsDB.get_instance().set_guild_settings(settings)
        await ctx.send(get_str(ctx, "music-npmsg-reset"))

    @npmsg.command(name="never", aliases=["0", "jamais", "disable", "nowhere", "no"])
    async def npmsg_never(self, ctx):
        """
            {command_prefix}npmsg never

        {help}
        """
        if not ctx.channel.permissions_for(ctx.author).manage_guild and not ctx.author.id == owner_id:
            raise commands.errors.CheckFailure

        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        settings.channel = False
        if ctx.guild.id in self.bot.lavalink.players.players:
            player = await self.get_player(ctx.guild)
            player.channel = None

        await SettingsDB.get_instance().set_guild_settings(settings)

        await ctx.send(get_str(ctx, "music-npmsg-set-disabled"))

    @commands.guild_only()
    @commands.cooldown(rate=1, per=1.5, type=commands.BucketType.user)
    @commands.command(aliases=["lazyer", 'manager'])
    async def lazy(self, ctx, *, text=None):
        """
            {command_prefix}lazy

        {help}
        """
        if not ctx.channel.permissions_for(ctx.author).manage_guild and not ctx.author.id == owner_id:
            raise commands.errors.CheckFailure

        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)

        settings.lazy = not settings.lazy
        await SettingsDB.get_instance().set_guild_settings(settings)
        await ctx.send(get_str(ctx, "cmd-lazy-status") + ' ' + get_str(ctx, "cmd-lazy-{}".format(['disabled', 'enabled'][settings.lazy])))

    @commands.group(aliases=["defaultvote", "threshold", "thresholdvote", "votethreshold", "defvot", "dvote", "setvote", "customvote"], invoke_without_command=True)
    async def defvote(self, ctx, *, leftover_args):
        """
            {command_prefix}defvote set [number]
            {command_prefix}defvote reset
            {command_prefix}defvote now

        {help}
        """
        if not ctx.invoked_subcommand:
            if leftover_args.isdigit():
                return await ctx.invoke(self.defvote_set, new_volume=int(leftover_args))

            await self.bot.send_cmd_help(ctx)

    @defvote.command(name="now", aliases=["queue", "display", "list", "liste", "info", "songlist"])
    async def defvote_list(self, ctx):
        """
            {command_prefix}defvote now

        {help}
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        await ctx.send(get_str(ctx, "music-defvote-now").format(f"`{settings.vote}%`"))

    @defvote.command(name="set", aliases=["add", "are", "config"])
    async def defvote_set(self, ctx,  *, new_volume: int):
        """
            {command_prefix}defvote set [number]

        {help}
        """
        if not ctx.channel.permissions_for(ctx.author).manage_guild and not ctx.author.id == owner_id:
            raise commands.errors.CheckFailure

        if new_volume == def_vote:
            return await ctx.invoke(self.defvote_delete)
        if 1 <= new_volume <= 100:
            settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
            settings.vote = new_volume
            await SettingsDB.get_instance().set_guild_settings(settings)
            await ctx.send(get_str(ctx, "music-defvote-set").format(f"`{new_volume}%`"))
        else:
            await ctx.send(get_str(ctx, "music-volume-unreasonable-volume").format(new_volume), delete_after=20)

    @defvote.command(name="reset", aliases=["remove", "delete", "stop", "end", "off", "clean", "clear"])
    async def defvote_delete(self, ctx):
        """
            {command_prefix}defvote reset

        {help}
        """
        if not ctx.channel.permissions_for(ctx.author).manage_guild and not ctx.author.id == owner_id:
            raise commands.errors.CheckFailure

        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        del settings.vote
        await SettingsDB.get_instance().set_guild_settings(settings)
        await ctx.send(get_str(ctx, "music-defvote-reset").format(f"`{def_vote}%`"))

    @commands.group(aliases=["autoco", "ac", "autosong", "autosongs", "autojoin", "autoconnects", "songauto", "songsauto", "as"], invoke_without_command=True)
    async def autoconnect(self, ctx, channel: discord.VoiceChannel, *, query: str = None):
        """
            {command_prefix}autoconnect add [VoiceChannel] [query|url|radio|autoplaylist]
            {command_prefix}autoconnect remove [VoiceChannel]
            {command_prefix}autoconnect list
            {command_prefix}autoconnect reset

        {help}
        """
        if not ctx.invoked_subcommand:
            if not ctx.channel.permissions_for(ctx.author).manage_guild and not ctx.author.id == owner_id:
                raise commands.errors.CheckFailure
            return await ctx.invoke(self.autoconnect_set, channel=channel, query=query)

    @checks.has_permissions(manage_guild=True)
    @autoconnect.command(name="set", aliases=["add", "are", "config"])
    async def autoconnect_set(self, ctx, channel: discord.VoiceChannel, *, query: str = None):
        """
            {command_prefix}autoconnect add [VoiceChannel]
            {command_prefix}autoconnect add [VoiceChannel] [query|url]
            {command_prefix}autoconnect add [VoiceChannel] autoplaylist:[autoplaylist_name]
            {command_prefix}autoconnect add [VoiceChannel] radio:[RadioName]
            {command_prefix}autoconnect add [VoiceChannel] radio:[RadioName] | autoplaylist:[autoplaylist_name] | ...

        {help}
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        if query:
            parts = query.split('|')
            for part in query.split('|'):
                if not part.strip():
                    parts.remove(part)
                elif 'radio:' in part:
                    if part.replace('radio:', '').strip() not in self.list_radiolist:
                        return await ctx.send(get_str(ctx, "music-radio-invalid-syntax").format("`{}radio list`".format(get_server_prefixes(ctx.bot, ctx.guild))))
                elif 'autoplaylist:' in part:
                    glob_settings = await SettingsDB.get_instance().get_glob_settings()
                    file_name = part.replace('autoplaylist:', '').strip()
                    if str(file_name.lower()) not in glob_settings.autoplaylists:
                        file_name = format_mentions(file_name)
                        return await ctx.send(get_str(ctx, "music-plstart-doesnt-exists").format(f"**{file_name}**", "`{}plnew`".format(get_server_prefixes(ctx.bot, ctx.guild))), delete_after=30)
            query = '|'.join(parts)

        settings.autosongs[str(channel.id)] = query

        if ctx.guild.id not in self.bot.autosongs_map:
            self.bot.autosongs_map[ctx.guild.id] = {}
        self.bot.autosongs_map[ctx.guild.id][str(channel.id)] = query
        await SettingsDB.get_instance().set_guild_settings(settings)
        await ctx.send(":ballot_box_with_check:")

    @checks.has_permissions(manage_guild=True)
    @autoconnect.command(name="remove", aliases=['-', 'd', 'r', 'delete'])
    async def autoconnect_remove(self, ctx, *, channel: discord.VoiceChannel):
        """
            {command_prefix}autoconnect remove [VoiceChannel]

        {help}
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)

        if ctx.guild.id in self.bot.autosongs_map:
            self.bot.autosongs_map[ctx.guild.id].pop(str(channel.id), None)
            settings.autosongs.pop(str(channel.id), None)
            await SettingsDB.get_instance().set_guild_settings(settings)
            await ctx.send(":ballot_box_with_check:")

    @autoconnect.command(name="now", aliases=["queue", "display", "list", "liste", "info", "songlist"])
    async def autoconnect_list(self, ctx):
        """
            {command_prefix}autoconnect list

        {help}
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        desc = ''
        for m, k in enumerate(settings.autosongs.items(), start=1):
            modified = (f' : **[{k[1]}]({k[1][:40]})**' if match_url(k[1])
                        else f' : `{k[1]}`') if k[1] else ''
            desc += '`{}.` **{}**{}\n'.format(m,
                                              ctx.guild.get_channel(int(k[0])), modified)
        if desc:
            embed = discord.Embed(description=desc[:1900])
            embed.set_author(name='Autoconnect list',
                             icon_url=ctx.guild.icon_url)
            await ctx.send(embed=embed)
        else:
            await ctx.send(get_str(ctx, "music-autoconnect-list-empty").format("`{}autoconnect add`".format(get_server_prefixes(ctx.bot, ctx.guild))))

    @checks.has_permissions(manage_guild=True)
    @autoconnect.command(name="reset", aliases=["off", "stop", "rien", "clear", "clean"])
    async def autoconnect_reset(self, ctx):
        """
            {command_prefix}autoconnect reset

        {help}
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        settings.autosongs = {}
        self.bot.autosongs_map.pop(ctx.guild.id, None)
        await SettingsDB.get_instance().set_guild_settings(settings)
        await ctx.send(":ballot_box_with_check:")

    @commands.group(aliases=["confighost", "ch", "hc", "hg", "gh"], invoke_without_command=True)
    async def hostconfig(self, ctx, ip: str, password: str = "youshallnotpass", port: int = 2333):
        """
            {command_prefix}hostconfig set [ip]
            {command_prefix}hostconfig set [ip] [password]
            {command_prefix}hostconfig set [ip] [password] [port]
            {command_prefix}hostconfig remove
            {command_prefix}hostconfig now
            {command_prefix}hostconfig switch
            {command_prefix}hostconfig link

            Allows to manage your credentials for your node to host yourself your music.
            Please read the documentation [**here**](https://docs.watora.xyz/features/self-hosting).
        """
        if not ctx.invoked_subcommand:  # TODO: Move all those commands to another node
            return await ctx.invoke(self.hostconfig_set, ip=ip, password=password, port=port)

    @hostconfig.command(name="set", aliases=["+", "add"])
    @commands.cooldown(rate=1, per=15, type=commands.BucketType.user)
    async def hostconfig_set(self, ctx, ip: str, password: str = "youshallnotpass", port: int = 2333):
        """
            {command_prefix}hostconfig set [ip]
            {command_prefix}hostconfig set [ip] [password]
            {command_prefix}hostconfig set [ip] [password] [port]

        Allows to set your node credentials.
        Default password is youshallnotpass (more than recommended to change it).
        Default port is 2333.
        """
        if ctx.guild and ip:
            try:
                await ctx.message.delete()
                # TODO: Translations
                await ctx.send('Please use this command in DMs for your privacy!')
            except discord.HTTPException:
                pass

        # TODO: Translations
        msg = await ctx.send('Connecting...')

        if not await self.ensure_node_connection(ip, port, password):
            return await msg.edit(content='Failed to connect to this server, please ensure that your credentials are correct! Also make sure that your server is running, and your firewall is not blocking the connection. You can also check if your port is opened correctly. For futher assistance, you can join Watora\'s discord.')  # TODO: Translations

        # TODO: Translations
        await msg.edit(content="Successfully connected to the server!")

        settings = await SettingsDB.get_instance().get_glob_settings()
        settings.custom_hosts[str(ctx.author.id)] = {
            'host': ip,
            'port': port,
            'password': password
        }
        await SettingsDB.get_instance().set_glob_settings(settings)

        resume_config = {
            'resume_key': str(ctx.author.id) + str(sum(self.bot.shards.keys())),
            'resume_timeout': 600
        }

        node = self.bot.lavalink.node_manager.get_node_by_name(
            str(ctx.author.id), True)
        if node:
            await self.bot.lavalink.node_manager.destroy_node(node)

        self.bot.lavalink.add_node(
            region=None, host=ip, password=password, name=f'{ctx.author.id}', port=port, is_perso=True, **resume_config)

    @hostconfig.command(name="delete", aliases=["remove", "-", "off", "stop", "leave"])
    @commands.cooldown(rate=1, per=3, type=commands.BucketType.guild)
    async def hostconfig_delete(self, ctx):
        """
            {command_prefix}hostconfig delete

        Removes your node configuration.
        """
        settings = await SettingsDB.get_instance().get_glob_settings()
        if str(ctx.author.id) in settings.custom_hosts.keys():
            del settings.custom_hosts[str(ctx.author.id)]
        await SettingsDB.get_instance().set_glob_settings(settings)
        node = self.bot.lavalink.node_manager.get_node_by_name(
            str(ctx.author.id), True)
        if node:
            await self.bot.lavalink.node_manager.destroy_node(node)
        await ctx.send("☑️")

    @hostconfig.command(name="now", aliases=["current", "atm"])
    async def hostconfig_now(self, ctx):
        """
            {command_prefix}hostconfig now

        Shows your node configuration.
        """
        settings = await SettingsDB.get_instance().get_glob_settings()
        if str(ctx.author.id) not in settings.custom_hosts.keys():
            # TODO: Translations
            return await ctx.send('No config currently registered! Use `{}hostconfig set` to set one.'.format(get_server_prefixes(self.bot, ctx.guild)))
        info = settings.custom_hosts[str(ctx.author.id)]
        # TODO: Translations
        embed = discord.Embed(description="Your server configuration")
        embed.add_field(name='IP', value=info['host'], inline=False)
        embed.add_field(name='Password', value=info['password'], inline=False)
        embed.add_field(name='Port', value=info['port'], inline=False)
        node = self.bot.lavalink.node_manager.get_node_by_name(
            str(ctx.author.id))
        # TODO: Translations
        text = "Server is currently " + \
            ("connected" if node else "disconnected")
        embed.set_footer(text=text)
        try:
            await ctx.author.send(embed=embed)
        except discord.HTTPException:
            return await ctx.send(get_str(ctx, "cant-send-pm"))
        if ctx.guild:
            await ctx.send(get_str(ctx, "message-send-to-mp"))

    @checks.has_permissions(manage_guild=True)
    @hostconfig.command(name="link", aliases=["connect", "setserver"])
    async def hostconfig_link(self, ctx):
        """
            {command_prefix}hostconfig link

        Links your configuration to this server.
        Your node will be used by default when people of this guild
        are trying to listen to music.
        """
        settings = await SettingsDB.get_instance().get_guild_settings(ctx.guild.id)
        if settings.defaultnode == str(ctx.author.id):
            settings.defaultnode = None
            await SettingsDB.get_instance().set_guild_settings(settings)
            # TODO: Translations
            return await ctx.send("Your node is not linked to this server anymore.")
        settings_glob = await SettingsDB.get_instance().get_glob_settings()
        if str(ctx.author.id) not in settings_glob.custom_hosts.keys():
            # TODO: Translations
            return await ctx.send('No config currently registered!')
        settings.defaultnode = str(ctx.author.id)
        await SettingsDB.get_instance().set_guild_settings(settings)
        # TODO: Translations
        await ctx.send("Your node is now linked to this server.")

    @hostconfig.command(name="switch", aliases=["move", "change"])
    @commands.cooldown(rate=1, per=15, type=commands.BucketType.guild)
    async def hostconfig_switch(self, ctx):
        """
            {command_prefix}hostconfig switch

        Switch current player to your node, or make it leaves your node.
        """
        settings = await SettingsDB.get_instance().get_glob_settings()
        if str(ctx.author.id) not in settings.custom_hosts.keys():
            # TODO: Translations
            return await ctx.send('No config currently registered!')
        info = settings.custom_hosts[str(ctx.author.id)]
        node = self.bot.lavalink.node_manager.get_node_by_name(
            str(ctx.author.id))
        if not node:
            # TODO: Translations
            return await ctx.send("Your node doesn't seem to be connected!")
        if ctx.guild.id not in self.bot.lavalink.players.players:
            return await ctx.send(get_str(ctx, "not-connected"), delete_after=20)
        player = await self.get_player(ctx.guild)
        if not await self.is_dj(ctx) and not player.node == node:
            raise commands.errors.CheckFailure
        is_user = True
        if player.node == node:
            # TODO: Translations
            await ctx.send('This player is already on your node! Moving it to another node...')

            node = self.bot.lavalink.node_manager.find_ideal_node(
                str(ctx.guild.id))
            if await self.bot.server_is_claimed(ctx.guild.id, settings):
                node = self.bot.lavalink.node_manager.get_node_by_name(
                    str("Premium")) or node
            is_user = False
            if not node:
                # TODO: Translations
                return await ctx.send('No other node available!')
        else:
            await ctx.send('Moving...')  # TODO: Translations
        await player.change_node(node)
        await self.reload_np_msg(player)
        if is_user:
            # TODO: Translations
            return await ctx.send(f'Moved to {ctx.author} node.')
        return await ctx.send(f'Left {ctx.author} node.')  # TODO: Translations

    @commands.is_owner()
    @commands.command()
    async def togglesource(self, ctx, *, source: str):
        """
            {command_prefix}togglesource

        Toggle default video source.
        """
        settings = await SettingsDB.get_instance().get_glob_settings()
        settings.source = source
        await SettingsDB.get_instance().set_glob_settings(settings)

        await ctx.send(f"Source toggled to `{source}`")

    @commands.is_owner()
    @commands.command()
    async def musiceval(self, ctx, *, stmt: str):
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
        self.temp = result
        await ctx.channel.send("```py\n--- In ---\n{}\n--- Out ---\n{}\n```".format(stmt, result))

    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        if before.region != after.region:
            log.debug("[Guild] \"%s\" changed regions: %s -> %s" %
                      (after.name, before.region, after.region))

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        if hasattr(self.bot, 'lavalink') and guild.id in self.bot.lavalink.players.players:
            log.debug(
                f"Removing player in removed guild ({guild.id}: {guild.name})")
            player = await self.get_player(guild)
            await self.disconnect_player(player)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        guild = channel.guild
        if hasattr(self.bot, 'lavalink') and guild.id in self.bot.lavalink.players.players:
            if isinstance(channel, discord.VoiceChannel):
                if guild.me in channel.members:
                    log.debug(
                        f"Removing player in removed channel ({guild.id}: {guild.name})")
                    player = await self.get_player(guild)
                    await self.disconnect_player(player)

    async def auto_join_play(self, member, after):
        """Joins and plays a song based on settings, and voice updates"""
        if member.bot or (member.voice and member.voice.mute):
            return
        song_info = self.bot.autosongs_map[member.guild.id][str(
            after.channel.id)]
        if not song_info:
            player = await self.get_player(member.guild, True, member.id)
            return await player.connect(after.channel.id)
        song_info = random.choice(song_info.split('|')).strip()
        if 'autoplaylist:' in song_info:
            settings = await SettingsDB.get_instance().get_glob_settings()
            file_name = song_info.replace('autoplaylist:', '').strip()
            if str(file_name.lower()) not in settings.autoplaylists:
                return
            player = await self.get_player(member.guild, True, member.id)
            if not player.is_connected:
                await player.connect(after.channel.id)
                tries = 0
                while not player.is_connected and tries < 5:
                    # Wait till the player connects to discord.. REE..
                    await asyncio.sleep(tries)
                    tries += 0.5
            else:
                if int(player.channel_id) != after.channel.id:
                    await player.connect(after.channel.id)
            player.autoplaylist = settings.autoplaylists[str(
                file_name.lower())]
            player.authorplaylist = member
            player.queue.clear()
            await player.skip()
        else:
            chan_id = after.channel.id
            if 'radio:' in song_info:
                song_info = song_info.replace('radio:', '').strip()
                song_info = self.list_radiolist.get(song_info)
                if not song_info:
                    return

            player = await self.get_player(member.guild, True, member.id)

            results = await self.prepare_url(query=song_info, node=player.node)

            if not results or not results['tracks']:
                return

            await player.connect(chan_id)

            if results['playlistInfo']:
                tracks = results['tracks']
                for track in tracks:
                    player.add(requester=member.id, track=track)
            else:
                track = results['tracks'][0]
                track = self.prepare_track(track)

                player.add(requester=member.id, track=track)

            await self.player_play(player, song_info)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not hasattr(self.bot, 'lavalink'):
            return

        if not all([before, after, member]):
            return

        if (member.guild.id not in self.bot.lavalink.players.players):
            if member.guild.id not in self.bot.autosongs_map:
                return
            if not all([after.channel, member.guild]):
                return
            if str(after.channel.id) not in self.bot.autosongs_map[member.guild.id]:
                return
            if after.channel and (sum(1 for m in after.channel.members if not (m.voice.deaf or m.bot or m.voice.self_deaf or m == m.guild.me))) and not (member.guild.me.voice and member.guild.me.voice.mute):
                await self.auto_join_play(member, after)

        try:
            player = self.bot.lavalink.players.players[member.guild.id]
        except KeyError:
            return

        if member == member.guild.me and not after.channel:
            log.warning(
                f"[Player] Just left voice for some reason. Disconnecting from {member.guild.id}/{member.guild.name}.")
            await self.disconnect_player(player)
            return

        if not player.connected_channel or not player.channel_id:
            return

        if member.guild.id in self.bot.autosongs_map:
            if after.channel:
                if str(after.channel.id) in self.bot.autosongs_map[member.guild.id]:
                    if member != member.guild.me and member.guild.me.voice:
                        if before.channel != after.channel:
                            if not (sum(1 for m in member.guild.me.voice.channel.members if not (m.voice.deaf or m.bot or m.voice.self_deaf or m == m.guild.me))):
                                if after.channel and (sum(1 for m in after.channel.members if not (m.voice.deaf or m.bot or m.voice.self_deaf or m == m.guild.me))) and not (member.guild.me.voice and member.guild.me.voice.mute):
                                    await self.auto_join_play(member, after)

        # We don't care, right ?
        if player.connected_channel not in [after.channel, before.channel]:
            return

        my_voice_channel = player.connected_channel

        guild = self.bot.get_guild(int(player.guild_id))  # member.guild ?

        if (sum(1 for m in my_voice_channel.members if not (m.voice.deaf or m.bot or m.voice.self_deaf or m == guild.me))) and not (guild.me.voice and guild.me.voice.mute):
            if player.auto_paused:
                player.auto_paused = False
                if player.paused:
                    await player.set_pause(False)
                    log.debug(
                        "[Voice] The player is now resumed on {}".format(guild.name))
                if guild.id in self.timeout_tasks:
                    self.timeout_tasks[guild.id].cancel()
                    self.timeout_tasks.pop(guild.id)
        else:
            if not player.auto_paused:
                player.auto_paused = True
                if not player.paused and player.is_playing:
                    await player.set_pause(True)
                    log.debug(
                        "[Voice] The player is now paused on {}".format(guild.name))
                if player.timer_value is not False:
                    task = asyncio.ensure_future(self.timeout_task(
                        player, additional_time=10 if guild.me.voice and guild.me.voice.mute else 0))  # don't instant leave for ever the vc
                    self.timeout_tasks[guild.id] = task

    async def timeout_task(self, player, additional_time):
        guild = self.bot.get_guild(int(player.guild_id))
        # if timer_value is at 0, don't instant leave the voice channel for ever if muted otherwise users can't unmute her
        await asyncio.sleep(min(1800, max(max(player.timer_value + additional_time, 0), 0)))
        if player in dict(self.bot.lavalink.players).values():  # prevent from stupid issues
            # if not sum(1 for m in player.connected_channel.members if not (m.voice.deaf or m.bot or m.voice.self_deaf or m == guild.me)):  # the last one is only useful for self bots
            log.debug(
                f"[Timer] I'm alone since about {player.timer_value} secs on {guild.id}/{guild.name}.")
            await self.disconnect_message(player, guild)
            await self.disconnect_player(player)

        self.timeout_tasks.pop(guild.id, None)

    async def inact_task(self, player):
        guild = self.bot.get_guild(int(player.guild_id))
        await asyncio.sleep(player.timer_value)
        if player in dict(self.bot.lavalink.players).values():  # prevent from stupid issues
            # if not player.is_playing and not player.queue:
            log.debug(
                f"[Timer] I'm inactive since about {player.timer_value} secs on {guild.id}/{guild.name}.")
            await self.disconnect_message(player, guild)
            await self.disconnect_player(player)

        self.inact_tasks.pop(guild.id, None)

    async def disconnect_message(self, player, guild, channel=None, inactivity=True):
        if not channel:
            channel = guild.get_channel(player.channel)
        if not channel:
            return
        color = self.get_color(guild)
        if inactivity:
            title = get_str(guild, "disconnecting-inactivity", bot=self.bot)
        else:
            title = get_str(guild, "music-stop-success", bot=self.bot)

        embed = discord.Embed(colour=color, title=title)
        requester = (player.current.requester if player.current else None) or (
            player.previous.requester if player.previous else None)
        if not requester or not await is_basicpatron(self.bot, requester):
            embed.description = "**[{}](https://www.patreon.com/watora)** {}\n{}".format(get_str(guild, "support-watora", bot=self.bot, can_owo=False),
                                                                                         get_str(guild, "support-watora-end", bot=self.bot), get_str(guild, "suggest-features", bot=self.bot).format(f"`{get_server_prefixes(self.bot, guild)}suggestion`"))
        else:
            embed.description = "{} {}\n{}".format(get_str(guild, "thanks-support", bot=self.bot, can_owo=False),
                                                   "<:WatoraLove:553618991328002058>", get_str(guild, "manage-autoleave-time", bot=self.bot).format(f"`{get_server_prefixes(self.bot, guild)}autoleave`"))
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            try:
                await channel.send(content=title)
            except discord.Forbidden:
                pass


def setup(bot):
    bot.add_cog(Music(bot))
