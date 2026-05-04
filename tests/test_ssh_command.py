from utils.ssh_command import join_ssh_command, split_ssh_args


def test_split_ssh_args_preserves_quoted_values():
    args = '-o ProxyCommand="ssh -W %h:%p bastion" -i "C:/Users/vital/.ssh/edge key"'

    assert split_ssh_args(args) == [
        "-o",
        "ProxyCommand=ssh -W %h:%p bastion",
        "-i",
        "C:/Users/vital/.ssh/edge key",
    ]


def test_split_ssh_args_preserves_windows_backslash_paths():
    args = r"ssh -i C:\Users\vital\.ssh\edge ratio@192.0.2.10"

    assert split_ssh_args(args) == [
        "ssh",
        "-i",
        r"C:\Users\vital\.ssh\edge",
        "ratio@192.0.2.10",
    ]


def test_split_ssh_args_preserves_quoted_windows_backslash_paths():
    args = r'ssh -i "C:\Users\vital\.ssh\edge key" ratio@192.0.2.10'

    assert split_ssh_args(args) == [
        "ssh",
        "-i",
        r"C:\Users\vital\.ssh\edge key",
        "ratio@192.0.2.10",
    ]


def test_join_ssh_command_round_trips_structured_parts():
    parts = [
        "ssh",
        "-i",
        r"C:\Users\vital\.ssh\edge key",
        "-o",
        "ProxyCommand=ssh -W %h:%p bastion",
        "ratio@192.0.2.10",
    ]

    assert split_ssh_args(join_ssh_command(parts)) == parts


def test_split_ssh_args_does_not_raise_on_malformed_quotes():
    assert split_ssh_args('ssh -i "C:/Users/vital/.ssh/edge key ratio@host') == [
        "ssh",
        "-i",
        '"C:/Users/vital/.ssh/edge',
        "key",
        "ratio@host",
    ]
