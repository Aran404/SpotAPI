from .data import Config
from .interfaces import CaptchaProtocol, LoggerProtocol, SaverProtocol
from typing import Any, Dict, Type, Set

class FilterInheritedMeta(type):
    def __new__(
        cls: Type['FilterInheritedMeta'], 
        name: str, 
        bases: tuple, 
        class_dict: Dict[str, Any]
    ) -> Type:
        new_class_dict: Dict[str, Any] = {}
        base_attrs: Set[str] = set()

        for base in bases:
            base_attrs.update(dir(base))
        
        for key, value in class_dict.items():
            if key not in base_attrs:
                new_class_dict[key] = value
        
        return super().__new__(cls, name, bases, new_class_dict)
