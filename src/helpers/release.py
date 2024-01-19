from github import UnknownObjectException

RELATIVE_RELEASE = {"major": 0, "minor": 1, "patch": 2, "bugfix": 2}


def is_relative_release(version_to_release):
    return version_to_release in RELATIVE_RELEASE


def is_valid_release(version_to_release):
    return all(map(lambda x: x.isdigit(), version_to_release.split(".")))


def get_relative_release(last_release, relative_version):
    last_release_split = last_release.split(".")
    new_release = []
    relative_version_index = RELATIVE_RELEASE[relative_version]

    # TODO improv
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


def get_last_release(repository):
    try:
        return repository.get_latest_release()
    except UnknownObjectException:
        return "0"
