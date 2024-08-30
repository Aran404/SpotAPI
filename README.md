# Legal Notice

> **Disclaimer**: This repository and any associated code are provided "as is" without warranty of any kind, either expressed or implied. The author of this repository does not accept any responsibility for the use or misuse of this repository or its contents. The author does not endorse any actions or consequences arising from the use of this repository. Any copies, forks, or re-uploads made by other users are not the responsibility of the author. The repository is solely intended as a Proof Of Concept for educational purposes regarding the use of a service's private API. By using this repository, you acknowledge that the author makes no claims about the accuracy, legality, or safety of the code and accepts no liability for any issues that may arise. More information can be found [HERE](./LEGAL_NOTICE.md).

# SpotAPI

Welcome to SpotAPI! This Python library is designed to interact with the private and public Spotify APIs, emulating the requests typically made through a web browser. This wrapper provides a convenient way to access Spotify’s rich set of features programmatically.

**Note**: This project is intended solely for educational purposes and should be used responsibly. Accessing private endpoints and scraping data without proper authorization may violate Spotify's terms of service.

## Table of Contents

1. [Introduction](#spotapi)
2. [Features](#features)
3. [Docs](#docs)
4. [Installation](#installation)
5. [Quick Examples](#quick-examples)
6. [Import Cookies](#import-cookies)
7. [Contributing](#contributing)
8. [Roadmap](#roadmap)
9. [License](#license)


## Features
- **No Premium Required**: Unlike the Web API which requires Spotify Premium, **SpotAPI** requires no Spotify Premium at all!
- **Public API Access**: Retrieve and manipulate public Spotify data such as playlists, albums, and tracks with ease.
- **Private API Access**: Explore private Spotify endpoints to tailor your application to your needs.
- **Ready to Use**: **SpotAPI** is designed for immediate integration, allowing you to accomplish tasks with just a few lines of code.
- **No API Key Required**: Seamlessly use **SpotAPI** without needing a Spotify API key. It’s straightforward and hassle free!
- **Browser-like Requests**: Accurately replicate the HTTP requests Spotify makes in the browser, providing a true to web experience while remaining undetected.

Everything you can do with Spotify, **SpotAPI** can do with just a user’s login credentials.


## Docs
- [**Artist.py**](./docs/artist.md)
- [**Creator.py**](./docs/creator.md)
- [**Family.py**](./docs/family.md)
- [**Login.py**](./docs/login.md)
- [**Password.py**](./docs/password.md)
- [**Player.py**](./docs/player.md)
- [**Song.py**](./docs/song.md)
- [**Playlist.py**](./docs/playlist.md)
- [**Status.py**](./docs/status.md)
- [**User.py**](./docs/user.md)


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

## Import Cookies
If you prefer not to use a third party CAPTCHA solver, you can import cookies to manage your session.

### Steps to Import Cookies:

1. **Choose a Session Saver**:
   - Select a session saver for storing your session data. 
   - For simplicity, you should use `JSONSaver`, especially if performance or quantity of sessions is not a big concern.

2. **Prepare Session Data**:
   - Create an object with the following keys:
     - **`identifier`**: This should be your email address or username.
     - **`cookies`**: These are the cookies you obtain when logged in. To get these cookies, visit [Spotify](https://open.spotify.com/), log in, and copy the cookies from your browser.
       - It can be a dict[str, str] or a string representation

3. **Load the Session**:
   - Use `Login.from_saver` (or your own implementation) to load the session from cache. This will enable you to use Spotify with a fully functional session without needing additional **CAPTCHA solving**.

## Contributing
Contributions are welcome! If you find any issues or have suggestions, please open an issue or submit a pull request.

## Roadmap
> I'll most likely do these if the project gains some traction

- [ ] No Captcha For Login (**100 Stars**)
- [x] In Depth Documentation
- [x] Websocket Listener
- [x] Player
- [ ] More wrappers around this project

## License
This project is licensed under the **GPL 3.0** License. See [LICENSE](https://choosealicense.com/licenses/gpl-3.0/) for details.

