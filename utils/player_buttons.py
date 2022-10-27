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
