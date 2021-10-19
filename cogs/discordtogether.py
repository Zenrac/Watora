import discord
from discord.ext import commands
from discordTogether import DiscordTogether
from utils.watora import get_str, get_color

class discordtogether(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.togetherControl = DiscordTogether(bot)

    @commands.command(aliases=['youtube'])
    async def youtubetogether(self, ctx):
        """
            {command_prefix}youtube

        Starts the youtube activity in your voice channel.
        """
        if not ctx.author.voice:
            return await ctx.send(get_str(ctx, "music-join-no-channel"))
        link = await self.togetherControl.create_link(ctx.author.voice.channel.id, 'youtube')

        embed=discord.Embed(
            title="Youtube Together",
            description=f"[Click Here]({link})",
            color=get_color(ctx.guild)
        )
        await ctx.send(embed=embed)

    @commands.command(aliases=['poker'])
    async def pokertogether(self, ctx):
        """
            {command_prefix}poker

        Starts the poker activity in your voice channel.
        """
        if not ctx.author.voice:
            return await ctx.send(get_str(ctx, "music-join-no-channel"))
        link = await self.togetherControl.create_link(ctx.author.voice.channel.id, 'poker')

        embed=discord.Embed(
            title="Poker Together",
            description=f"[Click Here]({link})",
            color=get_color(ctx.guild)
        )
        await ctx.send(embed=embed)

    @commands.command(aliases=['chess'])
    async def chesstogether(self, ctx):
        """
            {command_prefix}chess

        Starts the chess activity in your voice channel.
        """
        if not ctx.author.voice:
            return await ctx.send(get_str(ctx, "music-join-no-channel"))
        link = await self.togetherControl.create_link(ctx.author.voice.channel.id, 'chess')

        embed=discord.Embed(
            title="Chess Together",
            description=f"[Click Here]({link})",
            color=get_color(ctx.guild)
        )
        await ctx.send(embed=embed)

    @commands.command(aliases=['betrayal'])
    async def betrayaltogether(self, ctx):
        """
            {command_prefix}betrayal

        Starts the betrayal activity in your voice channel.
        """
        if not ctx.author.voice:
            return await ctx.send(get_str(ctx, "music-join-no-channel"))
        link = await self.togetherControl.create_link(ctx.author.voice.channel.id, 'betrayal')

        embed=discord.Embed(
            title="Betrayal Together",
            description=f"[Click Here]({link})",
            color=get_color(ctx.guild)
        )
        await ctx.send(embed=embed)

    @commands.command(aliases=['fishing'])
    async def fishingtogether(self, ctx):
        """
            {command_prefix}fishing

        Starts the fishing activity in your voice channel.
        """
        if not ctx.author.voice:
            return await ctx.send(get_str(ctx, "music-join-no-channel"))
        link = await self.togetherControl.create_link(ctx.author.voice.channel.id, 'fishing')

        embed=discord.Embed(
            title="Fishing Together",
            description=f"[Click Here]({link})",
            color=get_color(ctx.guild)
            )
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(discordtogether(bot))