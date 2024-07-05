""" This is a modified version of the original Zotify codebase.
I modified it so that it can be used as a library for the discord bot.
Functions that are not needed are removed.
Original codebase can be found here:
https://github.com/zotify-dev/zotify """


# For now Im just pasting all code into one single giant file, I will split it up later

import os
from dotenv import load_dotenv
from librespot.core import Session
from librespot.audio.decoders import VorbisOnlyAudioQuality
from librespot.audio.decoders import AudioQuality
from librespot.metadata import TrackId
import requests
import json
import time
import re
import platform
import uuid
import traceback
import ffmpy
import datetime
import math
import music_tag
from typing import Any, Tuple, List
from pathlib import Path, PurePath

""" URLs to interact with Spotify API """
FOLLOWED_ARTISTS_URL = 'https://api.spotify.com/v1/me/following?type=artist'
SEARCH_URL = 'https://api.spotify.com/v1/search'
TRACKS_URL = 'https://api.spotify.com/v1/tracks'
TRACK_STATS_URL = 'https://api.spotify.com/v1/audio-features/'
SAVED_TRACKS_URL = 'https://api.spotify.com/v1/me/tracks'


CODEC_MAP = {
    'aac': 'aac',
    'fdk_aac': 'libfdk_aac',
    'm4a': 'aac',
    'mp3': 'libmp3lame',
    'ogg': 'copy',
    'opus': 'libopus',
    'vorbis': 'copy',
}

EXT_MAP = {
    'aac': 'm4a',
    'fdk_aac': 'm4a',
    'm4a': 'm4a',
    'mp3': 'mp3',
    'ogg': 'ogg',
    'opus': 'ogg',
    'vorbis': 'ogg',
}

id: str = str(datetime.datetime.timestamp(datetime.datetime.now())).replace('.', '')

CONFIG = {
    'SAVE_CREDENTIALS':           True                                                              ,
    'CREDENTIALS_LOCATION':       ''                                                                ,
    'OUTPUT':                     ''                                                                ,
    'SONG_ARCHIVE':               ''                                                                ,
    'ROOT_PATH':                  Path('.').absolute() / 'output' / 'vc_songs' / 'OGG 320' / id     ,
    'ROOT_PODCAST_PATH':          ''                                                                ,
    'SPLIT_ALBUM_DISCS':          False                                                             ,
    'DOWNLOAD_LYRICS':            True                                                              ,
    'MD_SAVE_GENRES':             False                                                             ,
    'MD_ALLGENRES':               False                                                             ,
    'MD_GENREDELIMITER':          ','                                                               ,
    'DOWNLOAD_FORMAT':            'ogg'                                                             ,
    'DOWNLOAD_QUALITY':           'auto'                                                            ,
    'TRANSCODE_BITRATE':          'auto'                                                            ,
    'RETRY_ATTEMPTS':             1                                                                 ,
    'BULK_WAIT_TIME':             1                                                                 ,
    'OVERRIDE_AUTO_WAIT':         False                                                             ,
    'CHUNK_SIZE':                 20000                                                             ,
    'DOWNLOAD_REAL_TIME':         False                                                             ,
    'LANGUAGE':                   'en'                                                              ,
    'PRINT_SPLASH':               False                                                             ,
    'PRINT_SKIPS':                True                                                              ,
    'PRINT_DOWNLOAD_PROGRESS':    True                                                              ,
    'PRINT_ERRORS':               True                                                              ,
    'PRINT_DOWNLOADS':            False                                                             ,
    'PRINT_API_ERRORS':           True                                                              ,
    'PRINT_PROGRESS_INFO':        True                                                              ,
    'PRINT_WARNINGS':             True                                                              ,
    'TEMP_DOWNLOAD_DIR':          ''                                                                ,
}


