from typing import Dict, Final, Type
from spotify.solvers.capsolver import *

# from spotify.solvers.ezcaptcha import *
# from spotify.solvers.rockcaptcha import *
from spotify.interfaces import CaptchaProtocol

# solver_clients: Final[
#     Dict[str, Type[CaptchaProtocol]]
# ] = {"capsolver": Capsolver, "ezcaptcha": EzCaptcha, "rockcaptcha": RockCaptcha}

solver_clients_str: Final[Dict[str, Type[CaptchaProtocol]]] = {"capsolver": Capsolver}


class solver_clients:
    Capsolver: Type[CaptchaProtocol] = Capsolver
