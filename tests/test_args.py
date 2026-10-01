import pytest

from myata.skills.args import ArgsError, validate_args

SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "site": {"type": "string", "enum": ["google", "youtube"]},
        "minutes": {"type": "integer", "minimum": 1, "maximum": 600},
        "loud": {"type": "boolean"},
    },
    "required": ["query"],
}


def test_valid_and_coerced():
    args = {"query": " котики ", "minutes": "5", "loud": "true", "hack": "rm -rf /"}
    assert validate_args(SCHEMA, args) == {"query": "котики", "minutes": 5, "loud": True}


def test_missing_required():
    with pytest.raises(ArgsError):
        validate_args(SCHEMA, {"site": "google"})
    with pytest.raises(ArgsError):
        validate_args(SCHEMA, {"query": "   "})


def test_rejects_bad_values():
    for bad in ({"site": "bing"}, {"minutes": 0}, {"minutes": "много"}, {"minutes": True}):
        with pytest.raises(ArgsError):
            validate_args(SCHEMA, {"query": "x", **bad})
