import os
import re
import json
import subprocess
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_OWNER = os.environ["GITHUB_OWNER"]
GITHUB_REPO = os.environ["GITHUB_REPO"]
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3-coder:30b")

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

SYSTEM_PROMPT = """You are an autonomous software engineer working in an existing git repository.
You MUST output a single unified diff patch in git format that can be applied with `git apply`.
No explanations, no markdown, no extra text.
Rules:
- Do not modify or add secrets.
- Keep changes minimal for the task.
- Ensure tests pass by design.
- If you need new files, include them in the diff.
Output format:
diff --git a/... b/...
...
"""

def sh(cmd: list[str], check=True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True, check=check)

def ensure_clean_worktree():
    res = sh(["git", "status", "--porcelain"], check=True)
    if res.stdout.strip():
        raise RuntimeError("Working tree is not clean. Commit/stash your changes first.")

def current_branch() -> str:
    return sh(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()

def create_branch(branch: str):
    sh(["git", "checkout", "-B", branch])

def call_ollama(task_text: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": task_text,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {
            "temperature": 0.2,
        },
    }
    r = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=600)
    r.raise_for_status()
    data = r.json()
    return data["response"]

def extract_diff(text: str) -> str:
    # Sometimes models may prepend/append noise; extract from first "diff --git" to end
    m = re.search(r"(diff --git[\s\S]+)", text)
    if not m:
        raise RuntimeError("No `diff --git` block found in model output.")
    return m.group(1).strip() + "\n"

def apply_diff(diff_text: str):
    p = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", "-"],
        cwd=REPO_ROOT,
        input=diff_text,
        text=True,
        capture_output=True,
    )
    if p.returncode != 0:
        raise RuntimeError(f"git apply failed:\n{p.stderr}\n---\nModel diff was:\n{diff_text[:2000]}")

def run_tests() -> tuple[bool, str]:
    # Adjust path if your solution differs later
    cmd = ["dotnet", "test", r".\core\CoreSim.Tests\CoreSim.Tests.csproj", "-c", "Release"]
    p = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True)
    ok = (p.returncode == 0)
    out = (p.stdout or "") + "\n" + (p.stderr or "")
    return ok, out

def commit_all(message: str):
    sh(["git", "add", "-A"])
    sh(["git", "commit", "-m", message])

def push_branch(branch: str):
    sh(["git", "push", "-u", "origin", branch])

def create_pr(branch: str, title: str, body: str) -> str:
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/pulls"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    payload = {
        "title": title,
        "head": branch,
        "base": "main",
        "body": body,
    }
    r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
    r.raise_for_status()
    return r.json()["html_url"]

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-file", required=True, help="Path to a text file with the task/issue content.")
    parser.add_argument("--branch", default=None, help="Branch name to use (default: agent/<timestamp>)")
    parser.add_argument("--pr", action="store_true", help="Create a GitHub PR after push.")
    args = parser.parse_args()

    with open(args.task_file, "r", encoding="utf-8") as f:
        task = f.read().strip()

    ensure_clean_worktree()

    branch = args.branch or f"agent/{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    create_branch(branch)

    # Ask model for diff
    diff = call_ollama(task)
    diff = extract_diff(diff)
    apply_diff(diff)

    ok, test_output = run_tests()
    if not ok:
        # Ask model for a fix diff using the failing logs
        fix_task = task + "\n\nTESTS FAILED. Here is the test output:\n" + test_output + "\n\nReturn a git diff patch that fixes the failures."
        fix_diff = call_ollama(fix_task)
        fix_diff = extract_diff(fix_diff)
        apply_diff(fix_diff)

        ok2, test_output2 = run_tests()
        if not ok2:
            raise RuntimeError("Tests still failing after one fix attempt.\n" + test_output2)

    commit_all("bootstrap: core sim solution with tests")
    push_branch(branch)

    if args.pr:
        pr_url = create_pr(
            branch=branch,
            title="Bootstrap core simulation solution",
            body="Automated bootstrap: .NET core solution + NUnit tests + CI workflow.\n\nHow to verify:\n- dotnet test ./core/CoreSim.Tests/CoreSim.Tests.csproj\n",
        )
        print("PR:", pr_url)
    else:
        print("Pushed branch:", branch)
        print("Open a PR to main.")

if __name__ == "__main__":
    main()
