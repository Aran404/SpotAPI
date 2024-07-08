import sys
from asyncio import Lock

from spotify import Artist
from spotify.data import Config
from spotify.http.request import TLSClient
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

# r = 0
# a = PublicPlaylist("6xe4HqyIkcSYv3wOHb2mry")
# c = Song(a).paginate_songs("Gay")
# for i in c:
#     for b in i:
#         print(b["item"]["data"]["name"])
#         r += 1

# print(r)

r = 0
c = Artist(login).paginate_artists("Drake")
for i in c:
    for b in i:
        print(b["data"]["profile"]["name"])
        r += 1
