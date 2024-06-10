"""Module to help with GithubExceptions"""

from github import GithubException


def extract_message_from_error(error: dict[str, str]) -> str:
    """Extract the message from error"""
    if message := error.get("message"):
        return message

    if (field := error.get("field")) and (code := error.get("code")):
        return f"{field} {code}"

    return str(error)


def extract_github_error(exception: GithubException) -> str:
    """'Extract the message from GithubException"""
    data = exception.data
    return extract_message_from_error(data.get("errors")[0])
