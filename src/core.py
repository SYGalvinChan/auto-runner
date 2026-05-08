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


def _w(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


class Command:
    def __init__(self, command: list[str] = [], timeout: float | None = None) -> None:
        self.command = command
        self.timeout = timeout

    def run(self) -> int:
        try:
            result = subprocess.run(self.command, timeout=self.timeout)
            return result.returncode
        except subprocess.TimeoutExpired:
            _w(f"\n{RED}timed out after {self.timeout}s{RESET}\n")
            return -1

    def __str__(self) -> str:
        return shlex.join(self.command)


class GitFileWatcher:
    def __init__(self) -> None:
        self.repo_root: str = self._find_root()
        self._prev_state: dict[str, float] = {}
        self.last_changed: list[str] = []

    def _find_root(self) -> str:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True,
            )
            return result.stdout.strip() if result.returncode == 0 else os.getcwd()
        except FileNotFoundError:
            return os.getcwd()

    def _snapshot(self) -> dict[str, float]:
        try:
            result = subprocess.run(
                ["git", "ls-files"],
                capture_output=True, text=True,
                cwd=self.repo_root,
            )
        except FileNotFoundError:
            return {}
        state: dict[str, float] = {}
        for rel in result.stdout.splitlines():
            path = os.path.join(self.repo_root, rel)
            try:
                state[rel] = os.path.getmtime(path)
            except OSError:
                pass
        return state

    def is_modified(self) -> bool:
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

    def file_count(self) -> int:
        return len(self._prev_state)

    def source_label(self) -> str:
        return "git-tracked"


class FileWatcher:
    def __init__(self, patterns: list[str] = [], src_file: str = "") -> None:
        self.patterns = patterns
        self.src_file = src_file
        self._prev_state: dict[str, float] = {}
        self.last_changed: list[str] = []

    def _get_patterns(self) -> list[str]:
        patterns = list(self.patterns)
        if self.src_file:
            with open(self.src_file) as f:
                patterns += [l for l in f.read().splitlines() if l]
        return patterns

    def is_modified(self) -> bool:
        curr: dict[str, float] = {}
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

    def file_count(self) -> int:
        return len(self._prev_state)

    def source_label(self) -> str:
        return "watched"


class Screen:
    def enter(self) -> None:
        _w(ENTER_ALT + HIDE_CURSOR)

    def exit(self) -> None:
        _w(SHOW_CURSOR + EXIT_ALT)

    def render_header(
        self,
        command_str: str,
        file_count: int,
        source_label: str,
        changed_files: list[str] | None = None,
    ) -> None:
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

    def render_footer(self, exit_code: int, duration: float) -> None:
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
    def __init__(
        self,
        command: Command | None = None,
        file_watcher: GitFileWatcher | FileWatcher | None = None,
        screen: Screen | None = None,
        interval: float = 1,
    ) -> None:
        self.command      = command or Command()
        self.file_watcher = file_watcher or FileWatcher()
        self.screen       = screen
        self.interval     = interval
        self._stopped     = False

    def start(self) -> None:
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

    def _run_once(self) -> None:
        count   = self.file_watcher.file_count()
        label   = self.file_watcher.source_label()
        changed = getattr(self.file_watcher, "last_changed", None)

        if self.screen:
            self.screen.render_header(str(self.command), count, label, changed)

        start     = time.time()
        exit_code = self.command.run()
        duration  = time.time() - start

        if self.screen:
            self.screen.render_footer(exit_code or 0, duration)

    def stop(self) -> None:
        self._stopped = True
