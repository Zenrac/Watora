import re
import random
import discord

from collections import Counter, OrderedDict

from utils.db import SettingsDB
from utils.watora import get_server_prefixes, get_str

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
        return self.channel

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