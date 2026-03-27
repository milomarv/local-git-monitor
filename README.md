# Local Git Monitor

Small FastAPI dashboard that scans one or more project root folders and shows the git status of each repository at a glance.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Git

## Configuration

Create a `.env` file in the project root and configure the variables below.

| Variable | Required | Default | Description |
|---|---|---|---|
| `PROJECT_ROOTS` | Yes | _(empty)_ | Colon-separated list of folders to scan. Each path can be a container folder (its direct subfolders are scanned as individual projects) or a path that is itself a git repo. Example: `/home/you/projects:/home/you/work` |
| `APP_BASE_PATH` | No | _(empty)_ | URL prefix to mount the app under, useful behind a reverse proxy. Example: `/localgitmonitor` |
| `DEV` | No | `false` | Set to `true` to enable Uvicorn auto-reload. |

## Run

```bash
uv sync
uv run python main.py
```

Open `http://127.0.0.1:8010`.

## Docker & Traefik

A `docker-compose.yml` is included for container deployments with [Traefik](https://traefik.io/) as a reverse proxy:

- The app is exposed on port `8010` and attached to the `traefik-public` external network.
- Traefik labels route traffic via the `APP_BASE_PATH` prefix on the `websecure` entrypoint with TLS.
- The `PROJECT_ROOTS` path is bind-mounted into the container at the same path, so the value you set in `.env` works unchanged inside the container.
- Your `~/.ssh` directory is mounted read-only so git can push over SSH.

```bash
docker compose up -d --build
```

## Development

```bash
uv sync
uv run ruff check .   # lint
uv run ruff check --fix .  # auto-fix
```

## Status colours

| Colour | Meaning |
|---|---|
| **Green — OKAY** | Upstream configured, nothing waiting to be pushed |
| **Yellow — WARNING** | Unpushed commits or uncommitted file changes |
| **Red — CRITICAL** | No git repo found, folder missing, or no upstream remote configured |

## Terms

- **Branch** — the currently checked-out local branch. Status is only reported for that branch and its upstream; other local branches with unpushed commits are not shown.
- **Dirty Files** — files with local changes not yet committed (modified, added, deleted, renamed, untracked), based on `git status --porcelain`. Files matching patterns in `.git/info/exclude` are excluded from the count.
