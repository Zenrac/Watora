import motor.motor_asyncio

from abc import ABC
from utils.watora import globprefix, def_time, def_v, def_vote, db_host, db_port


class Settings(ABC):
    def __init__(self, id_):
        self._id = id_


class GuildSettings(Settings):
    def __init__(self, id, **kwargs):
        super().__init__(id)

        self.prefix = kwargs.get("prefix", globprefix)  # default prefix
        self.language = kwargs.get("language", "english")  # default language
        self.volume = kwargs.get("volume", def_v)  # default volume
        self.vote = kwargs.get("vote", def_vote)  # default vote percent
        self.timer = kwargs.get("timer", def_time)  # default timer value
        self.autoplay = kwargs.get("autoplay", False)
        self.owo = kwargs.get("owo", False)
        self.lazy = kwargs.get("lazy", False)
        self.channel = kwargs.get("channel", None)
        self.bound = kwargs.get("bound", None)
        self.defaultnode = kwargs.get("defaultnode", None)
        self.customcommands = kwargs.get("customcommands", {})
        self.points = kwargs.get("points", {})
        self.welcomes = kwargs.get("welcomes", {})
        self.goodbyes = kwargs.get("goodbyes", {})
        self.autosongs = kwargs.get("autosongs", {})
        self.djs = kwargs.get("djs", [])
        self.roles = kwargs.get("roles", [])
        self.autoroles = kwargs.get("autoroles", [])
        self.disabledchannels = kwargs.get("disabledchannels", {})
        self.disabledcommands = kwargs.get("disabledcommands", [])
        self.blacklisted = kwargs.get("blacklisted", [])
        self.clans = kwargs.get("clans", [])
        self.respect = kwargs.get("respect", 0)


class GlobSettings(Settings):
    def __init__(self, id, **kwargs):
        super().__init__(id)
        self.blacklisted = kwargs.get("blacklisted", [])
        self.autoplaylists = kwargs.get("autoplaylists", {})
        self.marry = kwargs.get("marry", {})
        self.donation = kwargs.get("donation", {})
        self.claim = kwargs.get("claim", {})
        self.animes = kwargs.get("animes", {})
        self.cachedanimes = kwargs.get("cachedanimes", {})
        self.server_count = kwargs.get("server_count", {})
        self.custom_hosts = kwargs.get("custom_hosts", {})
        self.source = kwargs.get("source", 'ytsearch')


class SettingsDB:
    _instance = None

    def __init__(self):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(db_host, db_port)
        self.db = self.client.Watora
        self.guild_settings_collection = self.db.settings
        self.glob_settings_collection = self.db.glob

    @staticmethod
    def get_instance():
        if not SettingsDB._instance:
            SettingsDB._instance = SettingsDB()
        return SettingsDB._instance

    async def get_glob_settings(self):
        document = await self.glob_settings_collection.find_one({"_id": 0})
        if document:
            return GlobSettings(document.get("_id"), **document)
        return GlobSettings(0)

    async def set_glob_settings(self, settings):
        return await self.glob_settings_collection.replace_one({"_id": 0}, settings.__dict__, True)

    async def get_guild_settings(self, id):
        document = await self.guild_settings_collection.find_one({"_id": id})
        if document:
            return GuildSettings(document.get("_id"), **document)
        return GuildSettings(id)

    async def set_guild_settings(self, settings):
        return await self.guild_settings_collection.replace_one({"_id": settings._id}, settings.__dict__, True)
