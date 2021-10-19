"""
The MIT License

Copyright (c) 2017-2020 Zenrac - Watora (https://github.com/Zenrac/Watora)

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


import asyncio
import aiohttp

from random import randrange
from urllib.parse import quote_plus


class YoutubeAPI:
    def __init__(self, youtube_token, loop=None, aiosession=None):
        self.youtube_token = youtube_token
        self.url = "https://www.googleapis.com/youtube/v3/"
        self.session = aiosession or aiohttp.ClientSession(loop=self.bot.loop)
        self.loop = loop or asyncio.get_event_loop()

    async def make_request(self, url):
        """Used to call youtune API"""
        url = f'{self.url}{url}&key={self.youtube_token}'
        async with self.session.get(url) as resp:
            if resp.status == 200:
                rep = await resp.json()
                await resp.release()
                return rep
        return {}

    async def youtube_search(self, query):
        """Allows to search"""
        search_response = await self.make_request(f'search?part=snippet&q={quote_plus(query)}')
        if not search_response:
            return {}
        videos = []
        for search_result in search_response.get('items', []):
            if search_result['id']['kind'] == 'youtube#video':
                track = {}
                track['uri'] = 'https://www.youtube.com/watch?v=' + \
                    search_result['id']['videoId']
                track['title'] = search_result['snippet']['title']
                videos.append(track)

        return videos

    async def get_youtube_title(self, player=None, *, id: list):
        if not isinstance(id, list):
            id = [id]
        found = {}
        while id:
            ids = id[:45]
            ready_ids = ','.join(ids)
            rep = await self.make_request(f'videos?part=snippet&id={ready_ids}')
            for x in ids:
                id.remove(x)
            if rep and rep['items']:
                for m in rep['items']:
                    found[m['id']] = m['snippet']['title']
        return found

    async def get_youtube_infos(self, id):
        rep = await self.make_request(f'videos?part=snippet&id={id}')
        if not rep:
            return None, None
        thumbnail = await self.get_youtube_thumbnail(rep)
        description = rep['items'][0]['snippet']['description']

        return thumbnail, description

    async def get_youtube_thumbnail(self, rep):
        """Gets song thumbnail from an ID or a youtube api response"""
        if not isinstance(rep, dict):
            rep = await self.make_request(f'videos?part=snippet&id={rep}')
            if not rep:
                return None
        thumb = rep['items'][0]['snippet']['thumbnails']
        best_res = list(thumb.values())[0]
        for res in list(thumb.values())[1:]:
            pixel = res['width'] * res['height']
            best_pixel = best_res['width'] * best_res['height']
            if best_pixel < pixel:
                best_res = res
        return best_res['url']

    async def get_recommendation(self, id: str, player=None):
        """Gets music recommendations from YouTube API from a specified ID"""
        rep = await self.make_request(f'search?part=snippet&relatedToVideoId={id}&type=video&id=10')
        if not rep:
            return {}
        results = rep['items']
        for result in results:
            if result['id']['videoId'] != id:
                if not player or (result['id']['videoId'] not in player.already_played):
                    if '1 hour' in result.get('snippet', {}).get('title', '').lower():  # Avoid 1 hour version
                        if player:
                            player.already_played.add(result['id']['videoId'])
                            player.already_played.add(id)
                        return result['id']['videoId']
        return results[randrange(len(results))]['id']['videoId']
        # If all recommendation have been already played..
        # Return a random result and hope it'll not create an
        # infinite recommendation loop, (this random should
        # prevent from this)
