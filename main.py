import discord
import asyncio


import logging
import os
from dotenv import load_dotenv
from bot.line import get_stickerpack
from bot.song_downloader import *
from deemix.exceptions import *
from bot.settings import *
from bot.fetch_arls import *
from bot.timer import Timer


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)


load_dotenv()
bot = discord.Bot()
TOKEN = os.getenv('DISCORD_TOKEN')
ARL = os.getenv('DEEZER_ARL')

vc_config_path = Path('.') / 'deemix' / 'vc_config'

# VC deemix settings: ignore tags and download only the song itself
# Init settings
vc_settings = loadSettings(vc_config_path)


@bot.command(name="ping", description='Test the reactivity of Ugoku !')
async def ping(ctx) -> None:
    latency = round(bot.latency*1000, 2)
    logging.info(f'Pinged latency: {latency}')
    await ctx.respond(f'あわあわあわわわ ! {latency}ms')


get = bot.create_group(
    "get",
    "Get stuff from Ugoku !"
)


@get.command(
    name='stickers',
    description='Download a LINE sticker pack from a given URL or a sticker pack ID.',
)
@discord.option(
    'url',
    type=discord.SlashCommandOptionType.string,
    description='URL of a sticker pack from LINE Store.',
)
@discord.option(
    'id',
    type=discord.SlashCommandOptionType.integer,
    description='Sticker pack ID. Can be found in the url.',
)
@discord.option(
    'gif',
    type=discord.SlashCommandOptionType.boolean,
    description=('Convert animated png to gifs, more widely supported. '
                 'Default: True.'),
    autocomplete=discord.utils.basic_autocomplete(
        [True, False]),
)
@discord.option(
    'loop',
    type=discord.SlashCommandOptionType.string,
    description=('Set how many times an animated sticker should be looped. '
                 'Default: forever.'),
    autocomplete=discord.utils.basic_autocomplete(
        ['never', 'forever']),
)
async def stickers(
    ctx: discord.ApplicationContext,
    id: str | None = None,
    url: int | None = None,
    gif: bool = True,
    loop=0,
) -> None:
    timer = Timer()

    if not id and not url:
        await ctx.respond(f'Please specify a URL or a sticker pack ID.')
    else:
        await ctx.respond(f'Give me a second !')
        if id:
            url = f'https://store.line.me/stickershop/product/{id}'
        zip_file = get_stickerpack(url, gif=gif, loop=loop)
        await ctx.send(
            file=discord.File(zip_file),
            content=(f"Sorry for the wait <@{ctx.author.id}> ! "
                     "Here's the sticker pack you requested.")
        )
        await ctx.edit(content=f'Done ! {timer.total()}')


@get.command(
    name='songs',
    description='Download your favorite songs !',
)
@discord.option(
    'url',
    type=discord.SlashCommandOptionType.string,
    description='Spotify/Deezer URL of a song, an album or a playlist. Separate urls with semi-colons.',
)
@discord.option(
    'format',
    type=discord.SlashCommandOptionType.string,
    description='The format of the files you want to save.',
    autocomplete=discord.utils.basic_autocomplete(
        ['FLAC', 'MP3 320', 'MP3 128']),
)
async def songs(
    ctx: discord.ApplicationContext,
    url,
    format: str | None = None,
) -> None:
    timer = Timer()

    await ctx.respond(f'Give me a second !')
    arl = get_setting(
        ctx.author.id,
        'publicArl',
        ARL
    )

    if not format:
        format = get_setting(
            ctx.user.id,
            'defaultMusicFormat',
            'MP3 320'
        )
    try:
        downloadObjects, format_ = init_dl(
            url=url,
            guild_id=ctx.guild_id,
            arl=arl,
            brfm=format
        )
        if not downloadObjects:
            raise TrackNotFound

        await ctx.edit(
            content=f'Download objects got, {timer.round()}. '
            'Fetching track data...'
        )
        results = await download(
            downloadObjects,
            format_,
            guild_id=ctx.guild_id,
            ctx=ctx,
            arl=arl,
            timer=timer,
        )
        path = results['path']

        size = os.path.getsize(path)
        ext = os.path.splitext(path)[1][1:]
        # To check if the Deezer account is paid (?)
        if 'zip' != ext and ext not in format.lower():
            raise InvalidARL

        logging.info(f'Chosen format: {format}')
        logging.info(f'File size: {size}, Path: {path}')

        if size >= ctx.guild.filesize_limit:
            if format != 'MP3 320' and format != 'MP3 128':

                await ctx.edit(
                    content='Track too heavy, trying '
                            'to download with MP3 320...'
                )
                downloadObjects, format_ = init_dl(
                    url=url,
                    guild_id=ctx.guild_id,
                    arl=arl,
                    brfm='mp3 320'
                )
                results = await download(
                    downloadObjects,
                    format_,
                    guild_id=ctx.guild_id,
                    ctx=ctx,
                    arl=arl,
                    timer=timer,
                )

                path = results['path']
                size = os.path.getsize(path)
                logging.info(f'File size: {size}, Path: {path}')
                if size >= ctx.guild.filesize_limit:
                    await ctx.edit(content='Track too heavy ￣へ￣')
                    return
            else:
                await ctx.edit(content='Track too heavy ￣へ￣')
                return
        # SUCESS:
        await ctx.edit(
            content=f'Download finished, {timer.round()}. Uploading...'
        )
        await ctx.send(
            file=discord.File(path),
            content=(f"Sorry for the wait <@{ctx.author.id}> ! "
                     "Here's the song(s) you requested. Enjoy (￣︶￣*))")
        )
        await ctx.edit(content=f'Done ! {timer.total()}')

    except InvalidARL:
        await ctx.edit(
            content=('The Deezer ARL is not valid. '
                     'Please contact the developer or use a custom ARL.')
        )
    except FileNotFoundError:
        await ctx.edit(
            content=('The Deezer ARL is not valid. '
                     'Please contact the developer or use a custom ARL.')
        )
    except TrackNotFound:
        await ctx.edit(
            content='Track not found on Deezer ! Try using another ARL.'
        )


