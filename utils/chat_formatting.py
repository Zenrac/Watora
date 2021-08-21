import asyncio
import discord
import math
import shlex

from utils.watora import get_str

ARROW_RIGHT = '▶'
ARROW_LEFT = '◀'
ARROW_TOP = '🔼'
ARROW_BOTTOM = '🔽'
ARROW_TOPTOP = '⏫'
ARROW_BOTBOT = '⏬'
ARROW_LEFTLEFT = '⬅'
ARROW_RIGHTRIGHT = '➡'
STOP = '⏹'
RESET = '⏺'
REPLAY = '🔁'
REPLAY_ONE = '🔂'
PAUSE = '⏸'
SHUFFLE = '🔀'
VOL_UP = '🔊'
VOL_DOWN = '🔉'
TRASH_BIN = '🚮'

COLOR = int("2AA198", 16)

tasks = {}


def box(text, lang=''):
    ret = '```{}\n{}\n```'.format(lang, text)
    return ret


def pagify(text, delims=['\n'], *, escape=True, shorten_by=8,
           page_length=2000):
    """THINGS WHICH DOES NOT RESPECT MARKDOWN BOXES OR INLINE CODE"""
    in_text = text
    if escape:
        num_mentions = text.count('@here') + text.count('@everyone')
        shorten_by += num_mentions
    page_length -= shorten_by
    while len(in_text) > page_length:
        closest_delim = max([in_text.rfind(d, 0, page_length)
                             for d in delims])
        closest_delim = closest_delim if closest_delim != -1 else page_length
        if escape:
            to_send = escape_mass_mentions(in_text[:closest_delim])
        else:
            to_send = in_text[:closest_delim]
        yield to_send
        in_text = in_text[closest_delim:]

    if escape:
        yield escape_mass_mentions(in_text)
    else:
        yield in_text


def escape(text, *, mass_mentions=False, formatting=False):
    if mass_mentions:
        text = text.replace('@everyone', '@\u200beveryone')
        text = text.replace('@here', '@\u200bhere')
    if formatting:
        text = (text.replace('`', '\\`')
                    .replace('*', '\\*')
                    .replace('_', '\\_')
                    .replace('~', '\\~'))
    return text


def escape_mass_mentions(text):
    return escape(text, mass_mentions=True)


def split_str_lines(string, split_at=2000):
    items = []
    lines = string.split(' ')
    new = ''
    for line in lines:
        if (len(new) + len(line)) > split_at:
            items.append(new)
            new = ''
        new += ' ' + line
    if new:
        items.append(new)

    return items


def shlex_ignore_single_quote(value):
    lex = shlex.shlex(value)
    lex.quotes = '"'
    lex.whitespace_split = True
    lex.commenters = ''
    return list(lex)