# Im renaming the class from Zotify to Chinofy because why not XD
class Chinofy:    
    SESSION: Session = None

    def __init__(self, args):
        Chinofy.login(args)
        self.quality_options = {
            'auto': AudioQuality.VERY_HIGH if self.check_premium() else AudioQuality.HIGH,
            'normal': AudioQuality.NORMAL,
            'high': AudioQuality.HIGH,
            'very_high': AudioQuality.VERY_HIGH
        }
        Chinofy.DOWNLOAD_QUALITY = self.quality_options[CONFIG['DOWNLOAD_QUALITY']]

    @classmethod
    def login(cls, args):
        """ Authenticates with Spotify and saves credentials to a file """

        load_dotenv()
        username = os.getenv('SPOTIFY_USERNAME')
        password = os.getenv('SPOTIFY_PASSWORD')

        conf = Session.Configuration.Builder().set_store_credentials(False).build()
        cls.SESSION = Session.Builder(conf).user_pass(username, password).create()

    @classmethod
    def get_content_stream(cls, content_id, quality):
        return cls.SESSION.content_feeder().load(content_id, VorbisOnlyAudioQuality(quality), False, None)

    @classmethod
    def __get_auth_token(cls):
        return cls.SESSION.tokens().get_token(
            'user-read-email', 'playlist-read-private', 'user-library-read', 'user-follow-read'
        ).access_token

    @classmethod
    def get_auth_header(cls):
        return {
            'Authorization': f'Bearer {cls.__get_auth_token()}',
            'Accept-Language': 'en',
            'Accept': 'application/json',
            'app-platform': 'WebPlayer'
        }

    @classmethod
    def get_auth_header_and_params(cls, limit, offset):
        return {
            'Authorization': f'Bearer {cls.__get_auth_token()}',
            'Accept-Language': 'en',
            'Accept': 'application/json',
            'app-platform': 'WebPlayer'
        }, {'limit': limit, 'offset': offset}

    @classmethod
    def invoke_url_with_params(cls, url, limit, offset, **kwargs):
        headers, params = cls.get_auth_header_and_params(limit=limit, offset=offset)
        params.update(kwargs)
        return requests.get(url, headers=headers, params=params).json()

    @classmethod
    def invoke_url(cls, url, tryCount=0):
        # we need to import that here, otherwise we will get circular imports!
        from zotify.termoutput import Printer, PrintChannel
        headers = cls.get_auth_header()
        response = requests.get(url, headers=headers)
        responsetext = response.text
        try:
            responsejson = response.json()
        except json.decoder.JSONDecodeError:
            responsejson = {"error": {"status": "unknown", "message": "received an empty response"}}

        if not responsejson or 'error' in responsejson:
            if tryCount < (CONFIG['RETRY_ATTEMPTS'] - 1):
                Printer.print(PrintChannel.WARNINGS, f"Spotify API Error (try {tryCount + 1}) ({responsejson['error']['status']}): {responsejson['error']['message']}")
                time.sleep(5)
                return cls.invoke_url(url, tryCount + 1)

            Printer.print(PrintChannel.API_ERRORS, f"Spotify API Error ({responsejson['error']['status']}): {responsejson['error']['message']}")

        return responsetext, responsejson

    @classmethod
    def check_premium(cls) -> bool:
        """ If user has spotify premium return true """
        return (cls.SESSION.get_user_attribute('type') == 'premium')