set = bot.create_group(
    "set",
    "Change bot settings."
)


@set.command(
    name='default-music-format',
    description='Change your default music format.',
)
@discord.option(
    'format',
    type=discord.SlashCommandOptionType.string,
    description='The format of the files you want to save.',
    autocomplete=discord.utils.basic_autocomplete(
        ['FLAC', 'MP3 320', 'MP3 128']),
)
async def default_music_format(
    ctx: discord.ApplicationContext,
    format: str
) -> None:
    if format not in ['FLAC', 'MP3 320', 'MP3 128']:
        await ctx.respond('Please select a valid format !')
    else:
        await change_settings(
            ctx.author.id,
            'defaultMusicFormat',
            format
        )
        await ctx.respond('Your default music format '
                          f'has been set to {format} !')


@set.command(
    name='custom-arl',
    description='Change your Deezer localization.'
)
@discord.option(
    'country',
    type=discord.SlashCommandOptionType.string,
    description='Songs from this country should be more available.',
    autocomplete=discord.utils.basic_autocomplete(get_countries()),
)
async def custom_arl(
    ctx: discord.ApplicationContext,
    country: str
) -> None:
    arl = get_arl(country)
    if arl:
        await change_settings(ctx.author.id, 'publicArl', arl)
        await ctx.respond(
            f'You are now using a Deezer ARL from {country} !'
        )
    else:
        await ctx.respond(f"Sorry ! The country {country} isn't available.")


@set.command(
    name='default-arl',
    description='Change your Deezer localization.'
)
async def default_arl(ctx: discord.ApplicationContext) -> None:
    await change_settings(ctx.author.id, 'publicArl', ARL)
    await ctx.respond("You are now using the default ARL !")


vc = bot.create_group(
    "vc",
    "Voice channel commands."
)


# From https://gist.github.com/aliencaocao/83690711ef4b6cec600f9a0d81f710e5
server_sessions = {}


class ServerSession:
    def __init__(self, guild_id: int, voice_client: discord.voice_client):
        self.guild_id = guild_id
        self.voice_client = voice_client
        self.queue = []

    def display_queue(
        self
    ) -> str:
        currently_playing = (
            f"Currently playing: {self.queue[0]['display_name']}"
        )
        return currently_playing + '\n' + '\n'.join([f"{i + 1}. {s['display_name']}" for i, s in enumerate(self.queue[1:])])

    async def add_to_queue(
        self,
        ctx: discord.ApplicationContext,
        info_dict: dict
    ) -> None:  # does not auto start playing the playlist
        self.queue.append(info_dict)
        if self.voice_client.is_playing():
            await ctx.edit(
                content=f"Added to queue: {info_dict['display_name']}"
            )

    async def start_playing(self, ctx) -> None:
        self.voice_client.play(
            discord.FFmpegOpusAudio(
                self.queue[0]['path'], 
                bitrate=510,
            ),
            after=lambda e=None: self.after_playing(ctx, e)
        )
        await ctx.edit(
            content=f"Now playing: {self.queue[0]['display_name']}"
        )

    def after_playing(
        self,
        ctx: discord.ApplicationContext,
        error: Exception
    ) -> None:
        if error:
            raise error
        else:
            if self.queue:
                asyncio.run_coroutine_threadsafe(
                    self.play_next(ctx), 
                    bot.loop
                )

    # should be called only after making the
    # first element of the queue the song to play
    async def play_next(
        self,
        ctx: discord.ApplicationContext,
    ) -> None:
        self.queue.pop(0)
        if self.queue:
            await ctx.send(
                content=f"Now playing: {self.queue[0]['display_name']}"
            )
            self.voice_client.play(
                discord.FFmpegOpusAudio(self.queue[0]['path'], bitrate=510),
                after=lambda e=None: self.after_playing(ctx, e)
            )


