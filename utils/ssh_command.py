import shlex


def split_ssh_args(args: str | None) -> list[str]:
    """Split SSH argument text while preserving quoted values."""
    if not args:
        return []
    try:
        lexer = shlex.shlex(args, posix=True)
        lexer.whitespace_split = True
        lexer.escape = ""
        return list(lexer)
    except ValueError:
        return args.split()


def join_ssh_command(parts: list[str]) -> str:
    """Return a shell-readable SSH command string from structured parts."""
    return shlex.join(parts)
