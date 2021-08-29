import os
import re
import discord
import logging
import mimetypes
import datetime

from time import time
from glob import glob
from utils.dataIO import dataIO
from discord.ext import commands
from TextToOwO import owo

config = dataIO.load_json("config/settings.json")

token = config["TOKEN"]
globprefix = config["PREFIX"]
ver = config["VER"]
owner_id = int(config["OWNER_ID"])
def_v = int(config["DEF_VOL"])
def_time = int(config["DEF_TIMEOUT"])
def_vote = int(config["DEF_VOTE"])
db_host = config["DB_HOST"]
db_port = config["DB_PORT"]

log = logging.getLogger("launcher")
uptime = time()
no_lang_loaded = dataIO.load_json("config/i18n/english.json")
if def_time < 0:
    def_time = 0
if 150 < def_v < 0:
    def_v = 100

# Regex
url_rx = re.compile('https?:\/\/(?:www\.)?.+')  # noqa: W605
local_rx = re.compile('.*\.[a-zA-Z0-9]+$')
illegal_rx = re.compile("[///:*?\"<>|@]")
time_rx = re.compile('[0-9]+')


class VoiceConnectionError(commands.CommandError):
    """Custom Exception for cases of connection errors."""


class NoVoiceChannel(VoiceConnectionError):
    """Exception for cases of no voice channel to join."""


class Jikan(object):
    """Class to make an object from a dict."""

    def __init__(self, d):
        for a, b in d.items():
            if isinstance(b, (list, tuple)):
                setattr(self, a, [Jikan(x) if isinstance(
                    x, dict) else x for x in b])
            else:
                setattr(self, a, Jikan(b) if isinstance(b, dict) else b)


def get_server_prefixes(bot, server):
    """Gets the server prefix"""
    if not server:  # Assuming DMs
        return globprefix
    prefix = bot.prefixes_map.get(server.id, globprefix)
    return prefix


def get_str(ctx, cmd, bot=None, can_owo=True):
    """Funct to get answers from i18n folder."""
    lang = 'english'
    weeb = False

    if isinstance(ctx, commands.context.Context) and ctx.guild:
        gid = ctx.guild.id
        bot = ctx.bot
        lang = bot.languages_map.get(gid, 'english')
        weeb = bot.owo_map.get(gid, False)
        texthelp = ""
    elif isinstance(ctx, discord.Guild):
        gid = ctx.id
        if bot:
            lang = bot.languages_map.get(gid, 'english')
            weeb = bot.owo_map.get(gid, False)
    else:
        bot = ctx.bot

    if bot.loaded_languages:
        lang = [l for l in bot.loaded_languages if l.lower() == lang]
        if lang:
            lang = lang[0]
        else:
            lang = 'english'
        current_lang = bot.loaded_languages[lang]
    else:
        current_lang = no_lang_loaded
    try:
        text = current_lang[cmd]
    except KeyError:
        try:
            text = no_lang_loaded[cmd]
        except KeyError:
            # I didn't translated the help for weeb commands.
            if 'Weeb' not in bot.cogs or (cmd.split("-")[1] not in [g.name for g in bot.cogs['Weeb'].get_commands()]):
                log.error(f"TranslationError {lang} : {cmd} is not existing.")
            if '-help' in cmd and 'cmd-' in cmd:
                realcmd = cmd.replace('cmd-', '').replace('-help', '')
                texthelp = bot.get_command(realcmd).help.split("\n")[-1]
            text = texthelp or "This translation isn't working, please report this command and what you done to my dev with `=bug`."

    if weeb and can_owo:
        text = owo.text_to_owo(text)
        if 'help' in cmd or 'bot' in cmd or 'success' in cmd or 'failed' in cmd or 'dm' in cmd or 'warning' in cmd or '```' in text:
            #  I've to admit that it's ugly but it's a lazy way to check if Watora sends a code block
            # basically if it's in a code block remove back slashes cus they are displayed
            text = text.replace('\\', '')
    return text


def _list_cogs():
    """Displays all cogs."""
    cogs = [os.path.basename(f) for f in glob("cogs/*.py")]
    return [os.path.splitext(f)[0] for f in cogs]


def get_color(guild=None):
    """Gets the top role color otherwise select the Watora's main color"""
    if not guild or str(guild.me.color) == "#000000":
        return int("FF015B", 16)
    return guild.me.color


