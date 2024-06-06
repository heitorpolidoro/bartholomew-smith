import pytest

from src.helpers.exception_helper import extract_message_from_error


@pytest.mark.parametrize(
    "error_dict,expected_return",
    [
        ({"message": "Error Message"}, "Error Message"),
        ({"field": "Field", "code": "Code"}, "Field Code"),
        ({"data": "any_data"}, "{'data': 'any_data'}")
    ],
)
def test_extract_message_from_error(error_dict, expected_return):
    assert expected_return == extract_message_from_error(error_dict)
