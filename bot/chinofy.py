""" This is a modified version of the original Zotify codebase.
I modified it so that it can be used as a library for the discord bot.
Functions that are not needed are removed.
Original codebase can be found here:
https://github.com/zotify-dev/zotify """


# For now Im just pasting all code into one single giant file, I will split it up later

from librespot.core import Session
from librespot.audio.decoders import VorbisOnlyAudioQuality
import requests
import json
import time
import re
import platform
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


root_path = Path('.').absolute() / 'output' / 'vc_songs' / 'OGG 320' / id

# Im renaming the class from Zotify to Chinofy because why not XD
class Chinofy:    
    SESSION: Session = None
    DOWNLOAD_QUALITY = None

    def __init__(self, args):
        Chinofy.login(args)

    @classmethod
    def login(cls, args):
        """ Authenticates with Spotify and saves credentials to a file """

        user_name = "" # spotify username and password
        password = ""
        conf = Session.Configuration.Builder().set_store_credentials(False).build()
        cls.SESSION = Session.Builder(conf).user_pass(user_name, password).create()
        print("hi")

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
            if tryCount < (cls.CONFIG.get_retry_attempts() - 1):
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

        # ext = EXT_MAP.get(Zotify.CONFIG.get_download_format().lower())
        ext = 'ogg' # Chinono: I will just hardcode this for now   # copilot knows exactly what Im going to write XDDDD

        output_template = output_template.replace("{artist}", fix_filename(artists[0]))
        output_template = output_template.replace("{album}", fix_filename(album_name))
        output_template = output_template.replace("{song_name}", fix_filename(name))
        output_template = output_template.replace("{release_year}", fix_filename(release_year))
        output_template = output_template.replace("{disc_number}", fix_filename(disc_number))
        output_template = output_template.replace("{track_number}", fix_filename(track_number))
        output_template = output_template.replace("{id}", fix_filename(scraped_song_id))
        output_template = output_template.replace("{track_id}", fix_filename(track_id))
        output_template = output_template.replace("{ext}", ext)

        filename = PurePath(root_path).joinpath(output_template)
        filedir = PurePath(filename).parent

        filename_temp = filename
        if Zotify.CONFIG.get_temp_download_dir() != '':
            filename_temp = PurePath(Zotify.CONFIG.get_temp_download_dir()).joinpath(f'zotify_{str(uuid.uuid4())}_{track_id}.{ext}')

        check_name = Path(filename).is_file() and Path(filename).stat().st_size
        check_id = scraped_song_id in get_directory_song_ids(filedir)
        check_all_time = scraped_song_id in get_previously_downloaded()

        # a song with the same name is installed
        if not check_id and check_name:
            c = len([file for file in Path(filedir).iterdir() if re.search(f'^{filename}_', str(file))]) + 1

            fname = PurePath(PurePath(filename).name).parent
            ext = PurePath(PurePath(filename).name).suffix

            filename = PurePath(filedir).joinpath(f'{fname}_{c}{ext}')

    except Exception as e:
        Printer.print(PrintChannel.ERRORS, '###   SKIPPING SONG - FAILED TO QUERY METADATA   ###')
        Printer.print(PrintChannel.ERRORS, 'Track_ID: ' + str(track_id))
        for k in extra_keys:
            Printer.print(PrintChannel.ERRORS, k + ': ' + str(extra_keys[k]))
        Printer.print(PrintChannel.ERRORS, "\n")
        Printer.print(PrintChannel.ERRORS, str(e) + "\n")
        Printer.print(PrintChannel.ERRORS, "".join(traceback.TracebackException.from_exception(e).format()) + "\n")

    else:
        try:
            if not is_playable:
                prepare_download_loader.stop()
                Printer.print(PrintChannel.SKIPS, '\n###   SKIPPING: ' + song_name + ' (SONG IS UNAVAILABLE)   ###' + "\n")
            else:
                if check_id and check_name and Zotify.CONFIG.get_skip_existing():
                    prepare_download_loader.stop()
                    Printer.print(PrintChannel.SKIPS, '\n###   SKIPPING: ' + song_name + ' (SONG ALREADY EXISTS)   ###' + "\n")

                elif check_all_time and Zotify.CONFIG.get_skip_previously_downloaded():
                    prepare_download_loader.stop()
                    Printer.print(PrintChannel.SKIPS, '\n###   SKIPPING: ' + song_name + ' (SONG ALREADY DOWNLOADED ONCE)   ###' + "\n")

                else:
                    if track_id != scraped_song_id:
                        track_id = scraped_song_id
                    track = TrackId.from_base62(track_id)
                    stream = Zotify.get_content_stream(track, Zotify.DOWNLOAD_QUALITY)
                    create_download_directory(filedir)
                    total_size = stream.input_stream.size

                    prepare_download_loader.stop()

                    time_start = time.time()
                    downloaded = 0
                    with open(filename_temp, 'wb') as file, Printer.progress(
                            desc=song_name,
                            total=total_size,
                            unit='B',
                            unit_scale=True,
                            unit_divisor=1024,
                            disable=disable_progressbar
                    ) as p_bar:
                        b = 0
                        while b < 5:
                        #for _ in range(int(total_size / Zotify.CONFIG.get_chunk_size()) + 2):
                            data = stream.input_stream.stream().read(Zotify.CONFIG.get_chunk_size())
                            p_bar.update(file.write(data))
                            downloaded += len(data)
                            b += 1 if data == b'' else 0
                            if Zotify.CONFIG.get_download_real_time():
                                delta_real = time.time() - time_start
                                delta_want = (downloaded / total_size) * (duration_ms/1000)
                                if delta_want > delta_real:
                                    time.sleep(delta_want - delta_real)

                    time_downloaded = time.time()

                    genres = get_song_genres(raw_artists, name)

                    if(Zotify.CONFIG.get_download_lyrics()):
                        try:
                            get_song_lyrics(track_id, PurePath(str(filename)[:-3] + "lrc"))
                        except ValueError:
                            Printer.print(PrintChannel.SKIPS, f"###   Skipping lyrics for {song_name}: lyrics not available   ###")
                    convert_audio_format(filename_temp)
                    try:
                        set_audio_tags(filename_temp, artists, genres, name, album_name, release_year, disc_number, track_number)
                        set_music_thumbnail(filename_temp, image_url)
                    except Exception:
                        Printer.print(PrintChannel.ERRORS, "Unable to write metadata, ensure ffmpeg is installed and added to your PATH.")

                    if filename_temp != filename:
                        Path(filename_temp).rename(filename)

                    time_finished = time.time()

                    Printer.print(PrintChannel.DOWNLOADS, f'###   Downloaded "{song_name}" to "{Path(filename).relative_to(Zotify.CONFIG.get_root_path())}" in {fmt_seconds(time_downloaded - time_start)} (plus {fmt_seconds(time_finished - time_downloaded)} converting)   ###' + "\n")

                    # add song id to archive file
                    if Zotify.CONFIG.get_skip_previously_downloaded():
                        add_to_archive(scraped_song_id, PurePath(filename).name, artists[0], name)
                    # add song id to download directory's .song_ids file
                    if not check_id:
                        add_to_directory_song_ids(filedir, scraped_song_id, PurePath(filename).name, artists[0], name)

                    if not Zotify.CONFIG.get_bulk_wait_time():
                        time.sleep(Zotify.CONFIG.get_bulk_wait_time())
        except Exception as e:
            Printer.print(PrintChannel.ERRORS, '###   SKIPPING: ' + song_name + ' (GENERAL DOWNLOAD ERROR)   ###')
            Printer.print(PrintChannel.ERRORS, 'Track_ID: ' + str(track_id))
            for k in extra_keys:
                Printer.print(PrintChannel.ERRORS, k + ': ' + str(extra_keys[k]))
            Printer.print(PrintChannel.ERRORS, "\n")
            Printer.print(PrintChannel.ERRORS, str(e) + "\n")
            Printer.print(PrintChannel.ERRORS, "".join(traceback.TracebackException.from_exception(e).format()) + "\n")
            if Path(filename_temp).exists():
                Path(filename_temp).unlink()

    prepare_download_loader.stop()


def convert_audio_format(filename) -> None:
    """ Converts raw audio into playable file """
    temp_filename = f'{PurePath(filename).parent}.tmp'
    Path(filename).replace(temp_filename)

    download_format = Zotify.CONFIG.get_download_format().lower()
    file_codec = CODEC_MAP.get(download_format, 'copy')
    if file_codec != 'copy':
        bitrate = Zotify.CONFIG.get_transcode_bitrate()
        bitrates = {
            'auto': '320k' if Zotify.check_premium() else '160k',
            'normal': '96k',
            'high': '160k',
            'very_high': '320k'
        }
        bitrate = bitrates[Zotify.CONFIG.get_download_quality()]
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
        with Loader(PrintChannel.PROGRESS_INFO, "Converting file..."):
            ff_m.run()

        if Path(temp_filename).exists():
            Path(temp_filename).unlink()

    except ffmpy.FFExecutableNotFoundError:
        Printer.print(PrintChannel.WARNINGS, f'###   SKIPPING {file_codec.upper()} CONVERSION - FFMPEG NOT FOUND   ###')