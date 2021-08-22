import re
import asyncio
import lavalink

from random import randrange
from lavalink.events import PlayerUpdateEvent
from time import time as current_time

from utils.db import SettingsDB
from utils.blindtest.blindtest import BlindTest
from utils.watora import def_time

from discord.voice_client import VoiceProtocol
from discord import abc, Client


class CustomVoice(VoiceProtocol):
    def __init__(self, client: Client, channel: abc.Connectable) -> None:
        super().__init__(client, channel)

    async def on_voice_state_update(self, data) -> None:
        retobj = {
            't': 'VOICE_STATE_UPDATE',
            'd': data
        }

        await self.client.lavalink.voice_update_handler(retobj)

    async def on_voice_server_update(self, data) -> None:
        retobj = {
            't': 'VOICE_SERVER_UPDATE',
            'd': data
        }

        await self.client.lavalink.voice_update_handler(retobj)

    async def connect(self, timeout = 60.0, reconnect = True):
        await self.channel.guild.change_voice_state(channel = self.channel)