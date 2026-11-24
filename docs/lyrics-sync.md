# Sync lyrics for local music

Install the optional media dependency:

```bash
pip install "spotapi[media]"
```

Point SpotAPI at a local MP3 or FLAC file, an album directory, or the root of your music library. Directories are scanned recursively by default. Start with a dry run to inspect the proposed changes:

```bash
spotapi lyrics-sync ./Music --dry-run
spotapi lyrics-sync ./Music
spotapi lyrics-sync ./Music --recursive --yes
spotapi lyrics-sync ./Music --no-recursive
spotapi lyrics-sync ./Music --output ./Lyrics
spotapi lyrics-sync ./Music --embed
```

The command queries [LRCLIB](https://lrclib.net/) using the title, artist, album (when present), and duration from your audio tags. It does not upload audio, require a Spotify account, or use Spotify's lyrics service. Only use lyrics you have permission to store.

Synced lyrics use `.lrc`; unsynced lyrics use `.txt`. Files are saved beside each track unless `--output` is specified, in which case the original relative directory structure is preserved. Existing lyrics are compared before changes; different lyrics require interactive approval unless `-y` or `--yes` is supplied. Redirected or noninteractive runs keep existing lyrics unless explicitly approved with `--yes`. Diffs are shown even with `--yes`. `--dry-run` never writes files, including when combined with `--yes`. A synced version never gets replaced by plain text. When upgrading a `.txt` file, its existing contents are retained.

`--embed` writes FLAC lyrics and unsynced MP3 lyrics; synced MP3 lyrics are saved as `.lrc` sidecars instead. The audio is staged before replacing the original. The command skips ambiguous filenames and invalid metadata, does not reorganize your music library, and stops when the provider is unavailable or rate limited. Lookups are intentionally sequential and spaced apart to respect LRCLIB's batch-client guidelines.

`--recursive` explicitly enables the default behavior; `--no-recursive` restricts scanning to the immediate directory. These flags do not change single-file behavior. Each run fetches fresh results from LRCLIB, so provider edits can change the proposed lyrics. `Not found` means no acceptable metadata and duration match was returned, not necessarily that the song has no lyrics.

The original `spotapi lyrics` command continues to read entitled Spotify lyrics for a Spotify track.
