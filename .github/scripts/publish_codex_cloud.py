"""Publish completed Codex Cloud tasks from a signed-in Mac."""

import argparse
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from publish_codex_patch import (
    CODEX_BOT_ID, REQUEST_ID, api, build_commit, find_request, git, target_ref,
)


TITLE_PREFIX = re.compile(rf"^\[codex:({REQUEST_ID})\] ")
TASK_LINK = re.compile(
    r"https://chatgpt\.com/(?:s/cd_[a-f0-9]+|codex/tasks/[A-Za-z0-9_-]+)"
)
CLI_TASK_ID = re.compile(r"task_[A-Za-z0-9_]+")
GITHUB_CREDENTIALS = (
    "-c", "credential.helper=", "-c", "credential.helper=!gh auth git-credential",
)


def github_pages(endpoint):
    pages = api(endpoint, "--paginate", "--slurp")
    return [item for page in pages for item in page]


def pending_reply(comments, nonce, sha):
    marker = f"CODEX_CLOUD_READY {nonce} {sha}"
    replies = [
        comment
        for comment in comments
        if comment["user"]["id"] == CODEX_BOT_ID
        and comment["body"].splitlines().count(marker) == 1
        and TASK_LINK.search(comment["body"])
    ]
    return replies[0] if len(replies) == 1 else None


def cloud_tasks():
    options = ["codex", "cloud", "list", "--json", "--limit", "50"]
    cursor = None
    seen = set()
    while True:
        command = options + (["--cursor", cursor] if cursor else [])
        page = json.loads(subprocess.check_output(command, timeout=60))
        yield from page["tasks"]
        cursor = page.get("cursor")
        if not cursor:
            return
        if cursor in seen:
            raise RuntimeError("Codex returned a repeated task cursor.")
        seen.add(cursor)


def resolve_task(tasks, title, repo, request, reply):
    start = datetime.fromisoformat(request["created_at"])
    end = datetime.fromisoformat(reply["created_at"]) + timedelta(minutes=2)
    matches = [
        task for task in tasks
        if task.get("title") == f"GitHub Mention: {title}"
        and (task.get("environment_label") or "").casefold() == repo.casefold()
        and start <= datetime.fromisoformat(task["updated_at"]) <= end
    ]
    if len(matches) != 1:
        return None
    task = matches[0]
    if task["status"] == "ready" and CLI_TASK_ID.fullmatch(task["id"]):
        return task["id"]
    return None


def publish(repo, pr_api, sha, task_path, task_id, number, author):
    original = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="codex-cloud-publish-") as directory:
        scratch = Path(directory)
        try:
            os.chdir(scratch)
            git("init", "--quiet", "--bare")
            owner = repo["owner"]["id"]
            default = repo["default_branch"]
            ref = target_ref(api(pr_api), repo["id"], owner, default, sha)
            origin = repo["clone_url"]
            git(*GITHUB_CREDENTIALS, "fetch", "--quiet", "--no-tags", "--depth=1",
                origin, f"refs/pull/{number}/head")
            if git("rev-parse", "FETCH_HEAD").decode().strip() != sha:
                raise RuntimeError("The PR head changed during fetch.")
            patch = subprocess.check_output(
                ["codex", "cloud", "diff", task_id], timeout=120
            )
            if not patch.startswith(b"diff --git "):
                raise RuntimeError("Codex did not return a Git patch.")
            commit = build_commit(sha, task_path, patch, scratch / "patch-index", number, author=author)
            if target_ref(api(pr_api), repo["id"], owner, default, sha) != ref:
                raise RuntimeError("The target branch changed.")
            # The lease requires the exact approved parent, even if the branch was rewound.
            git(
                *GITHUB_CREDENTIALS,
                "push", f"--force-with-lease={ref}:{sha}", origin, f"{commit}:{ref}",
            )
            print(f"Published {task_id} to PR #{number} as {commit}.", flush=True)
        finally:
            os.chdir(original)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", help="GitHub repository in owner/name form")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+", args.repository):
        parser.error("Expected a GitHub repository in owner/name form.")
    repo_api = f"repos/{args.repository}"
    repo = api(repo_api)
    owner_id = repo["owner"]["id"]
    user = api("user")
    if user["id"] != owner_id:
        parser.error("The GitHub CLI must be signed in as the repository owner.")
    author = (user["login"], f"{owner_id}+{user['login']}@users.noreply.github.com")
    tasks = None
    for pr in github_pages(f"{repo_api}/pulls?state=open&per_page=100"):
        title = pr["title"]
        prefix = TITLE_PREFIX.match(title)
        if not prefix or pr["user"]["id"] != owner_id:
            continue
        nonce = prefix[1]
        sha = pr["head"]["sha"]
        number = pr["number"]
        try:
            comments = github_pages(f"{repo_api}/issues/{number}/comments?per_page=100")
            reply = pending_reply(comments, nonce, sha)
            if not reply:
                continue
            request, task_path = find_request(comments, owner_id, reply, nonce, sha)
            if tasks is None:
                tasks = list(cloud_tasks())
            task_id = resolve_task(tasks, title, args.repository, request, reply)
            if task_id:
                publish(repo, f"{repo_api}/pulls/{number}", sha, task_path, task_id, number, author)
        except (RuntimeError, SystemExit, subprocess.SubprocessError) as error:
            print(f"PR #{number}: {error}", flush=True)


if __name__ == "__main__":
    main()
