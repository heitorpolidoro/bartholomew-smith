"""Helper to manage commands in texts"""

import re
from typing import Optional


def get_command(text: str, command_prefix: str) -> Optional[str]:
    """
    Retrieve the command from the commit message.
    The command in the commit message must be in the format [command_prefix: command]

    :param text: The Commit object.
    :param command_prefix: The command prefix to look for in the commit message.
    :return: The extracted command or None if there is no command.
    :raises: ValueError if the command is not valid.
    """
    command_pattern = r"\[" + command_prefix + r":(.*?)\]"
    commands_found = re.findall(command_pattern, text)
    if commands_found:
        return commands_found[-1].strip()
    return None
