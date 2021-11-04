# musicdb2sqlite

Convert Apple's Library.musicdb file to SQLite3 Database for explores data.

## How to use

```
pip3 install -r requirements.txt
./main.py /path/to/your.musiclibrary/Library.musicdb > log.txt
```

then script generates `library.sqlite3`, it should including all tracks/albums/artists information.

## Tasks

- [ ] Track Information
  - [ ] embedded binary things
  - [x] boma UTF-16 strings
  - [ ] other boma things
- [ ] Album Information
  - [ ] embedded binary things
  - [x] boma UTF-16 strings
  - [ ] other boma things
- [ ] Artist Information
  - [ ] embedded binary things
  - [x] boma UTF-16 strings
  - [ ] other boma things
- [ ] Playlist Information

## Special Thanks

- most of MusicDB file format: https://home.vollink.com/gary/playlister/musicdb.html