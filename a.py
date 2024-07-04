from spotify.login import Login
from spotify.data import Config
from spotify.logger import Logger
from spotify.solvers import solver_clients
from spotify.user import User
from spotify.playlist import PublicPlaylist


# login = Login(
#     cfg=Config(
#         logger=Logger(),
#         solver=solver_clients.Capsolver(
#             "CAP-394E37F0C75998ED5431B452957E1516",
#         ),
#     ),
#     password="adgaaadgagd@gmail.com",
#     username="adgaaadgagd@gmail.com",
# )
# login.login()

# user = User(login)
# print(user.has_premium)
print(PublicPlaylist("37i9dQZF1DWXT8uSSn6PRy").get_playlist_info())
