# 🤖 PR Review Bot

> An AI-powered GitHub bot that automatically reviews every pull request — catching bugs, security issues, readability problems, and missing error handling — and posts a structured comment directly on the PR.

---

## ✨ What it does

Every time a PR is **opened or updated**, the bot:

1. Reads all changed files in the PR
2. Extracts the git diff (the actual ±-lines)
3. Sends the diff to **Groq**
4. Posts a structured review comment like this:

```
## 🤖 AI Code Review

## 🐛 BUGS
- **File**: auth.py | **Line**: 42
  **Problem**: No try/except around the API call. If the request fails, the server crashes.
  **Fix**: Wrap in `try/except requests.RequestException as e: logger.error(e); return None`

## 🔒 SECURITY
- **File**: config.py | **Line**: 18
  **Problem**: API key hardcoded in source code.
  **Fix**: Move to environment variable → `os.getenv("API_KEY")`

## 📖 READABILITY
- **File**: utils.py | **Line**: 31
  **Problem**: Variable name `x` is meaningless.
  **Fix**: Rename to `user_count` to reflect its purpose.

## ⚠️ MISSING ERROR HANDLING
No issues found.
```

---

## 🧰 Tech Stack

| Tool | Purpose | Cost |
|---|---|---|
| **Python 3.11** | Runtime | Free |
| **GitHub Actions** | CI runner that triggers the bot | Free |
| **Groq** (`llama-3.3-70b-versatile`) | AI code reviewer | Free — 14,400 req/day |
| **PyGithub** | GitHub API client | Free |
| **openai** (Python lib) | OpenAI-compatible client for Groq | Free |
| **python-dotenv** | Loads `.env` for local dev | Free |

---

## 📁 Project Structure

```
pr-review-bot/
├── .github/
│   └── workflows/
│       └── pr-review.yml      ← GitHub Actions workflow
├── scripts/
│   ├── review_pr.py           ← Main script
│   └── prompts.py             ← AI prompt templates
├── requirements.txt
├── .env.example               ← Config template (copy → .env)
├── .gitignore
└── README.md
```

---

## 🚀 Setup Guide (5 minutes)

### Step 1 — Get your free Groq API key

1. Go to **https://console.groq.com**
2. Sign up with GitHub or Google (no credit card needed)
3. Navigate to **API Keys → Create API Key**
4. Copy the key — you'll need it in Step 3

---

### Step 2 — Fork or create the repository

```bash
# Clone this repo
git clone https://github.com/YOUR_USERNAME/pr-review-bot.git
cd pr-review-bot
```

Or create a new GitHub repository and push this project to it.

---

### Step 3 — Add secrets to GitHub

In your GitHub repository:

1. Go to **Settings → Secrets and variables → Actions**
2. Click **"New repository secret"** and add:

| Secret Name | Value |
|---|---|
| `GROQ_API_KEY` | Your Groq API key from Step 1 |

> ⚠️ `GITHUB_TOKEN` is **automatically provided** by GitHub Actions — you do NOT need to add it manually.

---

### Step 4 — Test it!

1. Create a new branch in your repository
2. Make any code change (even a small one)
3. Open a Pull Request
4. Watch the **Actions** tab — the bot will run within seconds
5. Check the PR — the review comment will appear automatically 🎉

---

## 💻 Local Development & Testing

```bash
# 1. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up your local config
cp .env.example .env
# Edit .env and fill in your API keys

# 4. Run the script against a real PR
# Make sure GITHUB_REPOSITORY and GITHUB_PR_NUMBER are set in your .env
python scripts/review_pr.py
```

Your `.env` should look like this for local testing:
```env
GROQ_API_KEY=gsk_...
GITHUB_TOKEN=ghp_...
GITHUB_REPOSITORY=alice/my-repo
GITHUB_PR_NUMBER=5
```

---

## ❌ Top 3 Errors Beginners Hit (and how to fix them)

### Error 1 — `Resource not accessible by integration`

```
GithubException: 403 {"message": "Resource not accessible by integration"}
```

**Cause:** The GitHub Actions workflow is missing the `permissions` block, so it doesn't have write access to post PR comments.

**Fix:** Make sure your `pr-review.yml` has this at the top level (already included in this project):
```yaml
permissions:
  pull-requests: write
  contents: read
```

---

### Error 2 — `GROQ_API_KEY` not found / `AuthenticationError`

```
[PR Review Bot] ❌ Missing required environment variable: GROQ_API_KEY
# or
openai.AuthenticationError: 401 Incorrect API key provided
```

**Cause:** The secret wasn't added to GitHub, or the secret name doesn't match exactly.

**Fix:**
1. Go to **GitHub repo → Settings → Secrets → Actions**
2. Verify the secret is named **exactly** `GROQ_API_KEY` (case-sensitive)
3. Re-run the failed workflow from the Actions tab

---

### Error 3 — The bot runs but posts no comment / empty diff

```
[PR Review Bot] ℹ️ No text diff found (binary-only changes or empty PR). Skipping review.
```

**Cause:** Either the PR only contains binary file changes (images, compiled files), or the branch has no commits ahead of the base branch.

**Fix:**
1. Make sure your PR branch has actual text file changes
2. If testing locally, verify `GITHUB_PR_NUMBER` points to a PR that has code changes
3. Check the Actions log — `📄 Diff collected — X characters` should appear if the diff was found

---

## 🔧 Configuration

You can tune the bot's behaviour by editing these values in `scripts/review_pr.py`:

| Variable | Default | Description |
|---|---|---|
| `MAX_DIFF_CHARS` | `6000` | Max characters of diff sent to AI (increase if you have a large context model) |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model to use |

And in `scripts/prompts.py` you can freely edit `SYSTEM_PROMPT` to change the review style, add/remove sections, or make the tone stricter/friendlier.

---

## 📊 Free Tier Limits

| Provider | Daily Limit | Per-Minute Limit | Context Window |
|---|---|---|---|
| Groq (llama-3.3-70b) | 14,400 requests | 30 RPM | 8,192 tokens |

For most projects, Groq's free tier is more than enough. A typical PR review uses 1 request.

---

## 🛡️ Security Notes

- **Never commit your `.env` file** — it's in `.gitignore`
- `GITHUB_TOKEN` is scoped to the current repo and expires after each workflow run
- The bot only **reads** PR diffs and **writes** comments — it cannot push code or modify branches
- Your diff is sent to Groq servers — don't use this on repos with highly sensitive IP until you review their data policies

---

## 📄 License

MIT — do whatever you want with it.
# Testing bot
