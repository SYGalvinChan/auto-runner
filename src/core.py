import os
import subprocess
import time
import glob
import shlex

class Command:
    def __init__(self,
                 command=[],
                 timeout=5):
        self.command = command
        self.timeout = timeout

    def run(self,
            stdout=None,
            stderr=None):
        try:
            subprocess.run(self.command, 
                           stdout=stdout,
                           stderr=stderr,
                           timeout=self.timeout,
                           check=True)
        except subprocess.CalledProcessError as e:
            print(f"command exited with non-zero code: {e.returncode}")
        except subprocess.TimeoutExpired:
            print(f"command timeout after {self.timeout} seconds")

    def __str__(self) -> str:
        return shlex.join(self.command)

class FileWatcher:
    def __init__(self,
                 patterns=[],
                 src_file=""):
        self.patterns = patterns
        self.src_file = src_file

        self.prev_files_state = {}

    def get_patterns_from_src(self):
        if self.src_file == "":
            return []
        with open(self.src_file) as src:
            patterns = src.read().splitlines()
            patterns = [line for line in patterns if line]
            return patterns

    def is_modified(self):
        patterns = self.get_patterns_from_src()
        patterns += self.patterns

        curr_files_state = {}

        for pattern in patterns:
            paths = glob.glob(pattern, recursive=True)
            for path in paths:
                try:
                    modified_time = os.path.getmtime(path)
                    curr_files_state[path] = modified_time
                except:
                    pass

        if curr_files_state == self.prev_files_state:
            return False
        else:
            self.prev_files_state = curr_files_state
            return True

class Logger:
    def __init__(self,
                 file_name="auto-runner.log",
                 max_backups=0,
                 combine_stderr=True):
        self.file_name = file_name

        self.max_backups = max_backups
        self.combine_stderr = combine_stderr

        self.curr_stdout = None
        self.curr_stderr = None

    def rotate(self):
        self.close_stdout()
        self.close_stderr()

        extensions = ["combined", "stdout", "stderr"]
        for i in range(self.max_backups - 1, 0, -1):
            for e in extensions:
                src = f"{self.file_name}.{e}.{i}"
                dest = f"{self.file_name}.{e}.{i + 1}"

                if os.path.exists(dest):
                    os.remove(dest)
                if os.path.exists(src):
                    os.rename(src, dest)

        for e in extensions:
            src = f"{self.file_name}.{e}"
            dest = f"{self.file_name}.{e}.1"

            if os.path.exists(src):
                if os.path.exists(dest):
                    os.remove(dest)
                os.rename(src, dest)

        if self.combine_stderr:
            combined = open(self.file_name + ".combined", "w")
            self.curr_stdout = combined
            self.curr_stderr = combined
        else:
            self.curr_stdout = open(self.file_name + ".stdout", "w")
            self.curr_stderr = open(self.file_name + ".stderr", "w")

    def get_stdout(self):
        return self.curr_stdout

    def get_stderr(self):
        return self.curr_stderr

    def stop(self):
        self.close_stdout()
        self.close_stderr()

    def close_stdout(self):
        if self.curr_stdout:
            self.curr_stdout.close()
        self.curr_stdout = None

    def close_stderr(self):
        if self.curr_stderr:
            self.curr_stderr.close()

class Runner:
    def __init__(self,
                 command=Command(),
                 file_watcher=FileWatcher(),
                 logger=Logger(),
                 interval=1):
        self.command = command
        self.file_watcher = file_watcher
        self.logger = logger
        self.interval = interval

        self.stopped = False

    def start(self):
        while not self.stopped:
            if self.file_watcher.is_modified():
                print(
                        "=================================================\n"
                        "Auto Runner has detected changes in watched files\n"
                        f"Begin executing {self.command}\n"
                        "================================================="
                        )
                self.logger.rotate()
                self.command.run(self.logger.get_stdout(), self.logger.get_stderr())
            time.sleep(self.interval)
    def stop(self):
        self.stopped = True
        self.logger.stop()

if __name__ == "__main__":
    command = Command(command=["./test.sh"])
    file_watcher = FileWatcher(patterns=["src/", "test/"])
    logger = Logger(file_name="log/auto-runner.log",
                    max_backups=5,
                    combine_stderr=True)
    runner = Runner(command=command,
                    file_watcher=file_watcher,
                    logger=logger)
    try:
        runner.start()
    except KeyboardInterrupt:
        runner.stop()