class Paginator:
    REACTIONS = (ARROW_LEFT, STOP, ARROW_RIGHT, TRASH_BIN)

    def __init__(self, **kwargs):
        self.ctx = kwargs.pop('ctx')
        self.items = kwargs.pop('items')
        self.data = kwargs.pop('data')
        self.items_per_page = kwargs.pop('items_per_page', 10)
        self.color = COLOR
        self.timeout = kwargs.pop('timeout', 180.0)
        self.page = kwargs.pop('page', 0)
        self.bot = self.ctx.bot
        self.msg = None

    @property
    def embed(self):
        lower_bound = self.page * self.items_per_page
        upper_bound = lower_bound + self.items_per_page
        to_display = self.items[lower_bound:upper_bound]
        desc = ""
        for content in to_display:
            desc += content
        embed = discord.Embed(color=self.color, description=desc)
        embed.set_author(
            name=f"{self.data['primary_artist']['name']} - {self.data['title']}", url=self.data["url"])
        embed.set_thumbnail(url=self.data["header_image_url"])
        if self.pages_needed > 1:
            embed.set_footer(text=f"{self.page+1}/{self.pages_needed}")
        return embed

    @property
    def reactions(self):
        return (ARROW_LEFT, STOP, ARROW_RIGHT, TRASH_BIN)

    @property
    def pages_needed(self):
        return math.ceil(len(self.items) / self.items_per_page)

    def check(self, reaction, user):
        return reaction.message.id == self.msg.id and user.id == self.ctx.author.id

    async def send_to_channel(self):
        while True:
            try:
                if self.msg:
                    await self.msg.edit(embed=self.embed)
                    if self.pages_needed < 2:
                        await self.msg.clear_reactions()
                        break
                else:
                    self.msg = await self.ctx.send(embed=self.embed)
                    if self.pages_needed < 2:
                        break
                    for r in self.reactions:
                        await self.msg.add_reaction(r)

                try:
                    reaction, user = await self.bot.wait_for('reaction_add', check=self.check, timeout=self.timeout)
                except asyncio.TimeoutError:
                    await self.msg.clear_reactions()
                    break

                if reaction.emoji == ARROW_LEFT:
                    self.page -= 1
                    self.page %= self.pages_needed
                elif reaction.emoji == ARROW_RIGHT:
                    self.page += 1
                    self.page %= self.pages_needed
                elif reaction.emoji == STOP:
                    try:
                        await self.msg.clear_reactions()
                    except discord.HTTPException:
                        pass
                    break
                elif reaction.emoji == TRASH_BIN:
                    await self.msg.delete()
                    break

                await self.msg.remove_reaction(reaction.emoji, user)

            except discord.HTTPException:
                if self.ctx.channel.permissions_for(self.ctx.me).add_reactions:
                    await self.ctx.send(get_str(self.ctx, 'need-manage-messages-permission'))
                elif self.ctx.channel.permissions_for(self.ctx.me).manage_messages:
                    await self.ctx.send(get_str(self.ctx, 'need-add-emojis'))
                else:
                    await self.ctx.send(get_str(self.ctx, 'need-manage-messages-permission') + ' ' + get_str(self.ctx, 'need-add-emojis'))
                break


