from typing import Dict, Final, Type

from spotapi.types.interfaces import CaptchaProtocol
from spotapi.solvers.capmonster import *
from spotapi.solvers.capsolver import *

solver_clients_str: Final[Dict[str, Type[CaptchaProtocol]]] = {
    "capsolver": Capsolver,
    "capmonster": Capmonster,
}


class solver_clients:
    Capsolver: Type[CaptchaProtocol] = Capsolver
    Capmonster: Type[CaptchaProtocol] = Capmonster
