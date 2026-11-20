# Taste Lab — experimental, local music discovery

Taste Lab is a runnable research example built on SpotAPI. It imports your current
library, retrieves potential discoveries, learns from conservative listening
signals, and optionally compares how recordings sound using a pretrained neural
audio model. Personal data stays in a local SQLite file. Spotify requests still
go to Spotify; the first audio run downloads public model weights from Hugging Face.

This is **not proven better than Spotify**. Offline tests establish correctness
and measure recovery of withheld favorites. Whether people prefer its discoveries
requires listening experiments. Scores are ranking heuristics, not enjoyment probabilities.

## Start with your existing library

From a full source checkout of SpotAPI, with Python 3.11 or newer. This
example is not installed by `pip install spotapi`:

```shell
python -m pip install -e . python-dotenv
python -m examples.taste_lab --env-file .env sync
python -m examples.taste_lab --env-file .env refresh
python -m examples.taste_lab recommend --limit 10
```

The environment file must contain `SPOTIFY_COOKIE`. An existing process environment
variable takes precedence. Only online commands need credentials. The default
database is `~/.spotapi/taste-lab.sqlite3`; use `--db PATH` before the command to
choose another profile. Treat this file as private listening data. Delete it to
reset the experiment; no Spotify data is deleted.

`sync` walks nested folders and all pages of liked tracks, saved albums and saved
playlists. Saved playlists include followed and editorial playlists: membership is
weak evidence, not proof that you like every track. Liked songs receive more weight.
Each source is replaced atomically. A failed source retains its previous import;
stale sources are removed only after a successful complete sync. Run it again when
you substantially change your library.

`refresh` starts with eight strongly represented artists, finds five related artists
per seed, and retrieves top tracks plus a bounded album sample. It also samples up
to 50 tracks from one discovered-on playlist per seed to broaden the candidate pool.
This is a limited candidate pool derived from Spotify's artist graph, not an
independent global music index. Increase `--seed-artists` (maximum 30) and
`--neighbors` (maximum 15) for broader coverage. Sparse coverage limits what any ranker can discover. Top-track responses
sometimes supply only the queried artist, so those credits can be incomplete.

## Optional audio analysis

Start with the metadata recommendations above. They require neither audio downloads
nor heavy machine-learning dependencies. Audio analysis is a separate experiment,
not a prerequisite for discovering tracks.

For recordings you have permission to process, prefer the local `audio-import`
workflow below. The alternative `enrich` command automatically searches for
matching recordings and analyzes a temporary 12-second excerpt. It accepts
exact titles and close durations from matching Topic channels, or matching artist
channels after checking YouTube's verification metadata.
It skips conflicting matches, covers, live variants and unrelated uploaders. This
is conservative metadata matching, not an acoustic fingerprint or proof of rights.
An official/Topic label does not establish a license to process a recording.

The automatic adapter uses yt-dlp and a bundled FFmpeg binary. It uses no YouTube
login, never forwards Spotify cookies, and does not bypass restricted recordings.
Audio is removed when analysis finishes; only embeddings, source URL and excerpt
offset remain. Respect the source's terms and recording permissions when using it.
YouTube access can change; failed searches retain metadata recommendations and
existing embeddings. This source is not presented as a licensed-preview service.
Use licensed local recordings below where appropriate.

Each run spreads its budget across library anchors and candidates, with artist
diversity. Cached recordings are skipped so later runs can make progress. Unmatched
recordings are deferred for a day and failed requests for an hour; `--force` retries
them immediately. `--limit` caps attempted recordings, not successful matches.

```shell
python -m pip install -r examples/taste_lab/requirements-audio.txt
python -m examples.taste_lab audio-import recordings.json
python -m examples.taste_lab recommend --dry-run
```

Create a JSON manifest matching imported/retrieved tracks to local recordings:

```json
{
  "https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC": "audio/matching-recording.wav"
}
```

Paths are relative to the manifest. Supply recordings you have permission to
process. Verify the exact version yourself: a live performance, cover or remix
is not interchangeable with the Spotify recording. WAV and FLAC are good starting formats;
other formats depend on your installed libsndfile support.

Include **both library favorites and candidate discoveries**. Audio on only one
side cannot establish similarity. Missing audio falls back to metadata ranking.
Audio import requires no Spotify login and sends no recordings to an external
inference service. It does not copy source recordings into the database.

The optional CPU pipeline loads a pinned CLAP checkpoint, reads up to three
ten-second sections across each recording, mixes channels to mono, resamples to
48 kHz, and stores normalized embeddings with the model revision and file hash.
It checkpoints each completed recording. Rerunning reuses unchanged files; changed
recordings are recomputed. Model downloads and inference take additional time and
disk space. Audio dependencies are deliberately separate from the core library.

