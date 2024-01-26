from typing import Optional

from github import Github, UnknownObjectException
from github.Repository import Repository


def get_repository(
    gh: Github, repository_name: str, repository_owner_login: str = None
) -> Optional[Repository]:
    """
    Try to get repository by name. If repository not found, try to get repository by owner and name.
    If repository not found by owner and name, return None.
    """
    try:
        return gh.get_repo(repository_name)
    except UnknownObjectException:
        if repository_owner_login:
            return get_repository(gh, f"{repository_owner_login}/{repository_name}")
        return None