class Equalizer:
    REACTIONS = (ARROW_LEFT, ARROW_RIGHT, ARROW_TOP, ARROW_TOPTOP,
                 ARROW_BOTTOM, ARROW_BOTTOM, STOP, RESET)

    def __init__(self, ctx, player):
        self.ctx = ctx
        self.color = COLOR
        self.timeout = 30
        self.player = player
        self.bot = self.ctx.bot
        self.msg = None
        self._band_count = 15
        self.bands = player.equalizer
        self.freqs = [r for r in range(15)]
        self.position = None

    @property
    def reactions(self):
        return (ARROW_LEFTLEFT, ARROW_LEFT, ARROW_RIGHT, ARROW_RIGHTRIGHT, ARROW_TOPTOP, ARROW_TOP, ARROW_BOTTOM, ARROW_BOTBOT, RESET, STOP)

    @property
    def embed(self):
        desc = "```yaml\n               EQUALIZER                    ```"
        desc += '```brainfuck\n' + \
            self.visual(self.player.equalizer, self.position) + '```'
        embed = discord.Embed(color=self.color, description=desc)
        return embed

    def check(self, reaction, user):
        return reaction.message.id == self.msg.id and user.id == self.ctx.author.id

    async def send_to_channel(self):
        while True:
            try:
                if self.msg:
                    await self.msg.edit(embed=self.embed)
                else:
                    self.position = 0
                    self.msg = await self.ctx.send(embed=self.embed)
                    for r in self.reactions:
                        await self.msg.add_reaction(r)

                try:
                    reaction, user = await self.bot.wait_for('reaction_add', check=self.check, timeout=self.timeout)
                except asyncio.TimeoutError:
                    await self.msg.clear_reactions()
                    break

                if reaction.emoji == ARROW_LEFT:
                    pos = self.position - 1
                    if pos < 0:
                        pos = self._band_count - 1
                    self.position = pos

                elif reaction.emoji == ARROW_RIGHT:
                    pos = self.position + 1
                    if pos > (self._band_count - 1):
                        pos = 0
                    self.position = pos

                elif reaction.emoji == ARROW_RIGHTRIGHT:
                    self.position = self._band_count - 1

                elif reaction.emoji == ARROW_LEFTLEFT:
                    self.position = 0

                elif reaction.emoji == ARROW_TOP:
                    change = min(
                        (self.player.equalizer[self.position] + 0.25), 1)
                    if change != self.player.equalizer[self.position]:
                        await self.player.set_gain(*(self.position, change))

                elif reaction.emoji == ARROW_BOTTOM:
                    change = max(
                        (self.player.equalizer[self.position] - 0.25), -0.25)
                    if change != self.player.equalizer[self.position]:
                        await self.player.set_gain(*(self.position, change))

                elif reaction.emoji == ARROW_TOPTOP:
                    await self.player.set_gain(*(self.position, 1))

                elif reaction.emoji == ARROW_BOTBOT:
                    await self.player.set_gain(*(self.position, 0))

                elif reaction.emoji == RESET:
                    await self.player.reset_equalizer()

                elif reaction.emoji == STOP:
                    try:
                        await self.msg.clear_reactions()
                    except discord.HTTPException:
                        pass
                    break

                await self.msg.remove_reaction(reaction.emoji, user)

            except discord.HTTPException:
                if self.ctx.channel.permissions_for(self.ctx.me).add_reactions:
                    await self.ctx.send(get_str(self.ctx, 'need-manage-messages-permission'))
                elif self.ctx.channel.permissions_for(self.ctx.me).manage_messages:
                    await self.ctx.send(get_str(self.ctx, 'need-add-emojis'))
                else:
                    await self.ctx.send(get_str(self.ctx, 'need-manage-messages-permission') + ' ' + get_str(self.ctx, 'need-add-emojis'))
                break

    def visual(self, equalizer, position):
        block = ''
        gains = [1.0, 0.75, 0.5, 0.25, 0.0, -0.25]
        bands = [r for r in range(10)]
        bands = [f'{self.freqs[band]:>2}' for band in bands]
        bands += [' A', ' B', ' C', ' D', ' E']
        bottom = ' ' * 7 + ''.join(bands)
        if position is not None:  # cus 0 doesn't work with only not
            bottom += f'\n{" " * 8}{"  " * position}^'

        for gain in gains:
            prefix = ' '

            if gain >= 0:
                prefix = '+'
            else:
                prefix = ''

            block += f'{prefix}{gain:.2f} | '

            for value in self.bands:
                if value >= gain:
                    block += '▄ '

                else:
                    block += '  '

            block += '\n'

        block += bottom
        return block


