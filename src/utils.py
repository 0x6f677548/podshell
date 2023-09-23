# Description: Utility functions for the project.


APP_NAME = "podshell"
"""The name of the application."""


def which(program: str, default: str | None = None) -> str | None:
    """Returns the path to a program if it exists in the PATH environment variable.
    Args:
        program: The name of the program to look for.
    Returns:
        The path to the program if it exists, default otherwise.
    """
    import os

    def is_exe(fpath: str) -> bool:
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, _ = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    elif "PATH" in os.environ:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return default