The personal learner preserves separate library examples instead of averaging all
your tastes into one vector. Nearby examples establish audio affinity; a regularized
kernel model generalizes positive and negative feedback to similar sounds. This is
a small learner over pretrained neural representations, not a neural network trained
from scratch on your listening history. Different model versions/dimensions cannot
be mixed silently.

## Teach it without changing Spotify

```shell
python -m examples.taste_lab feedback TRACK_URL like
python -m examples.taste_lab feedback TRACK_URL dislike
python -m examples.taste_lab --env-file .env observe
```

Explicit feedback is local. A like becomes another retrieval anchor; a dislike
blocks that recording. Removing a saved song is not classified as disliking it.
`observe` watches an existing Spotify player and sends no playback commands. Ctrl+C
stops it. It observes new activity rather than importing weeks of historical behavior.

Completion is weak positive evidence, requiring observed playback across most of
the track. An early transition is weak negative evidence because it may be a queue
change, not an intentional skip. Pauses, device switches, seeks and connection gaps
are neutral interruptions. Repeats count as exposure, not proof of intentional replay.
Feedback IDs prevent a retried observation from being counted twice.

## Familiarity, discovery and repetition

```shell
python -m examples.taste_lab recommend --novelty 0.6 --cooldown-hours 72
```

Ranking combines relevance, a configurable novelty target, feedback, a modest
smaller-artist bonus when audience size is known, and diversity across artists.
The novelty target also reserves part of the slate for unfamiliar artists when
eligible candidates exist; it never bypasses the relevance gate to fill that budget.
Unknown audience size does not count as a small audience. The initial smaller-artist
threshold is 250,000 monthly listeners; this is a product heuristic, not a scientific
definition. Repeated impressions are suppressed for 48 hours by default. Displaying
a recommendation does not count as listening. Actual observed exposure affects
familiarity/fatigue separately. `--dry-run` leaves impression history unchanged.

These are adjustable starting policies. Neuroscience does not establish one ideal
novelty setting, replay count, or cooldown for everyone. Audio cosine distance is
not musical complexity, and the system does not claim to measure neural surprise.
Research motivates testing familiarity and novelty together; it does not validate
these numerical weights. See [repeated listening and complexity](https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2017.00147/full)
and [uncertainty, surprise and musical pleasure](https://pubmed.ncbi.nlm.nih.gov/31708393/).

## Test quickly, then test enjoyment

```shell
python -m pytest tests/test_taste_lab.py tests/test_taste_audio.py
python -m examples.taste_lab.smoke_audio
python -m examples.taste_lab --env-file .env evaluate
python -m examples.taste_lab evaluate --cached
```

The fast tests use synthetic vectors/events to verify learning mechanics, isolation,
cooldowns and interruption handling. The optional smoke command runs the real neural
model on generated tones; it verifies decoding, resampling and repeatable inference,
**not recommendation quality**.

`evaluate` holds out artists and removes collaboration overlap, then retrieves a
fresh pool using only training artists. Withheld tracks are never injected into
the pool. It saves that isolated benchmark locally. Subsequent `evaluate --cached`
runs require no login or network and reuse the same partitions and candidates,
so ranking changes can be compared without changes in retrieval confounding them.
The production recommendation cache is separate. It reports retrieval recall separately from ranking hits, alongside
popularity and seeded-random baselines. If both training and candidate recordings
have audio, it also reports audio-assisted hits and audio coverage. Audio encodings
can be precomputed without using preference labels. Held-out library membership
never enters the audio learner. Baselines use the same pool but do not apply the
ranker's artist-diversity constraint; interpret differences accordingly.
Sparse or selectively acquired audio coverage can bias a comparison; this initial
coverage is a diagnostic, not a controlled audio-quality benchmark.

Missing candidate positives produce unavailable conditional ranking recall rather
than an invented success. Unobserved songs are unlabeled, not assumed disliked.
Recovering familiar favorites is a useful diagnostic but does not prove that new
discoveries are enjoyable. Evaluate multiple profiles and splits before generalizing.

For the next useful experiment, keep a fixed pool, compare `recommend --metadata-only
--dry-run` with audio-assisted `recommend --dry-run`, hide which method produced each
track, and rate short listening sessions. Measure explicit preference, saves,
artist discovery and later voluntary returns—not just uninterrupted playtime.
Record every shown track, avoid calling unplayed tracks dislikes, and keep training
feedback separate from later evaluation. A small blinded pilot can reveal obvious
failures today; sustained enjoyment still needs real use over time.

CLAP implementation reference: [Transformers CLAP documentation](https://huggingface.co/docs/transformers/model_doc/clap).
This example changes no public SpotAPI API and is not included in its wheel.