def get_image_from_url(text):
    """Gets the url and check if it's an image from a text."""

    for item in text.split(" "):
        try:
            url = re.search("(?P<url>https?://[^\s]+)", item).group("url")  # noqa: W605
            if url_is_image(url):
                return url
        except AttributeError:
            pass

    return None


def url_is_image(url):
    """Checks if the url point to an image."""
    mimetype, encoding = mimetypes.guess_type(url)
    if mimetype and mimetype.startswith('image'):
        return True

    ext = url.split('.')[-1].split("?")[0].lower()
    mimetype, encoding = mimetypes.guess_type(ext)
    # discord image url
    if ext in ["webp", "gif"] or (mimetype and mimetype.startswith('image')):
        return True

    return False


def match_url(url):
    """Checks if query match an url."""
    return url_rx.match(url)


def match_local(query):
    """Checks if query match a local file."""
    return local_rx.match(query) and len(query.split(' ')) == 1 and ('/' in query or '\\' in query)


def bytes2human(n):
    """Convertes bytes to humain readable values."""
    symbols = ('K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
    prefix = {}
    for i, s in enumerate(symbols):
        prefix[s] = 1 << (i + 1) * 10
    for s in reversed(symbols):
        if n >= prefix[s]:
            value = float(n) / prefix[s]
            return '%.1f%s' % (value, s)
    return "%sB" % n


def format_mentions(text):
    """Supress mentions from a text."""
    text = text.replace("@everyone", "@\u200beveryone")
    text = text.replace("@here", "@\u200bhere")
    return text


def get_uptime():
    """Gets current uptime."""
    secs = int(time() - uptime)
    return str(datetime.timedelta(seconds=secs))


def sweet_bar(current, max, length: int = 10):
    """Returns a sweet str bar with a max and min value."""
    prog_bar_str = ''
    percentage = 0.0
    progress_bar_length = length

    if max > 0:
        percentage = current / max
    for i in range(progress_bar_length):
        if (percentage <= 1 / progress_bar_length * i):
            prog_bar_str += '□'
        else:
            prog_bar_str += '■'

    return prog_bar_str


async def is_basicpatron(self, author, fetch=False, resp=None):
    """Checks if the user is basicpatron on my server."""
    return await check_if_role(self, author, fetch, resp, config["LOVER_ROLE"], config["BASIC_PATRON_ROLE"], config["PATRON_ROLE"])


async def is_patron(self, author, fetch=False, resp=None):
    """Checks if the user is patron on my server."""
    return await check_if_role(self, author, fetch, resp, config["PATRON_ROLE"], config["LOVER_ROLE"])


async def is_lover(self, author, fetch=False, resp=None):
    """Checks if the user is Lover on my server."""
    return await check_if_role(self, author, fetch, resp, config["LOVER_ROLE"])


async def is_voter(self, author, fetch=False, resp=None):
    """Checks if the user is Voter on my server."""
    return await check_if_role(self, author, fetch, resp, 498278262607314974, 341716510122835969, 341723457693810689, 341726906661470210)


async def check_if_role(self, author, fetch, resp, *role_id):
    if isinstance(author, discord.Member):
        author = author.id
    if author == owner_id:
        return True
    if not resp:
        try:
            resp = await self.http.get_member(268492317164437506, author)
        except discord.HTTPException:
            return False

    roles_id = resp.get('roles', [])

    if any(r for r in role_id if r in roles_id or str(r) in roles_id):
        if fetch:
            return resp
        return True

    return False


def is_admin(author, channel):
    """Checks if the user has administrator permission in the guild"""
    perms = channel.permissions_for(author)
    # perms.administrator is useless here lul
    if perms.administrator or perms.manage_guild or author.id == owner_id:
        return True
    return False


def is_alone(author):
    """Checks if the user is alone in a voice channel"""
    if not author.guild.me.voice or not author.voice:
        return False
    num_voice = sum(1 for m in author.voice.channel.members if not (
        m.voice.deaf or m.bot or m.voice.self_deaf))
    if num_voice == 1 and author.guild.me.voice.channel == author.voice.channel:
        return True
    return False


def is_modo(author, channel):
    """Checks if the user can deletes message in a voice channel"""
    perms = channel.permissions_for(author)
    if perms.manage_guild or perms.manage_messages or author.id == owner_id:
        return True


def illegal_char(string):
    """Checks if there are illegal characters in a string"""
    return illegal_rx.search(string)
