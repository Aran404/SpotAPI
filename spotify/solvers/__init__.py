from typing import Dict, Final, Type

from spotify.data.interfaces import CaptchaProtocol
from spotify.solvers.capmonster import *
from spotify.solvers.capsolver import *

solver_clients_str: Final[Dict[str, Type[CaptchaProtocol]]] = {
    "capsolver": Capsolver,
    "capmonster": Capmonster,
}


class solver_clients:
    Capsolver: Type[CaptchaProtocol] = Capsolver
    Capmonster: Type[CaptchaProtocol] = Capmonster