def search(search_term: str):
    """ Searches download server's API for relevant data """
    params = {'limit': '10',
              'offset': '0',
              'q': search_term,
              'type': 'track,album,artist,playlist'}

    # Parse args, $ Chinono: might remove later
    splits = search_term.split()
    for split in splits:
        index = splits.index(split)

        if split[0] == '-' and len(split) > 1:
            if len(splits)-1 == index:
                raise IndexError('No parameters passed after option: {}\n'.
                                 format(split))

        if split == '-l' or split == '-limit':
            try:
                int(splits[index+1])
            except ValueError:
                raise ValueError('Parameter passed after {} option must be an integer.\n'.
                                 format(split))
            if int(splits[index+1]) > 50:
                raise ValueError('Invalid limit passed. Max is 50.\n')
            params['limit'] = splits[index+1]

        if split == '-t' or split == '-type':

            allowed_types = ['track', 'playlist', 'album', 'artist']
            passed_types = []
            for i in range(index+1, len(splits)):
                if splits[i][0] == '-':
                    break

                if splits[i] not in allowed_types:
                    raise ValueError('Parameters passed after {} option must be from this list:\n{}'.
                                     format(split, '\n'.join(allowed_types)))

                passed_types.append(splits[i])
            params['type'] = ','.join(passed_types)

    if len(params['type']) == 0:
        params['type'] = 'track,album,artist,playlist'

    # Clean search term   # Chinono: I'm not sure what this does, so Im leaving it here for now
    search_term_list = []
    for split in splits:
        if split[0] == "-":
            break
        search_term_list.append(split)
    if not search_term_list:
        raise ValueError("Invalid query.")
    params["q"] = ' '.join(search_term_list)

    """ Returns search results from Spotify API """
    # It just prints all the data for now, I will implement a way to return the data later
    resp = Chinofy.invoke_url_with_params(SEARCH_URL, **params)

    counter = 1
    dics = []

    """ Tracks section """
    total_tracks = 0
    if 'track' in params['type'].split(','):
        tracks = resp['tracks']['items']
        if len(tracks) > 0:
            print('###  TRACKS  ###')
            track_data = []
            for track in tracks:
                if track['explicit']:
                    explicit = '[E]'
                else:
                    explicit = ''

                track_data.append([counter, f'{track['name']} {explicit}',
                                  ','.join([artist['name'] for artist in track['artists']])])
                dics.append({
                    'id': track['id'],
                    'name': track['name'],
                    'type': 'track',
                })

                counter += 1
            total_tracks = counter - 1
            print(track_data)
            del tracks
            del track_data

    """ Albums section """
    total_albums = 0
    if 'album' in params['type'].split(','):
        albums = resp['albums']['items']
        if len(albums) > 0:
            print('###  ALBUMS  ###')
            album_data = []
            for album in albums:
                album_data.append([counter, album['name'],
                                  ','.join([artist['name'] for artist in album['artists']])])
                dics.append({
                    'id': album['id'],
                    'name': album['name'],
                    'type': 'album',
                })

                counter += 1
            total_albums = counter - total_tracks - 1
            print(album_data)
            del albums
            del album_data

    """ Artist section """
    total_artists = 0
    if 'artist' in params['type'].split(','):
        artists = resp['artists']['items']
        if len(artists) > 0:
            print('###  ARTISTS  ###')
            artist_data = []
            for artist in artists:
                artist_data.append([counter, artist['name']])
                dics.append({
                    'id': artist['id'],
                    'name': artist['name'],
                    'type': 'artist',
                })
                counter += 1
            total_artists = counter - total_tracks - total_albums - 1
            print(artist_data)
            del artists
            del artist_data

    """ Playlist section """
    total_playlists = 0
    if 'playlist' in params['type'].split(','):
        playlists = resp['playlists']['items']
        if len(playlists) > 0:
            print('###  PLAYLISTS  ###')
            playlist_data = []
            for playlist in playlists:
                playlist_data.append(
                    [counter, playlist['name'], playlist['owner']['display_name']])
                dics.append({
                    'id': playlist['id'],
                    'name': playlist['name'],
                    'type': 'playlist',
                })
                counter += 1
            total_playlists = counter - total_artists - total_tracks - total_albums - 1
            print(playlist_data)
            del playlists
            del playlist_data

    if total_tracks + total_albums + total_artists + total_playlists == 0:
        print('NO RESULTS FOUND - EXITING...')
        return
    

# I really have no idea why the args is here, but Im not touching it for now
Chinofy(args=None)
search("pikasonic") # Testing the function




