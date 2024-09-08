from setuptools import setup, find_packages

__description__ = "A sleek API wrapper for Spotify's private API"
__install_require__ = [
    "requests",
    "colorama",
    "Pillow",
    "readerwriterlock",
    "tls_client",
    "typing_extensions",
    "validators",
]
__extras__ = {
    "websocket": ["websockets"],
    "redis": ["redis"],
    "pymongo": ["pymongo"],
}

with open("README.md", "r") as f:
    long_description = f.read()

setup(
    name="spotapi",
    author="Aran",
    description=__description__,
    packages=find_packages(),
    install_requires=__install_require__,
    extras_require=__extras__,
    keywords=[
        "Spotify",
        "API",
        "Spotify API",
        "Spotify Private API",
        "Follow",
        "Like",
        "Creator",
        "Music",
        "Music API",
        "Streaming",
        "Music Data",
        "Track",
        "Playlist",
        "Album",
        "Artist",
        "Music Search",
        "Music Metadata",
        "SpotAPI",
        "Python Spotify Wrapper",
        "Music Automation",
        "Web Scraping",
        "Python Music API",
        "Spotify Integration",
        "Spotify Playlist",
        "Spotify Tracks",
    ],
    long_description=long_description,
    long_description_content_type="text/markdown",
    version="1.1.0",
)