@vc.command(
    name='join',
    description='Invite Ugoku in your voice channel !'
)
async def join(
    ctx: discord.ApplicationContext,
    channel: discord.VoiceChannel
) -> None:
    if ctx.voice_client is not None:
        await ctx.voice_client.move_to(channel)
        await ctx.edit(content=f'Joined {ctx.voice_client.channel.name} !')
    else:
        await channel.connect()
        await ctx.edit(content=f'Joined {ctx.voice_client.channel.name} !')

    if ctx.voice_client.is_connected():
        server_sessions[ctx.guild.id] = ServerSession(
            ctx.guild.id,
            ctx.voice_client
        )
        return server_sessions[ctx.guild.id]
    else:
        await ctx.edit(content=f'Failed to connect to voice channel {ctx.user.voice.channel.name}.')


@vc.command(
    name='play',
    description='(VERY LOUD !!!!1) Select a song to play.'
)
@discord.option(
    'url',
    type=discord.SlashCommandOptionType.string,
    description='Deezer or Spotify url of a song/album/playlist.'
)
async def play(
    ctx: discord.ApplicationContext,
    url: str
) -> None:
    await ctx.respond(f'Connecting to Deezer...')
    if url:
        try:
            # Download
            arl = get_setting(
                ctx.author.id,
                'publicArl',
                ARL
            )
            downloadObjects, _ = init_dl(
                url=url,
                guild_id=ctx.guild_id,
                arl=arl,
                brfm='flac',
                settings=vc_settings
            )
            dz = load_arl(ctx.user.id, arl)
            await ctx.edit(content=f'Getting the song...')
            all_data = await download_links(
                dz,
                downloadObjects,
                settings=vc_settings
            )
            info_dict = all_data[0]
            if not downloadObjects:
                raise TrackNotFound

            # Join
            guild_id = ctx.guild.id
            if guild_id not in server_sessions:
                # not connected to any VC
                if ctx.user.voice is None:
                    await ctx.send(
                        f'You are not connected to any voice channel !'
                    )
                    return
                else:
                    session = await join(ctx, ctx.user.voice.channel)

            else:  # is connected to a VC
                session = server_sessions[guild_id]
                if session.voice_client.channel != ctx.user.voice.channel:
                    # connected to a different VC than the command issuer
                    # (but within the same server)
                    await session.voice_client.move_to(ctx.user.voice.channel)
                    await ctx.send(f'Connected to {ctx.user.voice.channel}.')

            await session.add_to_queue(ctx, info_dict)
            if not session.voice_client.is_playing() and len(session.queue) <= 1:
                await session.start_playing(ctx)

        except TrackNotFound:
            await ctx.edit(
                content='Track not found on Deezer ! Try using another ARL.'
            )
    else:
        ctx.respond('wut duh')


@vc.command(
    name='pause',
    description='Pause the current song.'
)
async def pause(ctx: discord.ApplicationContext):
    guild_id = ctx.guild.id
    if guild_id in server_sessions:
        voice_client = server_sessions[guild_id].voice_client
        if voice_client.is_playing():
            voice_client.pause()
            await ctx.respond('Paused !')


@vc.command(
    name='resume',
    description='Resume the current song.'
)
async def resume(ctx: discord.ApplicationContext):
    guild_id = ctx.guild.id
    if guild_id in server_sessions:
        voice_client = server_sessions[guild_id].voice_client
        if voice_client.is_paused():
            voice_client.resume()
            await ctx.respond('Resumed !')


@vc.command(
    name='skip',
    description='Skip the current song.'
)
async def skip(ctx: discord.ApplicationContext):
    guild_id = ctx.guild.id
    if guild_id in server_sessions:
        session = server_sessions[guild_id]
        voice_client = session.voice_client
        if voice_client.is_playing():
            if len(session.queue) > 1:
                voice_client.stop()
                await ctx.respond('Skipped !')
            else:
                await ctx.respond('This is the last song in queue !')


@vc.command(
    name='queue',
    description='Show the current queue.'
)
async def show_queue(ctx: discord.ApplicationContext):
    guild_id = ctx.guild.id
    if guild_id in server_sessions:
        print('queue:', server_sessions[guild_id].display_queue())
        await ctx.respond(
            f'{server_sessions[guild_id].display_queue()}'
        )


@vc.command(
    name='bitrate',
    description='Get the bitrate of the voice channel you are in.',
)
async def channel_bitrate(
    ctx: discord.ApplicationContext
) -> None:
    try:
        await ctx.respond(f'{ctx.author.voice.channel.bitrate//1000}kbps.')
    except:
        await ctx.respond('You are not in a voice channel !')


bot.run(TOKEN)