def fix_filename(name):
    """
    Replace invalid characters on Linux/Windows/MacOS with underscores.
    List from https://stackoverflow.com/a/31976060/819417
    Trailing spaces & periods are ignored on Windows.
    >>> fix_filename("  COM1  ")
    '_ COM1 _'
    >>> fix_filename("COM10")
    'COM10'
    >>> fix_filename("COM1,")
    'COM1,'
    >>> fix_filename("COM1.txt")
    '_.txt'
    >>> all('_' == fix_filename(chr(i)) for i in list(range(32)))
    True
    """
    if platform.system() == 'Windows':
        return re.sub(r'[/\\:|<>"?*\0-\x1f]|^(AUX|COM[1-9]|CON|LPT[1-9]|NUL|PRN)(?![^.])|^\s|[\s.]$', "_", str(name), flags=re.IGNORECASE)
    elif platform.system() == 'Linux':
        return re.sub(r'[/\0]', "_", str(name))
    else: # MacOS
        return re.sub(r'[/:\0]', "_", str(name))








def get_song_info(song_id) -> Tuple[List[str], List[Any], str, str, Any, Any, Any, Any, Any, Any, int]: # Chinono: WTF is this long list of Any XDD
    """ Retrieves metadata for downloaded songs """
    print("Fetching track information...")
    (raw, info) = Chinofy.invoke_url(f'{TRACKS_URL}?ids={song_id}&market=from_token')

    if not 'tracks' in info:
        raise ValueError(f'Invalid response from TRACKS_URL:\n{raw}')

    try:
        artists = []
        for data in info['tracks'][0]['artists']:
            artists.append(data['name'])

        album_name = info['tracks'][0]['album']['name']
        name = info['tracks'][0]['name']
        release_year = info['tracks'][0]['album']['release_date'].split('-')[0]
        disc_number = info['tracks'][0]['disc_number']
        track_number = info['tracks'][0]['track_number']
        scraped_song_id = info['tracks'][0]['id']
        is_playable = info['tracks'][0]['is_playable']
        duration_ms = info['tracks'][0]['duration_ms']

        image = info['tracks'][0]['album']['images'][0]
        for i in info['tracks'][0]['album']['images']:
            if i['width'] > image['width']:
                image = i
        image_url = image['url']

        return artists, info['tracks'][0]['artists'], album_name, name, image_url, release_year, disc_number, track_number, scraped_song_id, is_playable, duration_ms
    except Exception as e:
        raise ValueError(f'Failed to parse TRACKS_URL response: {str(e)}\n{raw}')





def create_download_directory(download_path: str) -> None:
    """ Create directory and add a hidden file with song ids """
    Path(download_path).mkdir(parents=True, exist_ok=True)

    # add hidden file with song ids
    hidden_file_path = PurePath(download_path).joinpath('.song_ids')
    if not Path(hidden_file_path).is_file():
        with open(hidden_file_path, 'w', encoding='utf-8') as f:
            pass


def get_directory_song_ids(download_path: str) -> List[str]:
    """ Gets song ids of songs in directory """

    song_ids = []

    hidden_file_path = PurePath(download_path).joinpath('.song_ids')
    if Path(hidden_file_path).is_file():
        with open(hidden_file_path, 'r', encoding='utf-8') as file:
            song_ids.extend([line.strip().split('\t')[0] for line in file.readlines()])

    return song_ids

def get_song_genres(rawartists: List[str], track_name: str) -> List[str]:
    if CONFIG['MD_SAVE_GENRES']:
        try:
            genres = []
            for data in rawartists:
                # query artist genres via href, which will be the api url
                with print("Fetching artist information..."):
                    (raw, artistInfo) = Chinofy.invoke_url(f'{data['href']}')
                if CONFIG.get_all_genres() and len(artistInfo['genres']) > 0:
                    for genre in artistInfo['genres']:
                        genres.append(genre)
                elif len(artistInfo['genres']) > 0:
                    genres.append(artistInfo['genres'][0])

            if len(genres) == 0:
                print('###    No Genres found for song ' + track_name)
                genres.append('')

            return genres
        except Exception as e:
            raise ValueError(f'Failed to parse GENRES response: {str(e)}\n{raw}')
    else:
        return ['']






