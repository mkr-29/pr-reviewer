# Mattermost PR/MR Automated Reviewer 🤖

An automated service that scans the Mattermost **"Daily Task Update"** channel for merge/pull requests sent to you, verifies target branch rules, performs in-depth AI code reviews using the `pr-review` rubric, and posts structured review outcomes directly back into the message thread.

---

## 🌟 Key Features

1. **Daily 8:00 PM Automation**:
   - Runs automatically every evening at **8:00 PM (20:00)** in your configured timezone (`Asia/Kolkata` by default).
   - Also supports on-demand immediate execution via `--now` and simulated testing via `--dry-run`.
2. **Channel & Tag Monitoring**:
   - Monitors the channel named `Daily Task Update`.
   - Filters only posts that `@mention` you and contain Merge Request (GitLab) or Pull Request (GitHub) links.
3. **`pre-main` Target Branch Gate**:
   - Verifies target/base branch before initiating review.
   - **Target != `pre-main`**: Immediately sends a thread reply asking the author to retarget the PR to `pre-main`.
   - **Target == `pre-main`**: Fetches the unified diff and proceeds to the full review.
4. **Rigorous Review Engine (`pr-review` / `mr-review-gitlab` rubric)**:
   - Evaluates:
     - **Task Completeness**: Compares code changes against issue requirements; catches scope creep.
     - **Test Coverage**: Verifies tests for modified logic; flags deleted or weakened tests.
     - **Implementation Quality**: Edge cases, error handling, null safety, resource cleanup, conventions.
     - **Hard Gates**: CI pipeline status, draft state, merge conflicts.
     - **Verdict Scale**: `🟢 GOOD` (mergeable), `🟡 AVERAGE` (needs revisions), `🔴 BAD — BLOCK` (blocking issues).
5. **Multi-LLM Flexibility**:
   - Configurable in `.env` to use **Google Gemini API**, **Anthropic Claude API**, or **Cursor / OpenAI-compatible API**.
6. **Thread Replies**:
   - Posts the outcome directly as a threaded reply to the sender's original message.
7. **Idempotency & State Persistence**:
   - Tracks processed `(post_id, url)` pairs in `data/state.json`. Never re-reviews the same post twice.

---

## 📋 Prerequisites

- **Mattermost**: Personal Access Token (PAT) or Bot Token with permissions to read channels and post messages.
- **Git Provider**:
  - GitLab Personal Access Token (`read_api` scope) if using GitLab.
  - GitHub Personal Access Token (`repo` scope) if using GitHub.
- **LLM API Key**: At least one of `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, or `OPENAI_API_KEY` / `CURSOR_API_KEY`.
- **Docker & Docker Compose** (for running on your dev server or containerized).

---

## 🚀 Quick Start (Local Development)

### 1. Set Up Environment
```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure `.env`
```bash
cp .env.example .env
# Edit .env and enter your Mattermost URL, Token, Git Tokens, and LLM Key
```

### 3. Run Automated Tests
```bash
pytest tests/
```

### 4. Test Single Run (Dry-run mode)
```bash
# Simulates scanning and printing replies to console without modifying Mattermost or state
python3 main.py --now --dry-run
```

### 5. Run Immediate Live Review
```bash
python3 main.py --now
```

### 6. Run Scheduler Daemon
```bash
# Runs continuously, firing daily at 20:00 (8:00 PM)
python3 main.py
```

---

## 🐳 Docker Setup

The easiest way to run the service 24/7 on your machine or dev server is with Docker Compose.

### 1. Build and Run Container
```bash
docker compose up -d --build
```

### 2. View Logs
```bash
docker compose logs -f
```

### 3. Trigger an On-Demand Review Inside Docker
```bash
docker compose run --rm reviewer python3 main.py --now
```

### 4. Stop Container
```bash
docker compose down
```

---

## 🖥️ Deploying to Your Dev Server via SSH

When ready to deploy on your remote dev server:

### Option A: Transfer and Deploy with `rsync` / `scp`
```bash
# 1. From your local machine, copy the folder to your dev server:
rsync -avz --exclude '.venv' --exclude 'data' --exclude '__pycache__' \
  ./ user@<DEV_SERVER_IP>:/home/user/pr-reviewer

# 2. SSH into your dev server:
ssh user@<DEV_SERVER_IP>

# 3. Enter directory and set up .env:
cd /home/user/pr-reviewer
cp .env.example .env
nano .env  # paste your tokens

# 4. Start the Docker container in the background:
docker compose up -d --build
```

### Option B: Provide Dev Server SSH Details to Agent
Alternatively, you can provide the SSH host/IP, username, and key/password in this conversation, and I will connect and set up the Docker container for you!

---

## 📁 Repository Structure

```
pr-reviewer/
├── app/
│   ├── config.py              # Environment configuration & validation
│   ├── mattermost.py          # Mattermost client (posts, threads, mentions)
│   ├── state.py               # JSON state persistence (tracks processed posts)
│   ├── git_providers/
│   │   ├── base.py            # Normalized PR/MR dataclass
│   │   ├── gitlab_client.py   # GitLab REST API client (branch check & diff fetcher)
│   │   ├── github_client.py   # GitHub REST API client (branch check & diff fetcher)
│   │   └── resolver.py        # URL extractor and provider router
│   ├── reviewer/
│   │   ├── rubric.py          # pr-review rubric, criteria, and prompt builder
│   │   └── llm.py             # Multi-backend LLM client (Gemini, Claude, Cursor/OpenAI)
│   └── bot.py                 # Core workflow orchestrator
├── main.py                    # Entrypoint & 8:00 PM daily scheduler
├── Dockerfile                 # Multi-stage lightweight Python 3.12-slim container
├── docker-compose.yml         # Compose configuration with persistent volume
├── requirements.txt           # Python dependencies
├── .env.example               # Environment variables template
├── pytest.ini                 # Test configuration
└── tests/                     # Unit tests for parsers, branch gate, and state
```
