from functools import lru_cache
from typing import Optional

from github import Github, UnknownObjectException
from github.Repository import Repository


@lru_cache
def get_repository(
    gh: Github, repository_name: str, repository_owner_login: str = None
) -> Optional[Repository]:
    """
    Try to get repository by name. If the repository is not found, try to get the repository by owner and name.
    If the repository is not found by owner and name, return None.
    """
    try:
        if repository_owner_login:
            return get_repository(gh, f"{repository_owner_login}/{repository_name}")
        return get_repo_cached(gh, repository_name)
    except UnknownObjectException:
        return None


@lru_cache
def get_repo_cached(gh, repository_name):
    return gh.get_repo(repository_name)
