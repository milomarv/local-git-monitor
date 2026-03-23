# Local Git Monitor

Small FastAPI application that scans one or more project root folders and shows the git status of each project directory.

## Configuration

Create a `.env` file in the project root (use `.env.example` as a starting point) and configure the settings below.

| Variable | Required | Default | Description |
|---|---|---|---|
| `PROJECT_ROOTS` | Yes | _(empty)_ | Colon-separated list of folders to scan. Each path can be a container folder whose direct subfolders are scanned as individual projects, or a path that is itself a git repo and is monitored directly. Example: `/home/you/projects:/home/you/work` |
| `APP_BASE_PATH` | No | _(empty)_ | URL path prefix to mount the app under, useful when serving behind a reverse proxy at a sub-path. Example: `/localgitmonitor` |
| `DEV` | No | `false` | Set to `true` to enable Uvicorn auto-reload for development. |

## Run

```bash
uv sync
uv run python main.py
```

Then open `http://127.0.0.1:8010`.

## Docker & Traefik

A `docker-compose.yml` is included for container deployments. It supports [Traefik](https://traefik.io/) as a reverse proxy out of the box:

- The app is exposed on port `8010` and attached to the `traefik-public` external network.
- Traefik labels route traffic via the `APP_BASE_PATH` prefix on the `websecure` entrypoint with TLS enabled.
- Set `APP_BASE_PATH` in your `.env` (e.g. `/localgitmonitor`) to match the Traefik `PathPrefix` rule.

```bash
docker compose up -d --build
```

## Status colours

- **Green OKAY** — upstream configured, nothing waiting to be pushed
- **Yellow WARNING** — commits exist locally that have not been pushed, or there are uncommitted (dirty) file changes
- **Red CRITICAL** — no git repo, folder missing, or no upstream remote configured

## Terms

- **Branch** — the currently checked-out local branch for that repository, such as `main` or `master`. The dashboard only reports status for the current branch and its upstream. Other local branches with unpushed commits are not shown unless you check out that branch.
- **Dirty Files** — count of files with local git changes that are not yet committed. This includes modified, added, deleted, renamed, and untracked files, based on `git status --porcelain`. Files whose relative path or filename matches a pattern in `.git/info/exclude` are excluded from the count, even for tracked (already-committed) files.
