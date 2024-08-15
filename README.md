# SpotAPI

Welcome to SpotAPI! This Python library is designed to interact with the private and public Spotify APIs, emulating the requests typically made through a web browser. This wrapper provides a convenient way to access Spotify’s rich set of features programmatically.

**Note**: This project is intended solely for educational purposes and should be used responsibly. Accessing private endpoints and scraping data without proper authorization may violate Spotify's terms of service

## Features
- **Public API Access**: Retrieve and manipulate public Spotify data such as playlists, albums, and tracks with ease.
- **Private API Access**: Explore private Spotify endpoints to tailor your application to your needs.
- **Ready to Use**: **SpotAPI** is designed for immediate integration, allowing you to accomplish tasks with just a few lines of code.
- **No API Key Required**: Seamlessly use **SpotAPI** without needing a Spotify API key. It’s straightforward and hassle free!
- **Browser-like Requests**: Accurately replicate the HTTP requests Spotify makes in the browser, providing a true to web experience while remaining undetected.

Everything you can do with Spotify, **SpotAPI** can do with just a user’s login credentials.


## Installation
```
pip install spotapi
```

## Quick Example
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

## Contributing
Contributions are welcome! If you find any issues or have suggestions, please open an issue or submit a pull request.

## License
This project is licensed under the **GPL 3.0** License. See [LICENSE](https://choosealicense.com/licenses/gpl-3.0/) for details.

