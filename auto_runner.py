import glob
import subprocess
import time
import os

class AutoRunner:
    def __init__(self, 
                 executable, 
                 patterns_watched=None, 
                 interval=1,
                 logger=None):
        self.executable = executable
        self.patterns_watched = patterns_watched if patterns_watched is not None else []
        self.interval = interval
        self.logger = logger if logger is not None else AutoLogger()

        self.prev_files_state = {}

        self.curr_child = None

        self.stopped = False

    def start(self):
        while not self.stopped:
            if self.files_modified():
                print(
                        "=================================================\n"
                        "Auto Runner has detected changes in watched files\n"
                        f"Begin executing {" ".join(self.executable)}\n"
                        "================================================="
                        )
                self.logger.rotate_logs()
                self.run(self.logger.curr_child_stdout, self.logger.curr_child_stderr)
            time.sleep(self.interval)

    def stop(self):
        print("stopping auto runner")
        self.stopped = True
        if self.curr_child:
            self.curr_child.kill()
        self.logger.stop()

    def run(self, stdout, stderr):
        child = subprocess.Popen(self.executable, stdout=stdout, stderr=stderr)
        self.child = child

    def files_modified(self):
        curr_files_state = {}

        for pattern in self.patterns_watched:
            paths = glob.glob(pattern)
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

class AutoLogger:
    def __init__(self,
                 logs_dir="",
                 max_backups=0,
                 ):
        if logs_dir == "":
            self.logs_dir = os.getcwd()
        elif "~" in logs_dir:
            self.logs_dir = os.path.expanduser(logs_dir)
        else:
            self.logs_dir = os.path.abspath(logs_dir)

        self.max_backups = max_backups

        self.curr_child_stdout = None
        self.curr_child_stderr = None

        self.curr_stdout_path = os.path.join(self.logs_dir, "curr_stdout")
        self.curr_stderr_path = os.path.join(self.logs_dir, "curr_stderr")

    def stop(self):
        if self.curr_child_stdout:
            self.curr_child_stdout.close()
        if self.curr_child_stderr:
            self.curr_child_stderr.close()

    def rotate_logs(self):
        self.delete_old_logs()

        if self.curr_child_stdout:
            self.curr_child_stdout.close()
        if self.curr_child_stderr:
            self.curr_child_stderr.close()
        if os.path.exists(self.curr_stdout_path):
            os.unlink(self.curr_stdout_path)
        if os.path.exists(self.curr_stderr_path):
            os.unlink(self.curr_stderr_path)

        curr_time = time.strftime("%H%M%S")

        stdout_path = os.path.join(self.logs_dir, f"{curr_time}_stdout")
        stderr_path = os.path.join(self.logs_dir, f"{curr_time}_stderr")

        stdout = open(stdout_path, 'w')
        stderr = open(stderr_path, 'w')

        os.symlink(stdout_path, self.curr_stdout_path)
        os.symlink(stderr_path, self.curr_stderr_path)

        self.curr_child_stdout = stdout
        self.curr_child_stderr = stderr

        return stdout, stderr

    def delete_old_logs(self):
        pass

if __name__ == '__main__':
    runner = AutoRunner(['ls', 'logs'], ['file1.txt', 'dir/*'], interval=1)
    try:
        runner.start()
    except KeyboardInterrupt:
        runner.stop()
