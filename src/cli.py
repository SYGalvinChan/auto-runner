import os
import shlex
import argparse

from core import Runner, Logger, Command, FileWatcher

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

    command_group = parser.add_argument_group(title="Command", 
                                              description="specifies command/file the auto-runner will execute whenever it detects a file is modified")
    command_group = command_group.add_mutually_exclusive_group(required=True)
    command_group.add_argument("-c", "--command", 
                               help="command to run automatically")
    command_group.add_argument("-C", "--command-file", 
                               help="executable file to run automatically (auto-runner will watch this file for changes)")

    watch_group = parser.add_argument_group(title="Watch", 
                                            description="specifies the set of files that the auto-runner will watch for changes.")
    watch_group = watch_group.add_mutually_exclusive_group()
    watch_group.add_argument("-w", "--watch", 
                             nargs='*', 
                             help="files to watch for changes (space seperated)")
    watch_group.add_argument("-W", "--watch-file", 
                             help="text file containing files to watch (auto-runner will watch this file for changes)")

    logging_group = parser.add_argument_group(title="Logging", 
                                              description="specifies logging behavior")
    logging_group.add_argument("--combine-stderr", 
                               choices=["true", "false"], 
                               default="true", 
                               help="if true, auto-runner will redirect both stdout and stderr of the command to the same log file")
    logging_group.add_argument("--log-file", 
                               default="auto-runner.log", 
                               help="auto-runner will log the outputs of commands to this file")
    logging_group.add_argument("--max-backups", 
                               default=10, 
                               type=int,
                               help="auto-runner will keep MAX_BACKUPS number of old logs and delete older logs")
    args = parser.parse_args()

    patterns_watched = []
    if args.command:
        executable = shlex.split(args.command)
    else:
        # todo user validation: file exists, is executable
        command_file = args.command_file
        if not os.path.exists(command_file):
            print(f"{command_file} does not exist")
            exit(1)
        if not os.access(command_file, os.X_OK):
            print(f"{command_file} is not an executable")
            exit(1)

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

    combine_stderr = True if args.combine_stderr == "true" else False

    if len(patterns_watched) == 0:
        print("auto-runner not watching any files, exiting")
        exit(1)

    command = Command(command=executable)
    file_watcher = FileWatcher(patterns=patterns_watched)
    logger = Logger(file_name=args.log_file,
                    max_backups=args.max_backups,
                    combine_stderr=combine_stderr)
    runner = Runner(command=command,
                    file_watcher=file_watcher,
                    logger=logger)
    try:
        runner.start()
    except KeyboardInterrupt:
        runner.stop()

if __name__ == "__main__":
    main()

