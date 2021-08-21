import re
import asyncio
import aiohttp

from jikanpy.exceptions import JikanException

from utils.db import SettingsDB
from utils.watora import Jikan


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