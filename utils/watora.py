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

log = logging.getLogger("launcher")
uptime = time()
no_lang_loaded = dataIO.load_json("config/i18n/english.json")
if def_time < 0:
    def_time = 0
if 150 < def_v < 0:
    def_v = 100

# Regex
url_rx = re.compile('https?:\/\/(?:www\.)?.+')  # noqa: W605
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
               setattr(self, a, [Jikan(x) if isinstance(x, dict) else x for x in b])
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
            if 'Weeb' not in bot.cogs or (cmd.split("-")[1] not in [g.name for g in bot.cogs['Weeb'].get_commands()]):  # I didn't translated the help for weeb commands.
                log.error(f"TranslationError {lang} : {cmd} is not existing.")
            text = "This translation isn't working, please report this command and what you done to my dev with `=bug`."

    if weeb and can_owo:
        text = owo.text_to_owo(text)
        if 'help' in cmd or 'bot' in cmd or 'success' in cmd or 'failed' in cmd or 'dm' in cmd or 'warning' in cmd or '```' in text:
            #  I've to admit that it's ugly but it's a lazy way to check if Watora sends a code block
            text = text.replace('\\', '')  # basically if it's in a code block remove back slashes cus they are displayed
    return text


def _list_cogs():
    """Displays all cogs."""
    cogs = [os.path.basename(f) for f in glob("cogs/*.py")]
    return [os.path.splitext(f)[0] for f in cogs]


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
    if ext in ["webp", "gif"] or (mimetype and mimetype.startswith('image')):  # discord image url
        return True

    return False


def match_url(url):
    """Checks if query match an url."""
    return url_rx.match(url)


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


def sweet_bar(current, max):
    """Returns a sweet str bar with a max and min value."""
    prog_bar_str = ''
    percentage = 0.0
    progress_bar_length = 30

    if max > 0:
        percentage = current / max
    for i in range(progress_bar_length):
        if (percentage <= 1 / progress_bar_length * i):
            prog_bar_str += '□'
        else:
            prog_bar_str += '■'

    return prog_bar_str


def is_basicpatron(self, author):
    """Checks if the user is basicpatron on my server."""
    return check_if_role(self, author, 341716510122835969)


def is_patron(self, author):
    """Checks if the user is patron on my server."""
    return check_if_role(self, author, 341723457693810689)


def is_lover(self, author):
    """Checks if the user is Lover on my server."""
    return check_if_role(self, author, 341726906661470210)


def is_voter(self, author):
    """Checks if the user is Voter on my server."""
    return check_if_role(self, author, 498278262607314974)


def check_if_role(self, author, role_id):
    if isinstance(author, discord.Member):
        author = author.id
    server = self.get_guild(268492317164437506)
    member = server.get_member(author)
    role = server.get_role(role_id)
    if not all([server, member, role]):
        return False
    return (role in member.roles or member.id == owner_id)


def is_admin(author, channel):
    """Checks if the user has administrator permission in the guild"""
    perms = channel.permissions_for(author)
    if perms.administrator or perms.manage_guild or author.id == owner_id:  # perms.administrator is useless here lul
        return True
    return False


def is_alone(author):
    """Checks if the user is alone in a voice channel"""
    if not author.guild.me.voice or not author.voice:
        return False
    num_voice = sum(1 for m in author.voice.channel.members if not (m.voice.deaf or m.bot or m.voice.self_deaf))
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