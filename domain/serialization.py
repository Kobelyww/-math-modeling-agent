from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, get_args, get_origin, get_type_hints


def to_json_dict(value: Any) -> Any:
    if is_dataclass(value):
        return {field.name: to_json_dict(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        return [to_json_dict(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_json_dict(item) for key, item in value.items()}
    return value


def from_json_dict(cls: type, payload: Any) -> Any:
    return _convert(cls, payload)


def _convert(annotation: Any, value: Any) -> Any:
    origin = get_origin(annotation)
    args = get_args(annotation)

    if value is None:
        return None

    if origin is list:
        item_type = args[0] if args else Any
        return [_convert(item_type, item) for item in value]

    if origin is dict:
        value_type = args[1] if len(args) == 2 else Any
        return {key: _convert(value_type, item) for key, item in value.items()}

    if origin is not None and type(None) in args:
        real_types = [arg for arg in args if arg is not type(None)]
        return _convert(real_types[0], value) if real_types else value

    if annotation is Path:
        return Path(value)

    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return annotation(value)

    if isinstance(annotation, type) and is_dataclass(annotation):
        hints = get_type_hints(annotation)
        kwargs = {
            field.name: _convert(hints.get(field.name, Any), value.get(field.name))
            for field in fields(annotation)
            if field.name in value
        }
        return annotation(**kwargs)

    return value
