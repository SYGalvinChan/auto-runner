import os
import time
import pytest
from unittest.mock import Mock, patch

from core import Command, FileWatcher, GitFileWatcher, Runner


# ── Command ───────────────────────────────────────────────────────────────────

class TestCommand:
    def test_success_returns_zero(self):
        assert Command(["true"]).run() == 0

    def test_failure_returns_nonzero(self):
        assert Command(["false"]).run() == 1

    def test_timeout_returns_minus_one(self):
        assert Command(["sleep", "10"], timeout=0.01).run() == -1

    def test_str(self):
        assert str(Command(["make", "build"])) == "make build"

    def test_str_quotes_args_with_spaces(self):
        assert str(Command(["echo", "hello world"])) == "echo 'hello world'"


# ── FileWatcher ───────────────────────────────────────────────────────────────

class TestFileWatcher:
    def test_first_call_true_when_files_exist(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        w = FileWatcher(patterns=[str(tmp_path / "*.py")])
        assert w.is_modified() is True

    def test_first_call_last_changed_is_empty(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        w = FileWatcher(patterns=[str(tmp_path / "*.py")])
        w.is_modified()
        assert w.last_changed == []

    def test_unchanged_returns_false(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        w = FileWatcher(patterns=[str(tmp_path / "*.py")])
        w.is_modified()
        assert w.is_modified() is False

    def test_modified_file_returns_true(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("x")
        w = FileWatcher(patterns=[str(tmp_path / "*.py")])
        w.is_modified()
        os.utime(f, (time.time() + 1, time.time() + 1))
        assert w.is_modified() is True

    def test_modified_file_in_last_changed(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("x")
        w = FileWatcher(patterns=[str(tmp_path / "*.py")])
        w.is_modified()
        os.utime(f, (time.time() + 1, time.time() + 1))
        w.is_modified()
        assert str(f) in w.last_changed

    def test_added_file_returns_true(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        w = FileWatcher(patterns=[str(tmp_path / "*.py")])
        w.is_modified()
        (tmp_path / "b.py").write_text("y")
        assert w.is_modified() is True

    def test_deleted_file_returns_true(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("x")
        w = FileWatcher(patterns=[str(tmp_path / "*.py")])
        w.is_modified()
        f.unlink()
        assert w.is_modified() is True

    def test_file_count(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        (tmp_path / "b.py").write_text("y")
        w = FileWatcher(patterns=[str(tmp_path / "*.py")])
        w.is_modified()
        assert w.file_count() == 2

    def test_source_label(self):
        assert FileWatcher().source_label() == "watched"

    def test_empty_patterns_returns_false(self):
        assert FileWatcher().is_modified() is False

    def test_patterns_loaded_from_src_file(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        watch = tmp_path / "watch.txt"
        watch.write_text(str(tmp_path / "*.py") + "\n")
        w = FileWatcher(src_file=str(watch))
        assert w.is_modified() is True
        assert w.file_count() == 1


# ── GitFileWatcher ────────────────────────────────────────────────────────────

class TestGitFileWatcher:
    def _watcher(self, root="/repo"):
        with patch.object(GitFileWatcher, "_find_root", return_value=root):
            return GitFileWatcher()

    def test_first_call_true_when_files_exist(self):
        w = self._watcher()
        w._snapshot = Mock(return_value={"a.py": 1.0})
        assert w.is_modified() is True

    def test_first_call_last_changed_is_empty(self):
        w = self._watcher()
        w._snapshot = Mock(return_value={"a.py": 1.0})
        w.is_modified()
        assert w.last_changed == []

    def test_unchanged_returns_false(self):
        w = self._watcher()
        w._snapshot = Mock(return_value={"a.py": 1.0})
        w.is_modified()
        assert w.is_modified() is False

    def test_modified_mtime_returns_true(self):
        w = self._watcher()
        w._snapshot = Mock(side_effect=[{"a.py": 1.0}, {"a.py": 2.0}])
        w.is_modified()
        assert w.is_modified() is True

    def test_modified_file_in_last_changed(self):
        w = self._watcher()
        w._snapshot = Mock(side_effect=[{"a.py": 1.0}, {"a.py": 2.0}])
        w.is_modified()
        w.is_modified()
        assert w.last_changed == ["a.py"]

    def test_added_file_in_last_changed(self):
        w = self._watcher()
        w._snapshot = Mock(side_effect=[
            {"a.py": 1.0},
            {"a.py": 1.0, "b.py": 1.0},
        ])
        w.is_modified()
        w.is_modified()
        assert w.last_changed == ["b.py"]

    def test_deleted_file_in_last_changed(self):
        w = self._watcher()
        w._snapshot = Mock(side_effect=[
            {"a.py": 1.0, "b.py": 1.0},
            {"a.py": 1.0},
        ])
        w.is_modified()
        w.is_modified()
        assert w.last_changed == ["b.py"]

    def test_multiple_changes_in_last_changed(self):
        w = self._watcher()
        w._snapshot = Mock(side_effect=[
            {"a.py": 1.0, "b.py": 1.0},
            {"a.py": 2.0, "b.py": 1.0, "c.py": 1.0},
        ])
        w.is_modified()
        w.is_modified()
        assert w.last_changed == ["a.py", "c.py"]

    def test_file_count(self):
        w = self._watcher()
        w._snapshot = Mock(return_value={"a.py": 1.0, "b.py": 2.0})
        w.is_modified()
        assert w.file_count() == 2

    def test_source_label(self):
        assert self._watcher().source_label() == "git-tracked"

    def test_find_root_falls_back_to_cwd_when_git_missing(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            w = GitFileWatcher()
        assert w.repo_root == os.getcwd()

    def test_snapshot_returns_empty_when_git_missing(self):
        w = self._watcher()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert w._snapshot() == {}


# ── Runner ────────────────────────────────────────────────────────────────────

class TestRunner:
    def _one_shot_watcher(self, runner_ref, fires=True):
        """Watcher that triggers once then stops the runner."""
        call_count = 0

        def is_modified():
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                runner_ref[0].stop()
            return fires and call_count == 1

        w = Mock()
        w.is_modified.side_effect = is_modified
        w.file_count.return_value = 5
        w.source_label.return_value = "git-tracked"
        w.last_changed = []
        return w

    def test_run_once_executes_command(self):
        cmd = Command(["true"])
        cmd.run = Mock(return_value=0)
        w = Mock(file_count=Mock(return_value=1), source_label=Mock(return_value="watched"), last_changed=[])
        Runner(command=cmd, file_watcher=w)._run_once()
        cmd.run.assert_called_once()

    def test_run_once_renders_header_and_footer(self):
        cmd = Command(["pytest"])
        cmd.run = Mock(return_value=0)
        screen = Mock()
        w = Mock(file_count=Mock(return_value=3), source_label=Mock(return_value="git-tracked"), last_changed=["a.py"])
        Runner(command=cmd, file_watcher=w, screen=screen)._run_once()
        screen.render_header.assert_called_once_with("pytest", 3, "git-tracked", ["a.py"])
        screen.render_footer.assert_called_once()

    def test_run_once_passes_exit_code_to_footer(self):
        cmd = Command(["false"])
        cmd.run = Mock(return_value=1)
        screen = Mock()
        w = Mock(file_count=Mock(return_value=1), source_label=Mock(return_value="watched"), last_changed=[])
        Runner(command=cmd, file_watcher=w, screen=screen)._run_once()
        exit_code = screen.render_footer.call_args[0][0]
        assert exit_code == 1

    def test_run_once_no_screen_does_not_render(self):
        cmd = Command(["true"])
        cmd.run = Mock(return_value=0)
        w = Mock(file_count=Mock(return_value=1), source_label=Mock(return_value="watched"), last_changed=[])
        screen = Mock()
        runner = Runner(command=cmd, file_watcher=w, screen=None)
        runner._run_once()
        screen.render_header.assert_not_called()

    def test_start_enters_and_exits_screen(self):
        screen = Mock()
        runner_ref = [None]
        cmd = Command(["true"])
        cmd.run = Mock(return_value=0)
        w = self._one_shot_watcher(runner_ref)
        runner = Runner(command=cmd, file_watcher=w, screen=screen)
        runner_ref[0] = runner
        with patch("time.sleep"):
            runner.start()
        screen.enter.assert_called_once()
        screen.exit.assert_called_once()

    def test_start_exits_screen_on_exception(self):
        screen = Mock()
        w = Mock()
        w.is_modified.side_effect = RuntimeError("boom")
        runner = Runner(command=Mock(), file_watcher=w, screen=screen)
        with patch("time.sleep"), pytest.raises(RuntimeError):
            runner.start()
        screen.exit.assert_called_once()

    def test_start_runs_command_when_modified(self):
        runner_ref = [None]
        cmd = Command(["true"])
        cmd.run = Mock(return_value=0)
        w = self._one_shot_watcher(runner_ref, fires=True)
        runner = Runner(command=cmd, file_watcher=w)
        runner_ref[0] = runner
        with patch("time.sleep"):
            runner.start()
        cmd.run.assert_called_once()

    def test_start_skips_command_when_not_modified(self):
        runner_ref = [None]
        cmd = Command(["true"])
        cmd.run = Mock(return_value=0)
        w = self._one_shot_watcher(runner_ref, fires=False)
        runner = Runner(command=cmd, file_watcher=w)
        runner_ref[0] = runner
        with patch("time.sleep"):
            runner.start()
        cmd.run.assert_not_called()

    def test_stop_sets_stopped_flag(self):
        runner = Runner()
        runner.stop()
        assert runner._stopped is True
