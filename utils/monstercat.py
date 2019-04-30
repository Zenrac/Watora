import aiohttp
import asyncio

from time import time as current_time
from bs4 import BeautifulSoup


class Client():
    def __init__(self, loop=None, aiosession=None):
        self._headers = {
            "User-Agent": "monstercatFM (https://github.com/Zenrac/monstercatFM)",
            "Content-Type": "application/json",
        }
        self.url = "https://mctl.io/"
        self.handler = None
        self._loop = loop or asyncio.get_event_loop()
        self.now_playing = None
        self.run = False
        self.tries = 1
        self.session = aiosession if aiosession else aiohttp.ClientSession(loop=self._loop)

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        return self._loop

    async def get_old_tracks(self, nb=None):
        """Gets previous tracks, can load 15, 25, 50 or 100 tracks other number returns 15."""
        if nb in [25, 50, 100]:
            url = self.url + "?l={}".format(nb)  # f-string only supported on py3.6+
        else:
            url = self.url

        async with self.session.get(url, headers=self._headers) as resp:
            if resp.status == 200:
                text = await resp.read()
                text = BeautifulSoup(text, 'lxml')
                text = text.find_all("tr")
                result = []
                for tex in text:
                    result.append(tex.text)
                results = result[1:]

                data = []
                for res in results:
                    ordered = []
                    occs = res.split('\n')
                    for occ in occs:
                        if occ and ('http' not in occ and not occ[1:2].isdigit()):
                            ordered.append(occ)
                    data.append(ordered)
                return data

    async def transform_html(self, text):
        """Makes html readable with BeautifulSoup and returns current track"""
        text = BeautifulSoup(text, 'lxml')
        text = text.find_all("p", {"name": "np-element"})
        result = []
        for tex in text:
            if tex.text not in result:  # avoid info occurrences
                if 'by ' in tex.text:
                    result.append(tex.text.replace('by ', ''))
                else:
                    result.append(tex.text)
        return result[1:]

    async def get_duration(self, text):
        """Gets duration from HTML with BeautifulSoup"""
        text = BeautifulSoup(text, 'lxml')
        text = text.find(id="duration")
        return int(text.text)

    async def is_not_sync(self, text):
        """Returns diff between current time and when the song started"""
        text = BeautifulSoup(text, 'lxml')
        text = text.find(id="time")
        time = current_time() - (int(text.attrs['time'])/1000)  # ms in html whereas time() is in s
        time -= 25  # don't know why but it always gives about 30 secs before the song started
        return time

    async def get_current_song(self):
        """Fonct to get the current song only"""
        if self.run:
            return self.now_playing
        song = await self.get_current_track()
        return song[0]

    async def get_current_track(self, handler=False):
        """Gets the current track informations"""
        async with session.get(self.url, headers=self._headers) as resp:
            if resp.status == 200:
                text = await resp.read()
                duration = await self.get_duration(text)
                sync = await self.is_not_sync(text)
                data = await self.transform_html(text)
                return data, duration, sync
            else:
                if handler:
                    await asyncio.sleep(60)  # Useless to spam requests if website is down
                else:
                    return None

    async def start(self):
        while self.run:
            if self.handler:
                current, duration, sync = await self.get_current_track(True)
                if current != self.now_playing:  # ignore if we already have the info
                    self.tries = 1
                    self.now_playing = current
                    await self.handler(current)
                    time = min((duration/1000), 600)  # can't be more than 10 mins, I think
                    if sync > 0:
                        time -= sync  # re-sync if needed
                    await asyncio.sleep(time)
                else:
                    self.tries += 1  # stupid counter to avoid spam when MC bot is down.
                    time = min(self.tries, 60)  # 1 request/min min after 60 fails
                    await asyncio.sleep(time)  # get info every sec until we are sync with songs durations etc...
            else:
                raise RuntimeError("No function handler specified")

            # I don't even know if using a aiohttp.get loop is a good idea
            # I tried to use websocket and socket.io, in vain. (lack of skills/knowledges ?)

    def register_handler(self, handler):
        """Registers a function handler to allow you to do something with the socket API data"""
        self.run = True
        self.handler = handler

    def switch_on_off(self):
        """Switch on or off the handler loop, returns current state"""
        self.run = not self.run
        return self.runimport aiohttp
import asyncio

from time import time as current_time
from bs4 import BeautifulSoup
