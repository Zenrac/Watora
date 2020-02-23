"""
The MIT License

Copyright (c) 2015-2020 Just-Some-Bots (https://github.com/Just-Some-Bots)
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

import aiohttp
import asyncio
import base64
import time

from utils.watora import log


class SpotifyError(Exception):
    pass


class Spotify:
    OAUTH_TOKEN_URL = 'https://accounts.spotify.com/api/token'
    API_BASE = 'https://api.spotify.com/v1/'

    def __init__(self, client_id, client_secret, aiosession=None, loop=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.aiosession = aiosession if aiosession else aiohttp.ClientSession()
        self.loop = loop if loop else asyncio.get_event_loop()

        self.token = None

    def _make_token_auth(self, client_id, client_secret):
        auth_header = base64.b64encode(
            (client_id + ':' + client_secret).encode('ascii'))
        return {'Authorization': 'Basic %s' % auth_header.decode('ascii')}

    async def get_track(self, uri):
        """Get a track's info from its URI"""
        return await self.make_spotify_req(self.API_BASE + 'tracks/{0}'.format(uri))

    async def get_album(self, uri):
        """Get an album's info from its URI"""
        return await self.make_spotify_req(self.API_BASE + 'albums/{0}'.format(uri))

    async def get_playlist(self, user, uri):
        """Get a playlist's info from its URI"""
        return await self.make_spotify_req(self.API_BASE + 'users/{0}/playlists/{1}'.format(user, uri))

    async def get_playlist_tracks(self, uri):
        """Get a list of a playlist's tracks"""
        return await self.make_spotify_req(self.API_BASE + 'playlists/{0}/tracks'.format(uri))

    async def get_artist_albums(self, uri):
        """Get a list of album of an artist"""
        return await self.make_spotify_req(self.API_BASE + 'artists/{0}/albums'.format(uri))

    async def make_spotify_req(self, url):
        """Proxy method for making a Spotify req using the correct Auth headers"""
        token = await self.get_token()
        return await self.make_get(url, headers={'Authorization': 'Bearer {0}'.format(token)})

    async def make_get(self, url, headers=None):
        """Makes a GET request and returns the results"""
        async with self.aiosession.get(url, headers=headers) as r:
            if r.status != 200:
                raise SpotifyError('Issue making GET request to {0}: [{1.status}] {2}'.format(url, r, await r.json()))
            return await r.json()

    async def make_post(self, url, payload, headers=None):
        """Makes a POST request and returns the results"""
        async with self.aiosession.post(url, data=payload, headers=headers) as r:
            if r.status != 200:
                raise SpotifyError('Issue making POST request to {0}: [{1.status}] {2}'.format(url, r, await r.json()))
            return await r.json()

    async def get_token(self):
        """Gets the token or creates a new one if expired"""
        if self.token and not await self.check_token(self.token):
            return self.token['access_token']

        token = await self.request_token()
        if not token:
            raise SpotifyError(
                'Requested a token from Spotify, did not end up getting one')
        token['expires_at'] = int(time.time()) + token['expires_in']
        self.token = token
        log.debug('Created a new access token: {0}'.format(token))
        return self.token['access_token']

    async def check_token(self, token):
        """Checks a token is valid"""
        now = int(time.time())
        return token['expires_at'] - now < 60

    async def request_token(self):
        """Obtains a token from Spotify and returns it"""
        payload = {'grant_type': 'client_credentials'}
        headers = self._make_token_auth(self.client_id, self.client_secret)
        r = await self.make_post(self.OAUTH_TOKEN_URL, payload=payload, headers=headers)
        return r
