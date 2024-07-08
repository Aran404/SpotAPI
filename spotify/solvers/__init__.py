from typing import Dict, Final, Type

# from spotify.solvers.ezcaptcha import *
# from spotify.solvers.rockcaptcha import *
from spotify.data.interfaces import CaptchaProtocol
from spotify.solvers.capsolver import *

# solver_clients: Final[
#     Dict[str, Type[CaptchaProtocol]]
# ] = {"capsolver": Capsolver, "ezcaptcha": EzCaptcha, "rockcaptcha": RockCaptcha}

solver_clients_str: Final[Dict[str, Type[CaptchaProtocol]]] = {"capsolver": Capsolver}


class solver_clients:
    Capsolver: Type[CaptchaProtocol] = Capsolver