class Lazyer:
    REACTIONS = (ARROW_LEFTLEFT, PAUSE, STOP, ARROW_RIGHTRIGHT,
                 REPLAY, REPLAY_ONE, SHUFFLE, VOL_UP, VOL_DOWN)

    def __init__(self, channel, bot, player):
        self.channel = channel
        self.color = COLOR
        self.timeout = 30
        self.player = player
        self.bot = bot
        self.embed = None
        self.ctx = None

    @property
    def reactions(self):
        return (ARROW_LEFTLEFT, PAUSE, STOP, ARROW_RIGHTRIGHT, REPLAY, REPLAY_ONE, SHUFFLE, VOL_UP, VOL_DOWN)

    def check(self, reaction, user):
        if not self.player.npmsg:
            return False
        if user.bot:
            return False
        elif reaction.message.id != self.player.npmsg.id:
            return False
        elif not self.player:
            return False
        elif not self.player.connected_channel:
            return False
        return True

    async def send_to_channel(self):
        if self.channel.guild.id in tasks:
            tasks[self.channel.guild.id].cancel()
            del tasks[self.channel.guild.id]
        task = asyncio.ensure_future(self.task_to_channel())
        tasks[self.channel.guild.id] = task
        # await task

    async def task_to_channel(self):
        self.player.npmsg = await self.channel.send(embed=self.embed)
        for r in self.reactions:
            try:
                await self.player.npmsg.add_reaction(r)
            except (discord.HTTPException, AttributeError):
                break

        while self.player and self.player.npmsg:
            param = None
            try:
                try:
                    reaction, user = await self.bot.wait_for('reaction_add', check=self.check, timeout=self.timeout)
                except asyncio.TimeoutError:
                    try:
                        if self.player.npmsg:
                            await self.player.npmsg.clear_reactions()
                    except discord.HTTPException:
                        pass
                    break

                if user.id not in self.player.connected_channel.voice_states:
                    try:
                        await self.player.npmsg.remove_reaction(reaction.emoji, user)
                    except discord.HTTPException:
                        pass
                    continue

                if reaction.emoji == ARROW_LEFTLEFT:
                    cmd = self.bot.get_command('previousnow')

                elif reaction.emoji == ARROW_RIGHTRIGHT:
                    cmd = self.bot.get_command('skip')

                elif reaction.emoji == PAUSE:
                    cmd = self.bot.get_command('pause')

                elif reaction.emoji == STOP:
                    cmd = self.bot.get_command('stop')

                elif reaction.emoji == REPLAY:
                    cmd = self.bot.get_command('repeat')

                elif reaction.emoji == REPLAY_ONE:
                    cmd = self.bot.get_command('replay')

                elif reaction.emoji == SHUFFLE:
                    cmd = self.bot.get_command('shuffle')

                elif reaction.emoji == VOL_UP:
                    cmd = self.bot.get_command('volume')
                    param = min(100, self.player.volume + 10)
                    if param == 100 == self.player.volume:
                        try:
                            await self.player.npmsg.remove_reaction(reaction.emoji, user)
                        except discord.HTTPException:
                            pass
                        continue

                elif reaction.emoji == VOL_DOWN:
                    cmd = self.bot.get_command('volume')
                    param = max(0, self.player.volume - 10)
                    if param == 0 == self.player.volume:
                        try:
                            await self.player.npmsg.remove_reaction(reaction.emoji, user)
                        except discord.HTTPException:
                            pass
                        continue

                else:
                    try:
                        await self.player.npmsg.remove_reaction(reaction.emoji, user)
                    except discord.HTTPException:
                        pass
                    continue

                self.ctx = await self.bot.get_context(reaction.message)
                self.ctx.author = user
                self.ctx.command = cmd

                if await self.invoke_react(cmd, self.ctx):
                    if param is not None:  # can be 0
                        asyncio.ensure_future(self.ctx.invoke(cmd, str(param)))
                    else:
                        asyncio.ensure_future(self.ctx.invoke(cmd))

                try:
                    await self.player.npmsg.remove_reaction(reaction.emoji, user)
                except discord.HTTPException:
                    pass

            except discord.Forbidden:
                if self.channel.permissions_for(self.channel.guild.me).add_reactions:
                    await self.channel.send(get_str(self.channel.guild, 'need-manage-messages-permission', self.bot))
                elif self.channel.permissions_for(self.channel.guild.me).manage_messages:
                    await self.channel.send(get_str(self.channel.guild, 'need-add-emojis', self.bot))
                else:
                    await self.channel.send(get_str(self.channel.guild, 'need-manage-messages-permission', self.bot) + ' ' + get_str(self.channel.guild, 'need-add-emojis', self.bot))
                break

    async def invoke_react(self, cmd, ctx):
        if not cmd._buckets.valid:
            return True

        if not (await cmd.can_run(ctx)):
            return False

        bucket = cmd._buckets.get_bucket(ctx)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            return False
        return True
