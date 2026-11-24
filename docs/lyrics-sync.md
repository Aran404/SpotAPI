# Sync lyrics for local music

Install the optional media dependency:

```bash
pip install "spotapi[media]"
```

Point SpotAPI at a local MP3 or FLAC file, or a directory:

```bash
spotapi lyrics-sync ./Music
spotapi lyrics-sync ./Music --dry-run
spotapi lyrics-sync ./Music --output ./Lyrics
spotapi lyrics-sync ./Music --embed
```

The command queries [LRCLIB](https://lrclib.net/) using the title, artist, album (when present), and duration from your audio tags. It does not upload audio, require a Spotify account, or use Spotify's lyrics service. Only use lyrics you have permission to store.

Synced lyrics use `.lrc`; unsynced lyrics use `.txt`. Files are saved beside each track unless `--output` is specified, in which case the original relative directory structure is preserved. Existing lyrics are compared before changes; different lyrics require interactive approval. Redirected or noninteractive runs leave existing lyrics unchanged. A synced version never gets replaced by plain text. When upgrading a `.txt` file, its existing contents are retained.

`--embed` writes FLAC lyrics and unsynced MP3 lyrics; synced MP3 lyrics are saved as `.lrc` sidecars instead. The audio is staged before replacing the original. The command skips ambiguous filenames and invalid metadata, does not reorganize your music library, and stops when the provider is unavailable or rate limited.

The original `spotapi lyrics` command continues to read entitled Spotify lyrics for a Spotify track.
