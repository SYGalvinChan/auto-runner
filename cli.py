import argparse

from auto_runner import AutoLogger, AutoRunner

def main():

    descriptor = ("auto-runner is a utility to watch a set of files for changes and run a command automatically when a change is detected.\n"
                  "\n"
                  "Example:\n"
                  "    auto-runner -C text.sh -w src/ tests/\n"
                  "\n"
                  "auto-runner will run ./text.sh everytime a file in src/ or tests/ directory is modified")
    parser = argparse.ArgumentParser(prog="auto-runner",
                                     description=descriptor,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)

    command_group = parser.add_argument_group(title="Command", description="specifies command/file the auto-runner will execute whenever it detects a file is modified")
    command_group = command_group.add_mutually_exclusive_group(required=True)
    command_group.add_argument("-c", "--command", help="command to run automatically")
    command_group.add_argument("-C", "--command-file", help="executable file to run automatically (auto-runner will watch this file for changes)")

    watch_group = parser.add_argument_group(title="Watch", description="specifies the set of files that the auto-runner will watch for changes.")
    watch_group = watch_group.add_mutually_exclusive_group(required=True)
    watch_group.add_argument("-w", "--watch", nargs='*', help="files to watch for changes (space seperated)")
    watch_group.add_argument("-W", "--watch-file", help="text file containing files to watch (auto-runner will watch this file for changes)")

    logging_group = parser.add_argument_group(title="Logging", description="specifies logging behavior")
    logging_group.add_argument("--dir", help="auto-runner will write the outputs of commands to this directory")
    logging_group.add_argument("--max-backups", help="auto-runner will keep MAX_BACKUPS number of logs and delete old logs")
    args = parser.parse_args()

    patterns_watched = []
    if args.command:
        executable = args.command.split()
    else:
        # todo user validation: file exists, is executable
        executable = [args.command_file]
        patterns_watched.append(args.command_file)

    if args.watch:
        patterns_watched += args.watch
    else:
        # todo user validation: file exists
        patterns_watched.append(args.watch_file)
        with open(args.watch_file, 'r') as watch_file:
            lines = watch_file.readlines()
            patterns_watched += lines

    logger = AutoLogger(logs_dir=args.dir,
                        max_backups=args.max_backups)
    runner = AutoRunner(executable=executable,
                        patterns_watched=patterns_watched,
                        logger=logger)
    try:
        runner.start()
    except KeyboardInterrupt:
        runner.stop()

if __name__ == "__main__":
    main()