def get_song_lyrics(song_id: str, file_save: str) -> None:
    raw, lyrics = Chinofy.invoke_url(f'https://spclient.wg.spotify.com/color-lyrics/v2/track/{song_id}')

    if lyrics:
        try:
            formatted_lyrics = lyrics['lyrics']['lines']
        except KeyError:
            raise ValueError(f'Failed to fetch lyrics: {song_id}')
        if(lyrics['lyrics']['syncType'] == "UNSYNCED"):
            with open(file_save, 'w+', encoding='utf-8') as file:
                for line in formatted_lyrics:
                    file.writelines(line['words'] + '\n')
            return
        elif(lyrics['lyrics']['syncType'] == "LINE_SYNCED"):
            with open(file_save, 'w+', encoding='utf-8') as file:
                for line in formatted_lyrics:
                    timestamp = int(line['startTimeMs'])
                    ts_minutes = str(math.floor(timestamp / 60000)).zfill(2)
                    ts_seconds = str(math.floor((timestamp % 60000) / 1000)).zfill(2)
                    ts_millis = str(math.floor(timestamp % 1000))[:2].zfill(2)
                    file.writelines(f'[{ts_minutes}:{ts_seconds}.{ts_millis}]' + line['words'] + '\n')
            return
    raise ValueError(f'Failed to fetch lyrics: {song_id}')




def add_to_archive(song_id: str, filename: str, author_name: str, song_name: str) -> None:
    """ Adds song id to all time installed songs archive """

    archive_path = CONFIG['SONG_ARCHIVE']

    if Path(archive_path).exists():
        with open(archive_path, 'a', encoding='utf-8') as file:
            file.write(f'{song_id}\t{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\t{author_name}\t{song_name}\t{filename}\n')
    else:
        with open(archive_path, 'w', encoding='utf-8') as file:
            file.write(f'{song_id}\t{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\t{author_name}\t{song_name}\t{filename}\n')


def add_to_directory_song_ids(download_path: str, song_id: str, filename: str, author_name: str, song_name: str) -> None:
    """ Appends song_id to .song_ids file in directory """

    hidden_file_path = PurePath(download_path).joinpath('.song_ids')
    # not checking if file exists because we need an exception
    # to be raised if something is wrong
    with open(hidden_file_path, 'a', encoding='utf-8') as file:
        file.write(f'{song_id}\t{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\t{author_name}\t{song_name}\t{filename}\n')



def set_audio_tags(filename, artists, genres, name, album_name, release_year, disc_number, track_number) -> None:
    """ sets music_tag metadata """
    tags = music_tag.load_file(filename)
    tags['albumartist'] = artists[0]
    tags['artist'] = conv_artist_format(artists)
    tags['genre'] = genres[0] if not CONFIG['MD_ALLGENRES'] else CONFIG['MD_GENREDELIMITER'].join(genres)
    tags['tracktitle'] = name
    tags['album'] = album_name
    tags['year'] = release_year
    tags['discnumber'] = disc_number
    tags['tracknumber'] = track_number
    tags.save()


def conv_artist_format(artists) -> str:
    """ Returns converted artist format """
    return ', '.join(artists)

def set_music_thumbnail(filename, image_url) -> None:
    """ Downloads cover artwork """
    img = requests.get(image_url).content
    tags = music_tag.load_file(filename)
    tags['artwork'] = img
    tags.save()





