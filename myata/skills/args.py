"""Check and clean the arguments an LLM passes to a skill.

The LLM is not trusted: unknown arguments are dropped, types are coerced
when it is safe, and anything else is rejected before the skill runs.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class ArgsError(ValueError):
    """Raised when tool arguments do not match the skill's schema."""


def validate_args(schema: Mapping[str, Any], args: Mapping[str, Any]) -> dict[str, Any]:
    properties: Mapping[str, Any] = schema.get("properties", {})
    result: dict[str, Any] = {}
    for name, value in args.items():
        if name in properties and value is not None:
            result[name] = _coerce(name, properties[name], value)
    missing = [name for name in schema.get("required", []) if result.get(name) in (None, "")]
    if missing:
        raise ArgsError(f"missing required arguments: {', '.join(missing)}")
    return result


def _coerce(name: str, prop: Mapping[str, Any], value: Any) -> Any:
    kind = prop.get("type", "string")
    try:
        if kind == "string":
            if isinstance(value, (dict, list)):
                raise ArgsError(f"{name}: expected a string")
            value = str(value).strip()
        elif kind == "integer":
            value = _to_int(value)
        elif kind == "number":
            if isinstance(value, bool):
                raise ArgsError(f"{name}: expected a number")
            value = float(value)
        elif kind == "boolean":
            value = _to_bool(value)
        else:
            raise ArgsError(f"{name}: unsupported type {kind!r}")
    except (TypeError, ValueError) as e:
        if isinstance(e, ArgsError):
            raise
        raise ArgsError(f"{name}: cannot convert {value!r} to {kind}") from e

    if "enum" in prop and value not in prop["enum"]:
        raise ArgsError(f"{name}: {value!r} is not one of {prop['enum']}")
    if "minimum" in prop and value < prop["minimum"]:
        raise ArgsError(f"{name}: {value} is below {prop['minimum']}")
    if "maximum" in prop and value > prop["maximum"]:
        raise ArgsError(f"{name}: {value} is above {prop['maximum']}")
    return value


def _to_int(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("bool is not an integer")
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError("not a whole number")
        return int(value)
    return int(str(value).strip())


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("true", "1", "yes", "да"):
        return True
    if text in ("false", "0", "no", "нет"):
        return False
    raise ValueError("not a boolean")
