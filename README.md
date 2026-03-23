# Local Git Monitor

Small FastAPI application that scans one or more project root folders and shows the git status of each project directory.

## Configuration

Create a `.env` file in the project root and set `PROJECT_ROOTS` to a colon-separated list of folders to scan:

```dotenv
PROJECT_ROOTS=/home/you/projects:/home/you/work
```

Each path can be:
- a container folder whose direct subfolders are each scanned as individual projects
- a path that is itself a git repo, in which case it is monitored directly

## Run

```bash
uv sync
uv run python main.py
```

Then open `http://127.0.0.1:8010`.

## Status colours

- **Green** — upstream configured, nothing waiting to be pushed
- **Yellow** — commits exist locally that have not been pushed
- **Red** — no git repo, folder missing, or no upstream remote configured

## Terms

- **Branch** — the currently checked-out local branch for that repository, such as `main` or `master`. The dashboard only reports status for the current branch and its upstream. Other local branches with unpushed commits are not shown unless you check out that branch.
- **Dirty Files** — count of files with local git changes that are not yet committed. This includes modified, added, deleted, renamed, and untracked files, based on `git status --porcelain`.
