from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
GIT_TIMEOUT_SECONDS = 5
APP_BASE_PATH = os.environ.get("APP_BASE_PATH", "").rstrip("/")

app = FastAPI(title="Local Git Monitor")
app.mount(
    f"{APP_BASE_PATH}/static", StaticFiles(directory=BASE_DIR / "static"), name="static"
)
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


class ProjectStatus(BaseModel):
    name: str
    path: str
    repo_root: str | None
    status: Literal["okay", "warning", "critical"]
    summary: str
    ahead_by: int
    behind_by: int
    uncommitted_changes: int
    has_remote: bool
    branch: str | None
    last_commit_date: str | None
    source_root: str


def normalize_path(raw_path: str) -> Path:
    return Path(raw_path).expanduser().resolve(strict=False)


def load_roots() -> list[str]:
    raw = os.environ.get("PROJECT_ROOTS", "")
    seen: set[str] = set()
    roots: list[str] = []
    for part in raw.split(":"):
        part = part.strip()
        if not part:
            continue
        normalized = str(normalize_path(part))
        if normalized not in seen:
            roots.append(normalized)
            seen.add(normalized)
    return roots


def git_command(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(path), *args],
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_SECONDS,
        check=False,
    )


def is_git_repository(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    result = git_command(path, "rev-parse", "--is-inside-work-tree")
    return result.returncode == 0 and result.stdout.strip() == "true"


def get_last_commit_date(repo_path: Path) -> str | None:
    result = git_command(
        repo_path,
        "log",
        "-1",
        "--date=format:%Y-%m-%d %H:%M:%S",
        "--format=%cd",
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return None


def candidate_directories(root_path: Path) -> list[Path]:
    if not root_path.exists() or not root_path.is_dir():
        return []

    if is_git_repository(root_path):
        return [root_path]

    children = [
        child
        for child in sorted(root_path.iterdir(), key=lambda item: item.name.lower())
        if child.is_dir()
    ]
    return children or [root_path]


def inspect_directory(source_root: Path, candidate: Path) -> ProjectStatus:
    if not candidate.exists() or not candidate.is_dir():
        return ProjectStatus(
            name=candidate.name or str(candidate),
            path=str(candidate),
            repo_root=None,
            status="critical",
            summary="Folder does not exist",
            ahead_by=0,
            behind_by=0,
            uncommitted_changes=0,
            has_remote=False,
            branch=None,
            last_commit_date=None,
            source_root=str(source_root),
        )

    is_repo = git_command(candidate, "rev-parse", "--is-inside-work-tree")
    if is_repo.returncode != 0 or is_repo.stdout.strip() != "true":
        return ProjectStatus(
            name=candidate.name,
            path=str(candidate),
            repo_root=None,
            status="critical",
            summary="No git repository found",
            ahead_by=0,
            behind_by=0,
            uncommitted_changes=0,
            has_remote=False,
            branch=None,
            last_commit_date=None,
            source_root=str(source_root),
        )

    repo_root_result = git_command(candidate, "rev-parse", "--show-toplevel")
    repo_root = Path(repo_root_result.stdout.strip()).resolve(strict=False)

    branch_result = git_command(repo_root, "branch", "--show-current")
    branch = branch_result.stdout.strip() or None

    status_result = git_command(repo_root, "status", "--porcelain")
    uncommitted_changes = len(
        [line for line in status_result.stdout.splitlines() if line.strip()]
    )

    upstream_result = git_command(
        repo_root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"
    )
    if upstream_result.returncode != 0:
        summary = "Git repository found, but no upstream remote is configured"
        return ProjectStatus(
            name=repo_root.name,
            path=str(repo_root),
            repo_root=str(repo_root),
            status="critical",
            summary=summary,
            ahead_by=0,
            behind_by=0,
            uncommitted_changes=uncommitted_changes,
            has_remote=False,
            branch=branch,
            last_commit_date=get_last_commit_date(repo_root),
            source_root=str(source_root),
        )

    ahead_result = git_command(repo_root, "rev-list", "--count", "@{upstream}..HEAD")
    behind_result = git_command(repo_root, "rev-list", "--count", "HEAD..@{upstream}")
    ahead_by = int(ahead_result.stdout.strip() or "0")
    behind_by = int(behind_result.stdout.strip() or "0")

    if ahead_by > 0:
        summary = (
            f"{ahead_by} commit{'s' if ahead_by != 1 else ''} waiting to be pushed"
        )
        status = "warning"
    else:
        summary = "Up to date with upstream"
        status = "okay"

    if behind_by > 0:
        summary += f"; {behind_by} behind upstream"
    if uncommitted_changes > 0:
        summary += f"; {uncommitted_changes} local file change{'s' if uncommitted_changes != 1 else ''}"

    return ProjectStatus(
        name=repo_root.name,
        path=str(repo_root),
        repo_root=str(repo_root),
        status=status,
        summary=summary,
        ahead_by=ahead_by,
        behind_by=behind_by,
        uncommitted_changes=uncommitted_changes,
        has_remote=True,
        branch=branch,
        last_commit_date=get_last_commit_date(repo_root),
        source_root=str(source_root),
    )


def collect_projects(roots: list[str]) -> list[ProjectStatus]:
    projects: list[ProjectStatus] = []
    seen_repos: set[str] = set()
    seen_missing: set[str] = set()

    for raw_root in roots:
        root_path = normalize_path(raw_root)
        for candidate in candidate_directories(root_path):
            project = inspect_directory(root_path, candidate)
            identity = project.repo_root or project.path
            if project.repo_root:
                if identity in seen_repos:
                    continue
                seen_repos.add(identity)
            else:
                if identity in seen_missing:
                    continue
                seen_missing.add(identity)
            projects.append(project)

    severity_order = {"critical": 0, "warning": 1, "okay": 2}
    return sorted(
        projects,
        key=lambda item: (
            severity_order[item.status],
            item.name.lower(),
            item.path.lower(),
        ),
    )


def build_dashboard_payload() -> dict[str, object]:
    roots = load_roots()
    missing_roots = [r for r in roots if not Path(r).exists()]
    all_projects = collect_projects(roots)
    non_repo_dirs = [p for p in all_projects if p.repo_root is None]
    projects = [p for p in all_projects if p.repo_root is not None]
    return {
        "missing_roots": missing_roots,
        "non_repo_dirs": [
            {"name": p.name, "path": p.path, "source_root": p.source_root}
            for p in non_repo_dirs
        ],
        "projects": [project.model_dump() for project in projects],
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total": len(projects),
            "okay": sum(1 for project in projects if project.status == "okay"),
            "warning": sum(1 for project in projects if project.status == "warning"),
            "critical": sum(1 for project in projects if project.status == "critical"),
        },
    }


@app.get(f"{APP_BASE_PATH}/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "initial_state": build_dashboard_payload(),
            "base_path": APP_BASE_PATH,
        },
    )


@app.get(f"{APP_BASE_PATH}/api/state")
async def get_state() -> dict[str, object]:
    return build_dashboard_payload()


def main() -> None:
    dev = os.environ.get("DEV", "false").lower() == "true"
    uvicorn.run("main:app", host="0.0.0.0", port=8010, reload=dev)


if __name__ == "__main__":
    main()
