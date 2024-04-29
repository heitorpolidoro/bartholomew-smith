import pytest

from src.helpers.command_helper import get_command


@pytest.mark.parametrize(
    "text,expected",
    [
        ("any text", None),
        ("[prefix:simple]", "simple"),
        ("blabla\n[prefix:complex]\nblabla", "complex"),
    ],
)
def test_get_command(text, expected):
    assert get_command(text, "prefix") == expected
