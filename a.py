from spotify.login import Login
from spotify.data import Config
from spotify.logger import Logger
from spotify.solvers import solver_clients
from spotify.user import User
from spotify.playlist import PublicPlaylist
from spotify.saver import JSONSaver
from asyncio import Lock


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
# print(user.edit_user_info)
# print(PublicPlaylist("37i9dQZF1DWXT8uSSn6PRy").__get_playlist())
print(JSONSaver("test.json").delete({"a": 1}, all_instances=False))