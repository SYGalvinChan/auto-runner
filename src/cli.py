import os
import sys
import shlex
import subprocess
import argparse

from core import Runner, Command, FileWatcher, GitFileWatcher, Screen


def in_git_repo() -> bool:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def main() -> None:
    descriptor = (
        "auto-runner watches files for changes and re-runs a command automatically.\n"
        "\n"
        "By default, when run inside a git repository, auto-runner watches all\n"
        "git-tracked files and displays output on an alternate terminal screen.\n"
        "\n"
        "Examples:\n"
        "    auto-runner -C test.sh\n"
        "    auto-runner -c 'pytest tests/' -w 'src/**' 'tests/**'\n"
        "    auto-runner -c 'make build' --no-screen -o build.log"
    )

    parser = argparse.ArgumentParser(
        prog="auto-runner",
        description=descriptor,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    command_group = parser.add_argument_group(
        title="Command",
        description="command to run when a watched file changes",
    )
    command_group = command_group.add_mutually_exclusive_group(required=True)
    command_group.add_argument("-c", "--command",
                               help="shell command to run")
    command_group.add_argument("-C", "--command-file",
                               help="executable file to run (also watched for changes in non-git mode)")

    watch_group = parser.add_argument_group(
        title="Watch",
        description="files to watch (defaults to all git-tracked files when inside a git repo)",
    )
    watch_group.add_argument("-w", "--watch",
                             nargs="+", action="extend",
                             help="glob patterns to watch (disables git mode)")
    watch_group.add_argument("-W", "--watch-file",
                             help="text file containing glob patterns to watch; the file itself is also watched (disables git mode)")
    watch_group.add_argument("--no-git",
                             action="store_true",
                             help="disable git-aware watching; requires -w or -W")

    display_group = parser.add_argument_group(title="Display")
    display_group.add_argument("--no-screen",
                               action="store_true",
                               help="disable alternate screen; output goes to stdout")

    parser.add_argument("--timeout",
                        type=float, default=None, metavar="SECONDS",
                        help="kill the command after this many seconds")

    args = parser.parse_args()

    # Build executable
    if args.command:
        executable = shlex.split(args.command)
    else:
        command_file = args.command_file
        if not os.path.exists(command_file):
            print(f"error: {command_file} does not exist")
            exit(1)
        if not os.access(command_file, os.X_OK):
            print(f"error: {command_file} is not executable")
            exit(1)
        executable = [os.path.abspath(command_file)]

    # Decide file watcher
    explicit_patterns = bool(args.watch or args.watch_file)
    use_git = not args.no_git and not explicit_patterns and in_git_repo()

    if use_git:
        file_watcher = GitFileWatcher()
    else:
        patterns = list(args.watch or [])
        # in non-git mode, also watch the command file and watch-file itself
        if args.command_file:
            patterns.insert(0, args.command_file)
        if args.watch_file:
            patterns.insert(0, args.watch_file)
        if not patterns and not args.watch_file:
            print("error: not watching any files — use -w, -W, or run inside a git repo")
            exit(1)
        file_watcher = FileWatcher(
            patterns=patterns,
            src_file=args.watch_file or "",
        )

    use_screen = sys.stdout.isatty() and not args.no_screen
    screen     = Screen() if use_screen else None

    command = Command(command=executable, timeout=args.timeout)
    runner  = Runner(
        command=command,
        file_watcher=file_watcher,
        screen=screen,
    )

    try:
        runner.start()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
