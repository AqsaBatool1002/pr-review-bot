"""
PR Review Bot — Main Script
────────────────────────────
Triggered by GitHub Actions on every new or updated pull request.

Flow:
  1. Authenticate with GitHub via GITHUB_TOKEN
  2. Fetch the PR and its file diffs
  4. Post the structured review as a PR comment

Environment variables (injected by GitHub Actions):
  GITHUB_TOKEN       — auto-provided by Actions, no setup needed
  GITHUB_REPOSITORY  — "owner/repo", auto-provided by Actions
  GITHUB_PR_NUMBER   — PR number, injected from the workflow
  GROQ_API_KEY       — your Groq API key
"""

import os
import sys

from dotenv import load_dotenv
from github import Github, GithubException

from prompts import build_review_prompt, SYSTEM_PROMPT

# ── Load .env for local development (ignored when running in Actions) ────────
load_dotenv()


# ── Config ───────────────────────────────────────────────────────────────────
MAX_DIFF_CHARS = 6000      # keep well within LLM token limits
GROQ_MODEL     = "llama-3.3-70b-versatile"    # Primary Groq model


# ─────────────────────────────────────────────────────────────────────────────
# 1. Read environment variables
# ─────────────────────────────────────────────────────────────────────────────

def get_env(name: str, required: bool = True) -> str:
    """Read an env var; exit with a clear message if required and missing."""
    value = os.getenv(name, "").strip()
    if required and not value:
        print(f"[PR Review Bot] ❌  Missing required environment variable: {name}")
        sys.exit(1)
    return value


github_token    = get_env("GITHUB_TOKEN")
repo_name       = get_env("GITHUB_REPOSITORY")   # e.g. "alice/my-repo"
pr_number_str   = get_env("GITHUB_PR_NUMBER")
groq_api_key    = get_env("GROQ_API_KEY")

if not pr_number_str.isdigit():
    print(f"[PR Review Bot] ❌  GITHUB_PR_NUMBER is not a valid integer: '{pr_number_str}'")
    sys.exit(1)

pr_number = int(pr_number_str)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Authenticate with GitHub and fetch the PR
# ─────────────────────────────────────────────────────────────────────────────

print(f"[PR Review Bot] 🔗  Connecting to GitHub — repo: {repo_name}, PR: #{pr_number}")

try:
    gh   = Github(github_token)
    repo = gh.get_repo(repo_name)
    pr   = repo.get_pull(pr_number)
except GithubException as exc:
    print(f"[PR Review Bot] ❌  GitHub API error: {exc}")
    sys.exit(1)

print(f"[PR Review Bot] ✅  Fetched PR: \"{pr.title}\"")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Build the diff string from changed files
# ─────────────────────────────────────────────────────────────────────────────

def build_diff(pull_request) -> str:
    """
    Iterate over all files changed in the PR and concatenate their patches
    (the actual ±-line diffs).  Truncates to MAX_DIFF_CHARS characters.
    """
    parts = []

    try:
        files = pull_request.get_files()
    except GithubException as exc:
        print(f"[PR Review Bot] ❌  Could not fetch file list: {exc}")
        sys.exit(1)

    for f in files:
        patch = getattr(f, "patch", None)   # patch is None for binary files
        if patch:
            parts.append(f"### File: {f.filename}\n{patch}\n")

    full_diff = "\n".join(parts)

    if not full_diff.strip():
        return ""

    # Truncate and add a notice so the AI knows the diff was cut
    if len(full_diff) > MAX_DIFF_CHARS:
        full_diff = full_diff[:MAX_DIFF_CHARS]
        full_diff += "\n\n[... diff truncated to fit token limit ...]"

    return full_diff


diff = build_diff(pr)

# ── Early exit if there's nothing to review ──────────────────────────────────
if not diff:
    print("[PR Review Bot] ℹ️   No text diff found (binary-only changes or empty PR). Skipping review.")
    sys.exit(0)

print(f"[PR Review Bot] 📄  Diff collected — {len(diff)} characters across changed files")


# ─────────────────────────────────────────────────────────────────────────────
# 4. Call the AI — Groq
# ─────────────────────────────────────────────────────────────────────────────

def call_groq(api_key: str, diff_text: str) -> str:
    """
    Call Groq via its OpenAI-compatible endpoint.
    llama3-70b-8192: 14,400 requests/day on the free tier.
    """
    import httpx
    from openai import OpenAI

    # We use a custom httpx client to avoid the 'proxies' bug on some systems
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
        http_client=httpx.Client()
    )

    prompt = build_review_prompt(diff_text)

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        temperature=0.2,
        max_tokens=1500,
    )

    return response.choices[0].message.content.strip()


review_text = ""

try:
    print(f"[PR Review Bot] 🤖  Calling Groq API ({GROQ_MODEL}) …")
    review_text = call_groq(groq_api_key, diff)
    print("[PR Review Bot] ✅  Groq review received")
except Exception as exc:
    print(f"[PR Review Bot] ❌  Groq call failed: {exc}")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Post the review as a PR comment
# ─────────────────────────────────────────────────────────────────────────────

COMMENT_HEADER = (
    "## 🤖 AI Code Review\n\n"
    "> *Automated review powered by Groq · "
    "[PR Review Bot](https://github.com/marketplace)*\n\n"
    "---\n\n"
)

COMMENT_FOOTER = (
    "\n\n---\n"
    "*This review was generated automatically. Always verify suggestions before applying them.*"
)

full_comment = COMMENT_HEADER + review_text + COMMENT_FOOTER

try:
    pr.create_issue_comment(full_comment)
    print(f"[PR Review Bot] 🎉  Review posted successfully on PR #{pr_number}!")
except GithubException as exc:
    print(f"[PR Review Bot] ❌  Failed to post comment: {exc}")
    sys.exit(1)
