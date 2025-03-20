## Installation

```
pip install spotapi
```

## Quick Examples

### With User Authentication

```py
from spotapi import (
    Login,
    Config,
    NoopLogger,
    solver_clients,
    PrivatePlaylist,
    MongoSaver
)

cfg = Config(
    solver=solver_clients.Capsolver("YOUR_API_KEY", proxy="YOUR_PROXY"), # Proxy is optional
    logger=NoopLogger(),
    # You can add a proxy by passing a custom TLSClient
)

instance = Login(cfg, "YOUR_PASSWORD", email="YOUR_EMAIL")
# Now we have a valid Login instance to pass around
instance.login()

# Do whatever you want now
playlist = PrivatePlaylist(instance)
playlist.create_playlist("SpotAPI Showcase!")

# Save the session
instance.save(MongoSaver())
```

### Without User Authentication

```py
"""Here's the example from spotipy https://github.com/spotipy-dev/spotipy?tab=readme-ov-file#quick-start"""
from spotapi import Song

song = Song()
gen = song.paginate_songs("weezer")

# Paginates 100 songs at a time till there's no more
for batch in gen:
    for idx, item in enumerate(batch):
        print(idx, item['item']['data']['name'])

# ^ ONLY 6 LINES OF CODE

# Alternatively, you can query a specfic amount
songs = song.query_songs("weezer", limit=20)
data = songs["data"]["searchV2"]["tracksV2"]["items"]
for idx, item in enumerate(data):
    print(idx, item['item']['data']['name'])
```

### Results

```
0 Island In The Sun
1 Say It Ain't So
2 Buddy Holly
.
.
.
18 Holiday
19 We Are All On d***s
```
