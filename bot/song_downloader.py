from pathlib import Path
from dotenv import load_dotenv
import os
from os import listdir
from os.path import isfile, join
from datetime import datetime, timedelta
import json

from concurrent.futures import ThreadPoolExecutor
from deezer import Deezer
from deezer import TrackFormats
from deemix import generateDownloadObject
from deemix.settings import load as loadSettings
from deemix.utils import getBitrateNumberFromText, formatListener
import deemix.utils.localpaths as localpaths
from deemix.downloader import Downloader
from deemix.itemgen import GenerationError
from deemix.plugins.spotify import Spotify
from deemix.itemgen import generateTrackItem
from deemix.types.DownloadObjects import Single, Collection
from deemix.types.Track import Track
from deemix.utils.pathtemplates import generatePath
from zipfile import ZipFile

import discord
from timer import Timer

from exceptions import *


class LogListener:
    @classmethod
    def send(cls, key, value=None):
        logString = formatListener(key, value)
        if logString:
            print(logString)

# ----------GLOBAL SETTINGS----------


load_dotenv()
ARL = os.getenv('DEEZER_ARL')

# Check for local configFolder
localpath = Path('.')
configFolder = localpath / 'config'

# Init settings
settings = loadSettings(configFolder)

# Load deezer
dz = Deezer()
listener = LogListener()
plugins = {
    "spotify": Spotify(configFolder=configFolder)
}
plugins["spotify"].setup()

# Load account
dz.login_via_arl(ARL)
# country = get_account_country()

# Init custom arl
custom_arls = {}

# ------------------------------------


def get_format(bitrate: int | str,):
    if bitrate == TrackFormats.FLAC:
        format_ = 'flac'
    else:
        format_ = 'mp3'

    return format_


# def get_account_country(path: str = 'config/settings.json'):
#     with open(path, 'r') as json_file:
#         settings = json.load(json_file)

#     return settings['country']

def recursive_write(path, zip_file):
    for entry in listdir(path):
        full_path = os.path.join(path, entry)
        if os.path.isdir(full_path):
            recursive_write(full_path, zip_file)
        else:
            print('write:', full_path)
            zip_file.write(full_path)


def get_objects(
    url: str | list,
    dz: Deezer,
    bitrate: str,
    plugins: dict,
    listener: LogListener,
) -> list:
    links = []
    for link in url:
        if ';' in link:
            for l in link.split(";"):
                links.append(l)
        else:
            links.append(link)

    downloadObjects = []

    for link in links:
        try:
            downloadObject = generateDownloadObject(
                dz,
                link,
                bitrate,
                plugins,
                listener
            )
        except GenerationError as e:
            print(f"{e.link}: {e.message}")
            continue
        if isinstance(downloadObject, list):
            downloadObjects += downloadObject
        else:
            downloadObjects.append(downloadObject)

    return downloadObjects


def load_arl(user_id: int, arl: str) -> Deezer:
    global custom_arls
    global dz
    if arl == ARL:
        return dz
    elif user_id in custom_arls:
        return custom_arls[user_id]
    else:
        # New Deezer instance
        new_dz = Deezer()
        new_dz.login_via_arl(arl)
        custom_arls[user_id] = new_dz
        return new_dz


def init_dl(
    url: str,
    guild_id: int,
    brfm: str = 'mp3 320',
    arl: str = ARL,
    settings: dict = settings
) -> tuple[list, str, Deezer]:
    # Check if custom_arl
    dz = load_arl(guild_id, arl)

    # Set the path according to the bitrate/format
    settings['downloadLocation'] = f'{settings['downloadLocation']}/{brfm}'
    bitrate = getBitrateNumberFromText(str(brfm))
    format_ = get_format(bitrate)

    brfm = brfm.lower()

    # Init objects
    url = [url]
    downloadObjects = get_objects(
        url=url,
        dz=dz,
        bitrate=bitrate,
        plugins=plugins,
        listener=listener,
    )
    converted_objs = []

    for obj in downloadObjects:
        if obj.__type__ == "Convertable":
            obj = plugins[obj.plugin].convert(
                dz,
                obj,
                settings,
                listener
            )
        converted_objs.append(obj)


    return converted_objs, format_


async def download_links(
    dz: Deezer,
    downloadObjects: list,
    ctx: discord.ApplicationContext | None = None,
    timer: Timer | None = None,
    settings: dict = settings
) -> list:
    all_data = []
    for obj in downloadObjects:
        # Create Track object to get final path
        try:
            all_data += await Downloader(
                dz,
                obj,
                settings,
                ctx,
                listener,
                timer
            ).start()
        except TrackNotFound:
            if len(downloadObjects) > 1 and ctx:
                ctx.respond("A song could not be downloaded, "
                            "try using a different ARL.")
            else:
                raise TrackNotFound

    return all_data


async def download(
    downloadObjects: list,
    format_: str,
    guild_id: int,
    ctx: discord.ApplicationContext,
    arl: str = ARL,
    timer: Timer | None = None,
) -> dict:
    # Check if custom_arl
    dz = load_arl(guild_id, arl)

    # Download all
    all_data = await download_links(
        dz,
        downloadObjects,
        ctx=ctx,
        timer=timer,
    )

    # [0][0]: API, [0][1]: Path
    real_final = ''
    path_count = len(all_data)
    if path_count == 0:
        raise TrackNotFound
    # Case 1: It's not a song
    elif path_count > 1 or all_data[0]['path'].is_dir():

        # Case 1.1: There is only one folder
        if path_count == 1:
            real_final = ("./output/archives/songs/"
                          f"{all_data[0]['title']}.zip")

        # Case 1.2: There is *not* only one folder
        else:
            now = datetime.now()
            ts = datetime.timestamp(now)
            real_final = ("./output/archives/songs/"
                          f"Compilation {ts}.zip")

        # Init the zip file
        zip_file = ZipFile(real_final, mode='w')

        # Add files associated to each path
        for info_dict in all_data:
            path = info_dict['path']
            print('path:', path)

            # Case 1.1.1: One of the thing is a folder
            if path.is_dir():
                recursive_write(path, zip_file)
            # Case 1.1.2: One of the thing is a song
            else:
                if format_ in str(path) and path.is_file():
                    zip_file.write(path)

        zip_file.close()
        return {'all_data': all_data, 'path': real_final}
    # Case 2: It's a song
    else:
        return {'all_data': all_data, 'path': all_data[0]['path']}