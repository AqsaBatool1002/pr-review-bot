"""
PR Review Bot — Main Script
────────────────────────────
Triggered by GitHub Actions on every new or updated pull request.

Flow:
  1. Authenticate with GitHub via GITHUB_TOKEN
  2. Fetch the PR and its file diffs
  3. Send the diff to an AI (Gemini primary, Groq fallback)
  4. Post the structured review as a PR comment

Environment variables (injected by GitHub Actions):
  GITHUB_TOKEN       — auto-provided by Actions, no setup needed
  GITHUB_REPOSITORY  — "owner/repo", auto-provided by Actions
  GITHUB_PR_NUMBER   — PR number, injected from the workflow
  GEMINI_API_KEY     — your Google Gemini API key (free tier)
  GROQ_API_KEY       — optional Groq API key (fallback)
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
GEMINI_MODEL   = "gemini-2.0-flash"   # free, fast, 1M context window
GROQ_MODEL     = "llama3-70b-8192"    # Groq fallback


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
gemini_api_key  = get_env("GEMINI_API_KEY", required=False)
groq_api_key    = get_env("GROQ_API_KEY",   required=False)

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
# 4. Call the AI — Gemini primary, Groq fallback
# ─────────────────────────────────────────────────────────────────────────────

def call_gemini(api_key: str, diff_text: str) -> str:
    """
    Call Google Gemini via the openai-compatible endpoint.
    Gemini Flash is free up to 1,500 requests/day with a 1M-token context.
    Endpoint: https://generativelanguage.googleapis.com/v1beta/openai/
    """
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )

    prompt = build_review_prompt(diff_text)

    response = client.chat.completions.create(
        model=GEMINI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        temperature=0.2,          # low temp = more focused, reproducible reviews
        max_tokens=1500,
    )

    return response.choices[0].message.content.strip()


def call_groq(api_key: str, diff_text: str) -> str:
    """
    Call Groq via its OpenAI-compatible endpoint.
    llama3-70b-8192: 14,400 requests/day on the free tier.
    """
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
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

if gemini_api_key:
    try:
        print("[PR Review Bot] 🤖  Calling Gemini API (gemini-2.0-flash) …")
        review_text = call_gemini(gemini_api_key, diff)
        print("[PR Review Bot] ✅  Gemini review received")
    except Exception as exc:
        print(f"[PR Review Bot] ⚠️   Gemini call failed ({exc}), trying Groq …")

if not review_text and groq_api_key:
    try:
        print("[PR Review Bot] 🤖  Calling Groq API (llama3-70b-8192) …")
        review_text = call_groq(groq_api_key, diff)
        print("[PR Review Bot] ✅  Groq review received")
    except Exception as exc:
        print(f"[PR Review Bot] ❌  Groq call also failed: {exc}")

if not review_text:
    print("[PR Review Bot] ❌  No AI response received. Check your API keys.")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Post the review as a PR comment
# ─────────────────────────────────────────────────────────────────────────────

COMMENT_HEADER = (
    "## 🤖 AI Code Review\n\n"
    "> *Automated review powered by Google Gemini · "
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
