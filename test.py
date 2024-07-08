import sys
from asyncio import Lock

from spotify.data.data import Config
from spotify.login import Login
from spotify.playlist import PrivatePlaylist, PublicPlaylist
from spotify.solvers import solver_clients
from spotify.song import Song
from spotify.user import User
from spotify.utils.logger import Logger
from spotify.utils.saver import JSONSaver

login = Login(
    cfg=Config(
        logger=Logger(),
        solver=solver_clients.Capsolver(
            "CAP-CD143A2A67149C5C67022C08A32769B2",
        ),
    ),
    password="adgaaadgagd@gmail.com",
    username="adgaaadgagd@gmail.com",
)
login.login()
# login = Login.from_cookies(JSONSaver().load({"identifier": "adgaaadgagd@gmail.com"}),
#     cfg=Config(
#         logger=Logger(),
#         solver=solver_clients.Capsolver(
#             "CAP-CD143A2A67149C5C67022C08A32769B2",
#         ),
#     ),
# )


a = PublicPlaylist("6xe4HqyIkcSYv3wOHb2mry")
print(Song(a).query_songs("Gay"))
