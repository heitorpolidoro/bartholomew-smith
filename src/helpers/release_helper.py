from github import UnknownObjectException
from github.Repository import Repository

RELATIVE_RELEASE = {"major": 0, "minor": 1, "patch": 2, "bugfix": 2}


def is_relative_release(version_to_release: str) -> bool:
    """
    Check if the version to release is a relative release, i.e. 'major', 'minor' etc.
    :param version_to_release: Version to check if is a relative release
    """
    return version_to_release in RELATIVE_RELEASE


def is_valid_release(version_to_release: str) -> bool:
    """
    Check if is a valid release
    :param version_to_release: Version to check if is a valid release
    """
    return bool(version_to_release) and all(map(lambda x: x.isdigit(), version_to_release.split(".")))


def get_absolute_release(last_release: str, relative_version: str) -> str:
    """
    Return the absolute release from the last release and the relative version
    :param last_release: The last release
    :param relative_version: The relative release
    :return: The absolute release
    """
    last_release_split = last_release.split(".")
    new_release = []
    relative_version_index = RELATIVE_RELEASE[relative_version]

    for i in range(relative_version_index + 1):
        if i < len(last_release_split):
            version = last_release_split[i]
        else:
            version = "0"

        if i == relative_version_index:
            new_release.append(str(int(version) + 1))
        else:
            new_release.append(version)

    while len(new_release) < len(last_release_split):
        new_release.append("0")
    return ".".join(new_release)


def get_last_release(repository: Repository) -> str:
    """
    Return the latest release from the repository, if exists
    :param repository:
    :return:
    """
    try:
        return repository.get_latest_release().tag_name
    except UnknownObjectException:
        return "0"
