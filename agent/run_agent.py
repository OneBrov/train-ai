import os
import re
import json
import subprocess
from datetime import datetime
from typing import Tuple, Optional

import requests
from dotenv import load_dotenv

# ============================================================
# Configuration
# ============================================================

load_dotenv()

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_OWNER = os.environ["GITHUB_OWNER"]
GITHUB_REPO = os.environ["GITHUB_REPO"]

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3-coder:30b")

MAX_DIFF_ATTEMPTS = int(os.getenv("MAX_DIFF_ATTEMPTS", "3"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))

TEST_PROJECT = os.getenv("TEST_PROJECT", r".\core\CoreSim.Tests\CoreSim.Tests.csproj")

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Logging
LOG_DIR = os.path.join(REPO_ROOT, "agent_logs")
os.makedirs(LOG_DIR, exist_ok=True)

# ============================================================
# Prompts
# ============================================================

SYSTEM_PROMPT = """You are an autonomous senior software engineer working in an existing git repository.

You MUST output a single unified git diff that can be applied with `git apply`.

STRICT RULES:
- Output ONLY the diff. No explanations. No markdown.
- Every opened file must be complete and syntactically valid.
- If you add or modify a file, include correct full patch chunks.
- Do not touch secrets or environment files.
- Keep changes minimal and directly related to the task.
- Ensure CI passes.

Output MUST start with:
diff --git a/... b/...
"""

# ============================================================
# Utilities
# ============================================================

def _write_log(name: str, content: str):
    path = os.path.join(LOG_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path

def sh(cmd: list[str], check=True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=check,
    )

def ensure_clean_worktree():
    res = sh(["git", "status", "--porcelain"])
    if res.stdout.strip():
        raise RuntimeError(
            "Working tree is not clean.\n"
            "Commit/stash local changes before running the agent."
        )

def hard_reset():
    sh(["git", "reset", "--hard"])

def create_branch(branch: str):
    sh(["git", "checkout", "-B", branch])

def new_branch_name() -> str:
    return f"agent/{datetime.now().strftime('%Y%m%d-%H%M%S')}"

# ============================================================
# Ollama
# ============================================================

def call_ollama(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {"temperature": TEMPERATURE},
    }
    r = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=600)
    r.raise_for_status()
    return r.json()["response"]

# ============================================================
# Diff validation & apply
# ============================================================

def extract_diff(text: str) -> str:
    match = re.search(r"(diff --git[\s\S]+)", text)
    if not match:
        raise ValueError("No git diff found in model output.")

    diff = match.group(1).strip() + "\n"

    # If model outputs XML, require basic closure to avoid truncation disasters
    if "<Project" in diff:
        if "</Project>" not in diff:
            raise ValueError("Incomplete XML in diff (missing </Project>).")
        if diff.count("<Project") != diff.count("</Project>"):
            raise ValueError("Mismatched <Project> XML tags in diff.")

    return diff

def git_apply_check(diff: str):
    p = subprocess.run(
        ["git", "apply", "--check", "--whitespace=nowarn", "-"],
        cwd=REPO_ROOT,
        input=diff,
        text=True,
        capture_output=True,
    )
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip())

def git_apply(diff: str):
    p = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", "-"],
        cwd=REPO_ROOT,
        input=diff,
        text=True,
        capture_output=True,
    )
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip())

# ============================================================
# Tests
# ============================================================

def run_tests() -> Tuple[bool, str]:
    cmd = ["dotnet", "test", TEST_PROJECT, "-c", "Release"]
    p = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True)
    output = (p.stdout or "") + "\n" + (p.stderr or "")
    return p.returncode == 0, output

# ============================================================
# GitHub API
# ============================================================

def _gh_headers() -> dict:
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }

def _gh_raise_for_status(r: requests.Response, context: str):
    if r.ok:
        return
    try:
        payload = r.json()
        pretty = json.dumps(payload, ensure_ascii=False, indent=2)
    except Exception:
        pretty = r.text
    log_path = _write_log(f"github_error_{context}.txt", pretty)
    raise RuntimeError(f"GitHub API error ({context}) {r.status_code}. Details saved to: {log_path}")

def commit_all(message: str):
    sh(["git", "add", "-A"])
    sh(["git", "commit", "-m", message])

def push_branch(branch: str):
    sh(["git", "push", "-u", "origin", branch])

def create_pr(branch: str, title: str, body: str) -> int:
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/pulls"
    r = requests.post(
        url,
        headers=_gh_headers(),
        json={"title": title, "head": branch, "base": "main", "body": body},
        timeout=60,
    )
    if not r.ok:
        _gh_raise_for_status(r, "create_pr")
    return r.json()["number"]

def enable_auto_merge(pr_number: int):
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/pulls/{pr_number}/auto-merge"
    r = requests.put(url, headers=_gh_headers(), json={"merge_method": "squash"}, timeout=60)
    if not r.ok:
        _gh_raise_for_status(r, "enable_auto_merge")

# ============================================================
# Agent loop
# ============================================================

def generate_and_apply(task: str):
    last_error: Optional[str] = None

    for attempt in range(1, MAX_DIFF_ATTEMPTS + 1):
        print(f"[agent] Diff attempt {attempt}/{MAX_DIFF_ATTEMPTS}")

        prompt = task
        if last_error:
            prompt += (
                "\n\nPREVIOUS FAILURE:\n"
                f"{last_error}\n\n"
                "Return a corrected FULL git diff. Output ONLY the diff."
            )

        try:
            raw = call_ollama(prompt)
            _write_log(f"ollama_raw_attempt_{attempt}.txt", raw)

            diff = extract_diff(raw)
            _write_log(f"ollama_diff_attempt_{attempt}.diff", diff)

            # extra safety: check before apply
            git_apply_check(diff)
            git_apply(diff)
            return
        except Exception as e:
            hard_reset()
            last_error = str(e)
            print("[agent] failed:", last_error)

    raise RuntimeError(f"Failed after {MAX_DIFF_ATTEMPTS} attempts. Last error: {last_error}")

# ============================================================
# Main
# ============================================================

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--task-file", required=True)
    parser.add_argument("--branch", default=None)
    parser.add_argument("--pr", action="store_true", help="Create PR and enable auto-merge immediately.")
    args = parser.parse_args()

    with open(args.task_file, "r", encoding="utf-8") as f:
        task = f.read().strip()

    ensure_clean_worktree()

    branch = args.branch or new_branch_name()
    create_branch(branch)

    generate_and_apply(task)

    ok, output = run_tests()
    _write_log("dotnet_test_output.txt", output)
    if not ok:
        print("[agent] Tests failed, attempting auto-fix")
        fix_task = task + "\n\nTEST OUTPUT:\n" + output
        generate_and_apply(fix_task)

        ok2, output2 = run_tests()
        _write_log("dotnet_test_output_after_fix.txt", output2)
        if not ok2:
            raise RuntimeError("Tests still failing after fix. See agent_logs/ for outputs.")

    commit_all("feat: apply task changes")
    push_branch(branch)

    if args.pr:
        pr_number = create_pr(
            branch=branch,
            title="Automated change",
            body=f"Autonomous agent PR.\n\nHow to verify:\n- dotnet test {TEST_PROJECT}\n",
        )
        enable_auto_merge(pr_number)
        print("PR created + auto-merge enabled:", pr_number)
    else:
        print("Branch pushed:", branch)

if __name__ == "__main__":
    main()
