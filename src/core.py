import os
import sys
import subprocess
import time
import glob
import shlex
from datetime import datetime

_E = "\033["
ENTER_ALT   = _E + "?1049h"
EXIT_ALT    = _E + "?1049l"
CLEAR       = _E + "2J" + _E + "H"
HIDE_CURSOR = _E + "?25l"
SHOW_CURSOR = _E + "?25h"
BOLD        = _E + "1m"
DIM         = _E + "2m"
RESET       = _E + "0m"
GREEN       = _E + "32m"
RED         = _E + "31m"
CYAN        = _E + "36m"


def _w(text):
    sys.stdout.write(text)
    sys.stdout.flush()


class Command:
    def __init__(self, command=[], timeout=None):
        self.command = command
        self.timeout = timeout

    def run(self, stdout=None, stderr=None):
        try:
            result = subprocess.run(
                self.command,
                stdout=stdout,
                stderr=stderr,
                timeout=self.timeout,
            )
            return result.returncode
        except subprocess.TimeoutExpired:
            _w(f"\n{RED}timed out after {self.timeout}s{RESET}\n")
            return -1

    def __str__(self):
        return shlex.join(self.command)


class GitFileWatcher:
    def __init__(self):
        self.repo_root = self._find_root()
        self._prev_state = {}

    def _find_root(self):
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True,
            )
            return result.stdout.strip() if result.returncode == 0 else os.getcwd()
        except FileNotFoundError:
            return os.getcwd()

    def _snapshot(self):
        try:
            result = subprocess.run(
                ["git", "ls-files"],
                capture_output=True, text=True,
                cwd=self.repo_root,
            )
        except FileNotFoundError:
            return {}
        state = {}
        for rel in result.stdout.splitlines():
            path = os.path.join(self.repo_root, rel)
            try:
                state[rel] = os.path.getmtime(path)
            except OSError:
                pass
        return state

    def is_modified(self):
        curr = self._snapshot()
        if not self._prev_state:
            self.last_changed = []
        else:
            self.last_changed = sorted(
                k for k in set(curr) | set(self._prev_state)
                if curr.get(k) != self._prev_state.get(k)
            )
        changed = curr != self._prev_state
        self._prev_state = curr
        return changed

    def file_count(self):
        return len(self._prev_state)

    def source_label(self):
        return "git-tracked"


class FileWatcher:
    def __init__(self, patterns=[], src_file=""):
        self.patterns = patterns
        self.src_file = src_file
        self._prev_state = {}

    def _get_patterns(self):
        patterns = list(self.patterns)
        if self.src_file:
            with open(self.src_file) as f:
                patterns += [l for l in f.read().splitlines() if l]
        return patterns

    def is_modified(self):
        curr = {}
        for pattern in self._get_patterns():
            for path in glob.glob(pattern, recursive=True):
                try:
                    curr[path] = os.path.getmtime(path)
                except OSError:
                    pass
        if not self._prev_state:
            self.last_changed = []
        else:
            self.last_changed = sorted(
                k for k in set(curr) | set(self._prev_state)
                if curr.get(k) != self._prev_state.get(k)
            )
        changed = curr != self._prev_state
        self._prev_state = curr
        return changed

    def file_count(self):
        return len(self._prev_state)

    def source_label(self):
        return "watched"


class Logger:
    def __init__(self, file_name="auto-runner.log", max_backups=10, combine_stderr=True):
        self.file_name = file_name
        self.max_backups = max_backups
        self.combine_stderr = combine_stderr
        self._stdout = None
        self._stderr = None

    def rotate(self):
        self._close()
        exts = ["combined", "stdout", "stderr"]
        for i in range(self.max_backups - 1, 0, -1):
            for e in exts:
                src  = f"{self.file_name}.{e}.{i}"
                dest = f"{self.file_name}.{e}.{i+1}"
                if os.path.exists(dest): os.remove(dest)
                if os.path.exists(src):  os.rename(src, dest)
        for e in exts:
            src  = f"{self.file_name}.{e}"
            dest = f"{self.file_name}.{e}.1"
            if os.path.exists(src):
                if os.path.exists(dest): os.remove(dest)
                os.rename(src, dest)
        if self.combine_stderr:
            combined = open(self.file_name + ".combined", "w")
            self._stdout = combined
            self._stderr = combined
        else:
            self._stdout = open(self.file_name + ".stdout", "w")
            self._stderr = open(self.file_name + ".stderr", "w")

    def get_stdout(self): return self._stdout
    def get_stderr(self): return self._stderr

    def stop(self): self._close()

    def _close(self):
        if self._stdout: self._stdout.close()
        if self._stderr and self._stderr is not self._stdout: self._stderr.close()
        self._stdout = None
        self._stderr = None


class Screen:
    def enter(self):
        _w(ENTER_ALT + HIDE_CURSOR)

    def exit(self):
        _w(SHOW_CURSOR + EXIT_ALT)

    def render_header(self, command_str, file_count, source_label, changed_files=None):
        try:
            cols = os.get_terminal_size().columns
        except OSError:
            cols = 80
        bar = DIM + "─" * cols + RESET
        ts  = datetime.now().strftime("%H:%M:%S")

        changed_line = ""
        if changed_files:
            MAX = 3
            shown = "  ".join(changed_files[:MAX])
            rest  = f"  {DIM}+{len(changed_files) - MAX} more{RESET}" if len(changed_files) > MAX else ""
            changed_line = f"  {DIM}changed:{RESET} {BOLD}{shown}{RESET}{rest}\n"

        _w(
            CLEAR +
            f"{BOLD}{CYAN}auto-runner{RESET}  "
            f"{DIM}{file_count} {source_label}  {ts}{RESET}\n" +
            bar + "\n" +
            f"  {DIM}cmd:{RESET} {command_str}\n" +
            changed_line +
            bar + "\n"
        )

    def render_footer(self, exit_code, duration):
        try:
            cols = os.get_terminal_size().columns
        except OSError:
            cols = 80
        bar   = DIM + "─" * cols + RESET
        color = GREEN if exit_code == 0 else RED
        _w(
            f"\n{bar}\n"
            f"  exit {color}{exit_code}{RESET}  "
            f"{DIM}{duration:.2f}s  watching for changes...  Ctrl+C to stop{RESET}\n"
        )


class Runner:
    def __init__(self,
                 command=None,
                 file_watcher=None,
                 logger=None,
                 screen=None,
                 interval=1):
        self.command      = command or Command()
        self.file_watcher = file_watcher or FileWatcher()
        self.logger       = logger
        self.screen       = screen
        self.interval     = interval
        self._stopped     = False

    def start(self):
        if self.screen:
            self.screen.enter()
        try:
            while not self._stopped:
                if self.file_watcher.is_modified():
                    self._run_once()
                time.sleep(self.interval)
        finally:
            if self.screen:
                self.screen.exit()
            if self.logger:
                self.logger.stop()

    def _run_once(self):
        count = self.file_watcher.file_count()
        label = self.file_watcher.source_label()

        if self.screen:
            changed = getattr(self.file_watcher, "last_changed", None)
            self.screen.render_header(str(self.command), count, label, changed)
            stdout, stderr = None, None
        elif self.logger:
            self.logger.rotate()
            stdout = self.logger.get_stdout()
            stderr = self.logger.get_stderr()
        else:
            stdout, stderr = None, None

        start     = time.time()
        exit_code = self.command.run(stdout=stdout, stderr=stderr)
        duration  = time.time() - start

        if self.screen:
            self.screen.render_footer(exit_code or 0, duration)

    def stop(self):
        self._stopped = True
