import os
import re
import json
import subprocess
from datetime import datetime
from typing import Tuple

import requests
from dotenv import load_dotenv

# =========================
# Configuration
# =========================

load_dotenv()

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_OWNER = os.environ["GITHUB_OWNER"]
GITHUB_REPO = os.environ["GITHUB_REPO"]

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3-coder:30b")

MAX_DIFF_ATTEMPTS = 3
TEMPERATURE = 0.2

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# =========================
# Prompts
# =========================

SYSTEM_PROMPT = """You are an autonomous senior software engineer working in an existing git repository.

You MUST output a single unified git diff that can be applied with `git apply`.

STRICT RULES:
- Output ONLY the diff. No explanations. No markdown.
- Every opened file must be complete and syntactically valid.
- XML/CSProj files MUST be fully closed.
- If you add a file, include the full file contents.
- Do not touch secrets or environment files.
- Keep changes minimal and directly related to the task.

Output format MUST start with:
diff --git a/... b/...
"""

# =========================
# Utilities
# =========================

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
            "Commit or stash your local changes before running the agent."
        )

def hard_reset():
    sh(["git", "reset", "--hard"])

def create_branch(branch: str):
    sh(["git", "checkout", "-B", branch])

# =========================
# Ollama
# =========================

def call_ollama(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {
            "temperature": TEMPERATURE,
        },
    }

    r = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json=payload,
        timeout=600,
    )
    r.raise_for_status()
    return r.json()["response"]

# =========================
# Diff validation
# =========================

def extract_diff(text: str) -> str:
    match = re.search(r"(diff --git[\s\S]+)", text)
    if not match:
        raise ValueError("No git diff found in model output.")

    diff = match.group(1).strip() + "\n"

    if len(diff) < 50:
        raise ValueError("Diff is suspiciously small.")

    # XML sanity checks
    if "<Project" in diff and "</Project>" not in diff:
        raise ValueError("Incomplete XML: missing </Project>.")

    if diff.count("<Project") != diff.count("</Project>"):
        raise ValueError("Mismatched <Project> XML tags.")

    return diff

def try_apply_diff(diff: str):
    p = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", "-"],
        cwd=REPO_ROOT,
        input=diff,
        text=True,
        capture_output=True,
    )

    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip())

# =========================
# Tests
# =========================

def run_tests() -> Tuple[bool, str]:
    cmd = [
        "dotnet",
        "test",
        r".\core\CoreSim.Tests\CoreSim.Tests.csproj",
        "-c",
        "Release",
    ]

    p = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    output = (p.stdout or "") + "\n" + (p.stderr or "")
    return p.returncode == 0, output

# =========================
# GitHub
# =========================

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

    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()["html_url"]

# =========================
# Main agent loop
# =========================

def generate_and_apply(task: str):
    last_error = None

    for attempt in range(1, MAX_DIFF_ATTEMPTS + 1):
        print(f"[agent] Diff attempt {attempt}/{MAX_DIFF_ATTEMPTS}")

        prompt = task
        if last_error:
            prompt += (
                "\n\nPREVIOUS ATTEMPT FAILED:\n"
                f"{last_error}\n\n"
                "Return a FULL corrected git diff."
            )

        try:
            raw = call_ollama(prompt)
            diff = extract_diff(raw)
            try_apply_diff(diff)
            return
        except Exception as e:
            hard_reset()
            last_error = str(e)
            print(f"[agent] attempt failed: {last_error}")

    raise RuntimeError(
        "Failed to produce a valid git diff after "
        f"{MAX_DIFF_ATTEMPTS} attempts.\n"
        f"Last error: {last_error}"
    )

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--task-file", required=True)
    parser.add_argument("--branch", default=None)
    parser.add_argument("--pr", action="store_true")
    args = parser.parse_args()

    with open(args.task_file, "r", encoding="utf-8") as f:
        task = f.read().strip()

    ensure_clean_worktree()

    branch = args.branch or f"agent/{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    create_branch(branch)

    # Generate + apply diff
    generate_and_apply(task)

    # Tests + one repair attempt
    ok, output = run_tests()
    if not ok:
        print("[agent] Tests failed, attempting auto-fix")
        fix_task = (
            task
            + "\n\nTEST OUTPUT:\n"
            + output
            + "\n\nReturn a git diff that fixes the failures."
        )
        generate_and_apply(fix_task)

        ok2, output2 = run_tests()
        if not ok2:
            raise RuntimeError("Tests still failing:\n" + output2)

    commit_all("bootstrap: core simulation scaffold")
    push_branch(branch)

    if args.pr:
        pr_url = create_pr(
            branch,
            "Bootstrap core simulation",
            "Automated bootstrap via local agent.\n\n"
            "How to verify:\n"
            "- dotnet test ./core/CoreSim.Tests/CoreSim.Tests.csproj\n",
        )
        print("PR created:", pr_url)
    else:
        print("Branch pushed:", branch)

# =========================

if __name__ == "__main__":
    main()
