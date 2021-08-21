import re
import asyncio
import lavalink

from random import randrange
from lavalink.events import PlayerUpdateEvent
from time import time as current_time

from utils.db import SettingsDB
from utils.blindtest.blindtest import BlindTest
from utils.watora import def_time


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