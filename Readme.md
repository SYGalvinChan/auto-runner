# auto-runner

Watch files for changes and re-run a command automatically.

In a git repository, auto-runner tracks all git-managed files by default and
displays output on an alternate terminal screen — so your terminal stays clean
and only shows the latest run.

## Installation

```bash
pip install git+https://github.com/SYGalvinChan/auto-runner.git
```

## Usage

```
auto-runner (-c COMMAND | -C COMMAND_FILE) [options]
```

### Examples

Run a test script whenever any git-tracked file changes:
```bash
auto-runner -C test.sh
```

Run pytest against specific directories:
```bash
auto-runner -c 'pytest tests/' -w 'src/**' 'tests/**'
```

Run a make target without the alternate screen:
```bash
auto-runner -c 'make build' --no-screen
```

## Options

### Command *(required, pick one)*

| Flag | Description |
|------|-------------|
| `-c`, `--command` | Shell command to run |
| `-C`, `--command-file` | Executable file to run (also watched for changes in non-git mode) |

### Watch

| Flag | Description |
|------|-------------|
| `-w`, `--watch` | Glob patterns to watch — disables git mode |
| `-W`, `--watch-file` | Text file containing glob patterns (one per line); the file itself is also watched — disables git mode |
| `--no-git` | Disable git-aware watching; requires `-w` or `-W` |

### Display

| Flag | Description |
|------|-------------|
| `--no-screen` | Disable alternate screen; output goes to stdout |

## How it works

- **Git mode** (default inside a git repo): watches all files tracked by `git ls-files`. The header shows how many files are tracked and which ones changed on the last run.
- **Pattern mode** (`-w` / `-W`): watches files matched by glob patterns. Useful outside git repos or when you only care about a subset of files.
- The screen redraws automatically when the terminal is resized.
- Press `Ctrl+C` to stop.
