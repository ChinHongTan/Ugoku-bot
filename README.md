## Features

- Download stickers from LINE.
- Download songs, albums or playlists from Deezer (with a Deezer or Spotify link).
- Play songs in vc, with the **best possible audio quality**.
  - Bypasses the channel's audio bitrate.
  - Audio taken from lossless files, then converted to Opus 510kbps.
- Play songs/videos in vc from Youtube, with standard audio quality.
- Set default file format/bitrate (Available: FLAC, MP3 320 or MP3 128).
- Chat (using GPT-4o)

## To do:

- Finish the music player:
  - Add the possibility to add an entire album in queue (/vc play).
  - Add the possibility to play any uploaded file (for Yuuka-chan ~)
  - Optimize Zotify integration (pretty slow to add songs when they're from Spotify)
  - Do not download all the playlist before playing the first song
  - ..
- Improve queue design.
- Add download modes (eg. upload songs one by one for albums/playlists).
- Add the ability to /vc play an entire playlist/album at once.

## Known bugs:

- Clips at default volume (because of the lack of volume control with opus format).

Most of the code of the player comes from [this github gist](https://gist.github.com/aliencaocao/83690711ef4b6cec600f9a0d81f710e5) !
