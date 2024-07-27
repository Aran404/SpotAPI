import sys
from asyncio import Lock

from spotify import Artist, Login, PrivatePlaylist, PublicPlaylist, Song, User
from spotify.data import Config
from spotify.http.request import TLSClient
from spotify.solvers import solver_clients
from spotify.utils.logger import Logger
from spotify import Creator
from spotify.utils.saver import JSONSaver

try:
    login = Creator(
        cfg=Config(
            logger=Logger(),
            solver=solver_clients.Capsolver(
                "CAP-CD143A2A67149C5C67022C08A32769B2",
            ),
        ),
        password="adgaaadgaaagd@gmail.com",
        email="adgaaadgaaagd@gmail.com",
    )
    login.register()
except Exception as err:
    print(err)
    print(err.error)
    

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

# try:
#     r = 0
#     c = Artist(login).paginate_artists("Drake")
#     for i in c:
#         for b in i:
#             print(b["item"]["data"]["name"])
#             r += 1

# except Exception as err:
#     print(err.error)