def download_track(mode: str, track_id: str, extra_keys=None, disable_progressbar=False) -> None: # mode can be 'single', 'album', 'playlist', 'liked', 'extplaylist, Im not bothering them for now
    """ Downloads raw song audio from Spotify """

    if extra_keys is None:
        extra_keys = {}

    print("Preparing Download...")

    try:
        output_template = '{artist} - {song_name}.{ext}' # Only Single mode, other modes I will try to implement later

        (artists, raw_artists, album_name, name, image_url, release_year, disc_number,
         track_number, scraped_song_id, is_playable, duration_ms) = get_song_info(track_id)

        song_name = fix_filename(artists[0]) + ' - ' + fix_filename(name)

        for k in extra_keys:
            output_template = output_template.replace("{"+k+"}", fix_filename(extra_keys[k]))

        ext = EXT_MAP.get(CONFIG['DOWNLOAD_FORMAT'].lower())

        output_template = output_template.replace("{artist}", fix_filename(artists[0]))
        output_template = output_template.replace("{album}", fix_filename(album_name))
        output_template = output_template.replace("{song_name}", fix_filename(name))
        output_template = output_template.replace("{release_year}", fix_filename(release_year))
        output_template = output_template.replace("{disc_number}", fix_filename(disc_number))
        output_template = output_template.replace("{track_number}", fix_filename(track_number))
        output_template = output_template.replace("{id}", fix_filename(scraped_song_id))
        output_template = output_template.replace("{track_id}", fix_filename(track_id))
        output_template = output_template.replace("{ext}", ext)

        filename = PurePath(CONFIG['ROOT_PATH']).joinpath(output_template)
        filedir = PurePath(filename).parent

        print(filename, filedir)
        filename_temp = filename
        if CONFIG['TEMP_DOWNLOAD_DIR'] != '':
            filename_temp = PurePath(CONFIG['TEMP_DOWNLOAD_DIR']).joinpath(f'zotify_{str(uuid.uuid4())}_{track_id}.{ext}')

        check_name = Path(filename).is_file() and Path(filename).stat().st_size
        check_id = scraped_song_id in get_directory_song_ids(filedir)

        # a song with the same name is installed
        if not check_id and check_name:
            c = len([file for file in Path(filedir).iterdir() if re.search(f'^{filename}_', str(file))]) + 1

            fname = PurePath(PurePath(filename).name).parent
            ext = PurePath(PurePath(filename).name).suffix

            filename = PurePath(filedir).joinpath(f'{fname}_{c}{ext}')

    except Exception as e:
        print('###   SKIPPING SONG - FAILED TO QUERY METADATA   ###')
        print('Track_ID: ' + str(track_id))
        for k in extra_keys:
            print(k + ': ' + str(extra_keys[k]))
        print("\n")
        print(str(e) + "\n")
        print("".join(traceback.TracebackException.from_exception(e).format()) + "\n")

    else:
        try:
            if not is_playable:
                print('\n###   SKIPPING: ' + song_name + ' (SONG IS UNAVAILABLE)   ###' + "\n")
            else:
                if track_id != scraped_song_id:
                    track_id = scraped_song_id
                track = TrackId.from_base62(track_id)
                stream = Chinofy.get_content_stream(track, Chinofy.DOWNLOAD_QUALITY)
                create_download_directory(filedir)
                total_size = stream.input_stream.size


                time_start = time.time()
                downloaded = 0
                with open(filename_temp, 'wb') as file:
                    b = 0
                    while b < 5:
                        data = stream.input_stream.stream().read(CONFIG['CHUNK_SIZE'])
                        file.write(data)
                        downloaded += len(data)
                        b += 1 if data == b'' else 0
                        if CONFIG['DOWNLOAD_REAL_TIME']:
                            delta_real = time.time() - time_start
                            delta_want = (downloaded / total_size) * (duration_ms/1000)
                            if delta_want > delta_real:
                                time.sleep(delta_want - delta_real)

                time_downloaded = time.time()

                genres = get_song_genres(raw_artists, name)

                if(CONFIG['DOWNLOAD_LYRICS']):
                    try:
                        get_song_lyrics(track_id, PurePath(str(filename)[:-3] + "lrc"))
                    except ValueError:
                        print(f"###   Skipping lyrics for {song_name}: lyrics not available   ###")
                convert_audio_format(filename_temp)
                try:
                    set_audio_tags(filename_temp, artists, genres, name, album_name, release_year, disc_number, track_number)
                    set_music_thumbnail(filename_temp, image_url)
                except Exception:
                    print("Unable to write metadata, ensure ffmpeg is installed and added to your PATH.")

                if filename_temp != filename:
                    Path(filename_temp).rename(filename)

                time_finished = time.time()

                print(f'###   Downloaded "{song_name}" to "{Path(filename).relative_to(CONFIG['ROOT_PATH'])}" in {fmt_seconds(time_downloaded - time_start)} (plus {fmt_seconds(time_finished - time_downloaded)} converting)   ###' + "\n")

                # add song id to download directory's .song_ids file
                if not check_id:
                    add_to_directory_song_ids(filedir, scraped_song_id, PurePath(filename).name, artists[0], name)

                if not CONFIG['BULK_WAIT_TIME']:
                    time.sleep(CONFIG['BULK_WAIT_TIME'])
        except Exception as e:
            print('###   SKIPPING: ' + song_name + ' (GENERAL DOWNLOAD ERROR)   ###')
            print('Track_ID: ' + str(track_id))
            for k in extra_keys:
                print(k + ': ' + str(extra_keys[k]))
            print("\n")
            print(str(e) + "\n")
            print("".join(traceback.TracebackException.from_exception(e).format()) + "\n")
            if Path(filename_temp).exists():
                Path(filename_temp).unlink()


