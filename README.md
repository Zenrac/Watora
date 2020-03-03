<a href="https://www.patreon.com/watora"><img alt="Become a Watora's Patron" src="https://c5.patreon.com/external/logo/become_a_patron_button.png" height="35px"></a><br>
# Watora
Here's the official repository of Watora, the discord music bot.

## Requirements: <br>
- [Python3.6+ with pip](https://www.python.org/downloads/)<br>
- [mongodb](https://www.mongodb.com/download-center/community) <br>
- [Java](https://www.java.com/fr/download/) <br>
- [Watora Translations](https://github.com/Zenrac/watora-translations)

## Installation
```
git clone https://github.com/Zenrac/Watora
cd Watora
```
Install or update all dependencies with `update.bat` on Windows, or `update.sh` on Linux.<br>

## Get Started
- Fill your credentials and tokens in `config/tokens.json` and `settings.json`, you can use the examples as a base.<br>
- Start a mongo server in a terminal with `mongod`.<br>
- Make sure that you have at least one [Lavalink server](https://github.com/Frederikam/Lavalink) running to use music features.<br>
- [Watora Translations](https://github.com/Zenrac/watora-translations) are supposed to go into `config/i18n/`<br>
- You may have to delete the `cogs/web.py` cog has it will not be useful in any point for a local bot.<br>
- Start Watora with `run.bat` on Windows, or `run.sh` on Linux.<br>

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details

[![Discord Bots](https://discordbots.org/api/widget/220644154177355777.svg)](https://discordbots.org/bot/220644154177355777)
