"""
The MIT License

Copyright (c) Lavalink.py (https://github.com/Devoxin/Lavalink.py)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""


import zlib
import discord

from discord.ext import commands


class SocketFix(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self._zlib = zlib.decompressobj()
        self._buffer = bytearray()

    @commands.Cog.listener('on_socket_raw_receive')
    async def on_socket_raw_receive(self, msg):
        """ This is to replicate discord.py's 'on_socket_response' that was removed from discord.py v2 """
        if type(msg) is bytes:
            self._buffer.extend(msg)

            if len(msg) < 4 or msg[-4:] != b'\x00\x00\xff\xff':
                return

            try:
                msg = self._zlib.decompress(self._buffer)
            except Exception:
                self._buffer = bytearray()  # Reset buffer on fail just in case...
                return

            msg = msg.decode('utf-8')
            self._buffer = bytearray()

        msg = discord.utils.from_json(msg)
        self.bot.dispatch('socket_custom_receive', msg)

def setup(bot):
    bot.add_cog(SocketFix(bot))