def convert_audio_format(filename) -> None:
    """ Converts raw audio into playable file """
    temp_filename = f'{PurePath(filename).parent}.tmp'
    Path(filename).replace(temp_filename)

    download_format = CONFIG['DOWNLOAD_FORMAT'].lower()
    file_codec = CODEC_MAP.get(download_format, 'copy')
    if file_codec != 'copy':
        bitrate = CONFIG['TRANSCODE_BITRATE']
        bitrates = {
            'auto': '320k' if Chinofy.check_premium() else '160k',
            'normal': '96k',
            'high': '160k',
            'very_high': '320k'
        }
        bitrate = bitrates[CONFIG['DOWNLOAD_QUALITY']]
    else:
        bitrate = None

    output_params = ['-c:a', file_codec]
    if bitrate:
        output_params += ['-b:a', bitrate]

    try:
        ff_m = ffmpy.FFmpeg(
            global_options=['-y', '-hide_banner', '-loglevel error'],
            inputs={temp_filename: None},
            outputs={filename: output_params}
        )
        print("Converting file...")
        ff_m.run()

        if Path(temp_filename).exists():
            Path(temp_filename).unlink()

    except ffmpy.FFExecutableNotFoundError:
        print(f'###   SKIPPING {file_codec.upper()} CONVERSION - FFMPEG NOT FOUND   ###')

def fmt_seconds(secs: float) -> str:
    val = math.floor(secs)

    s = math.floor(val % 60)
    val -= s
    val /= 60

    m = math.floor(val % 60)
    val -= m
    val /= 60

    h = math.floor(val)

    if h == 0 and m == 0 and s == 0:
        return "0s"
    elif h == 0 and m == 0:
        return f'{s}s'.zfill(2)
    elif h == 0:
        return f'{m}'.zfill(2) + ':' + f'{s}'.zfill(2)
    else:
        return f'{h}'.zfill(2) + ':' + f'{m}'.zfill(2) + ':' + f'{s}'.zfill(2)
    

download_track('single', '3mdtjsn20feMaoIaiiIw52') # Testing the function
print("done")