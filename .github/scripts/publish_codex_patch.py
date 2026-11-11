"""Apply a Codex comment patch to the exact PR head approved in its request."""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


CODEX_BOT_ID = 199175422
REQUEST_ID = r"[0-9a-f]{32}"
SHA = r"[0-9a-f]{40}"
TASK = r"ideas/[A-Za-z0-9][A-Za-z0-9._-]*/TASK\.md"


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def api(endpoint, *options):
    output = subprocess.check_output(["gh", "api", *options, endpoint])
    return json.loads(output)


def git(*args, env=None, data=None):
    result = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *args],
        env=env,
        input=data,
        stdout=subprocess.PIPE,
        check=True,
    )
    return result.stdout


def read_reply(body):
    body = body.replace("\r\n", "\n")
    markers = re.findall(
        rf"^CODEX_PATCH_RESULT ({REQUEST_ID}) ({SHA})$", body, re.MULTILINE
    )
    require(len(markers) == 1, "Expected exactly one Codex result marker.")
    request_id, sha = markers[0]
    blocks = re.findall(
        rf"^CODEX_PATCH_RESULT {request_id} {sha}\n"
        r"```diff\n(diff --git [\s\S]*?)^```\n"
        rf"CODEX_PATCH_END {request_id}$",
        body,
        re.MULTILINE,
    )
    require(len(blocks) == 1, "Codex did not supply a complete fenced patch.")
    require(
        not re.search(r"^```", blocks[0], re.MULTILINE),
        "The patch must be in one fenced block.",
    )
    return request_id, sha, blocks[0].encode()


def find_request(comments, owner_id, response, request_id, sha):
    marker = re.compile(
        rf"^CODEX_PATCH_REQUEST {request_id} {sha} ({TASK})$", re.MULTILINE
    )
    matches = []
    for comment in comments:
        if (
            comment["user"]["id"] != owner_id
            or comment["id"] >= response["id"]
            or comment["created_at"] > response["created_at"]
            or comment["updated_at"] != comment["created_at"]
        ):
            continue
        body = comment["body"].replace("\r\n", "\n")
        if body.startswith("@codex "):
            matches.extend((comment, task) for task in marker.findall(body))
    require(len(matches) == 1, "No unique matching request from the repository owner.")
    return matches[0]


def target_ref(pr, repo_id, owner_id, default_branch, sha):
    head = pr["head"]
    require(pr["state"] == "open", "The pull request is closed.")
    require(pr["user"]["id"] == owner_id, "The pull request must belong to the owner.")
    require((head["repo"] or {}).get("id") == repo_id, "Fork branches are unsupported.")
    require(pr["base"]["ref"] == default_branch, "Expected a PR into the default branch.")
    require(head["ref"] != default_branch, "Cannot publish onto the default branch.")
    require(head["sha"] == sha, "The PR head moved. Request a new Codex patch.")
    ref = "refs/heads/" + head["ref"]
    git("check-ref-format", ref)
    return ref


def build_commit(
    sha, task, patch, index_path, pr_number,
    *,
    author=("github-actions[bot]", "41898282+github-actions[bot]@users.noreply.github.com"),
):
    name, email = author
    env = os.environ | {
        "GIT_INDEX_FILE": str(index_path),
        "GIT_AUTHOR_NAME": name,
        "GIT_AUTHOR_EMAIL": email,
        "GIT_COMMITTER_NAME": name,
        "GIT_COMMITTER_EMAIL": email,
    }
    require(
        git("cat-file", "-t", f"{sha}:{task}").strip() == b"blob",
        "The task file must exist at the approved revision.",
    )
    git("read-tree", sha, env=env)
    git("apply", "--cached", "--whitespace=error", "-", env=env, data=patch)
    changes = git(
        "diff", "--cached", "--raw", "--no-renames", "-z", sha, env=env
    ).split(b"\0")[:-1]
    require(changes, "The patch makes no changes.")
    project = task.rsplit("/", 1)[0].encode() + b"/"
    regular_modes = {b"000000", b"100644", b"100755"}
    for metadata, path in zip(changes[::2], changes[1::2], strict=True):
        old_mode, new_mode, *_ = metadata[1:].split()
        require(path.startswith(project), "The patch changes files outside the task project.")
        require(
            old_mode in regular_modes and new_mode in regular_modes,
            "Only regular files can be published.",
        )
    tree = git("write-tree", env=env).decode().strip()
    return git(
        "commit-tree", tree, "-p", sha, "-m", f"Apply Codex patch for PR #{pr_number}",
        env=env,
    ).decode().strip()


def main():
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    response = event["comment"]
    require(response["user"]["id"] == CODEX_BOT_ID, "Expected a Codex bot comment.")
    repo = event["repository"]
    owner_id = repo["owner"]["id"]
    pr_number = event["issue"]["number"]
    request_id, sha, patch = read_reply(response["body"])
    repo_api = f"repos/{repo['full_name']}"
    pr_api = f"{repo_api}/pulls/{pr_number}"
    pr = api(pr_api)
    ref = target_ref(pr, repo["id"], owner_id, repo["default_branch"], sha)
    pages = api(
        f"{repo_api}/issues/{pr_number}/comments?per_page=100", "--paginate", "--slurp"
    )
    _, task = find_request(
        (comment for page in pages for comment in page), owner_id, response, request_id, sha
    )
    git("fetch", "--no-tags", "origin", f"refs/pull/{pr_number}/head")
    require(
        git("rev-parse", "FETCH_HEAD").decode().strip() == sha,
        "The PR head changed during fetch.",
    )
    with tempfile.TemporaryDirectory() as directory:
        commit = build_commit(sha, task, patch, Path(directory) / "index", pr_number)
    require(
        target_ref(api(pr_api), repo["id"], owner_id, repo["default_branch"], sha) == ref,
        "The target branch changed.",
    )
    # The commit is a child of sha. The lease also rejects a deleted or rewound ref.
    git("push", f"--force-with-lease={ref}:{sha}", "origin", f"{commit}:{ref}")
    print(f"Published {commit} to PR #{pr_number}.")


if __name__ == "__main__":
    main()
