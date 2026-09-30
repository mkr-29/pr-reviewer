import sys
import time
from typing import Optional
from app.config import Config
from app.state import StateManager
from app.mattermost import MattermostClient
from app.git_providers.resolver import GitResolver
from app.reviewer.llm import LLMReviewer


def log(msg: str):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {msg}", file=sys.stderr, flush=True)


class PRReviewBot:
    def __init__(
        self,
        mm_client: Optional[MattermostClient] = None,
        state_manager: Optional[StateManager] = None,
        git_resolver: Optional[GitResolver] = None,
        reviewer: Optional[LLMReviewer] = None,
        dry_run: bool = False,
        target_username: Optional[str] = None
    ):
        self.dry_run = dry_run
        self.mm = mm_client or MattermostClient()
        self.state_manager = state_manager or StateManager()
        self.git_resolver = git_resolver or GitResolver()
        self.reviewer = reviewer if reviewer is not None else (None if dry_run else LLMReviewer())
        self.target_username = target_username or Config.MM_TARGET_USERNAME

    def run_once(self):
        """Executes a single scan-and-review cycle across the Daily Task Update channel."""
        log("Starting PR/MR review scan cycle...")

        if not self.mm.base_url or not self.mm.token:
            log("Configuration notice: MM_URL and MM_TOKEN are required in .env to connect to Mattermost.")
            if self.dry_run:
                log("[DRY RUN] Skipping live Mattermost scan because MM_URL / MM_TOKEN are not configured in .env.")
                log("[DRY RUN] Simulation complete. To run against a live server, configure your .env file.")
                return
            raise ValueError("MM_URL and MM_TOKEN must be set in .env")

        me = self.mm.get_me()
        my_username = me.get("username", "")
        my_id = me.get("id", "")

        # Resolve all target usernames and names dynamically from user IDs and profiles
        target_names = set()
        if isinstance(my_username, str) and my_username.strip():
            target_names.add(my_username.strip())
        first_name = me.get("first_name", "")
        last_name = me.get("last_name", "")
        if isinstance(first_name, str) and isinstance(last_name, str) and first_name and last_name:
            target_names.add(f"{first_name.strip()} {last_name.strip()}")

        # Query Mattermost by unique user ID for any configured target accounts
        if Config.MM_TARGET_USER_IDS:
            for uid in Config.MM_TARGET_USER_IDS.split(","):
                uid = uid.strip()
                if uid and uid != my_id:
                    try:
                        u_profile = self.mm.get_user(uid)
                        if isinstance(u_profile, dict):
                            uname = u_profile.get("username")
                            if isinstance(uname, str) and uname.strip():
                                target_names.add(uname.strip())
                            fn = u_profile.get("first_name", "")
                            ln = u_profile.get("last_name", "")
                            if isinstance(fn, str) and isinstance(ln, str) and fn and ln:
                                target_names.add(f"{fn.strip()} {ln.strip()}")
                    except Exception as e:
                        log(f"Notice: could not resolve user ID '{uid}': {e}")

        if self.target_username:
            for item in self.target_username.split(","):
                item_str = str(item).strip().lstrip("@")
                if item_str:
                    target_names.add(item_str)

        target_pattern = ",".join(sorted(str(s) for s in target_names))
        mention_re = self.mm.build_mention_regex(target_pattern)

        channel_id = self.mm.find_channel_id()
        state = self.state_manager.load()
        done = set(state.get("done", []))
        run_started = int(time.time() * 1000)

        log(f"Authenticated as @{my_username} (ID: {my_id}) | Monitoring mentions for: {target_pattern}")
        log(f"Scanning channel '{Config.MM_CHANNEL_NAME}' (ID: {channel_id}) since {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(state['last_run_ms'] / 1000))}")

        posts = self.mm.get_posts_since(channel_id, state["last_run_ms"])
        log(f"Retrieved {len(posts)} new or updated posts since last run")

        processed_count = 0

        for post in posts:
            if post.get("delete_at", 0) > 0:
                continue

            msg = post.get("message", "")
            # Avoid feedback loops: skip automated replies posted by the bot itself
            if post.get("user_id") == my_id and (
                msg.startswith(":warning:") or msg.startswith("**Automated review for**")
            ):
                continue

            if not mention_re.search(msg):
                continue  # Post does not tag the user

            pr_urls = self.git_resolver.extract_pr_urls(msg)
            if not pr_urls:
                continue

            # If REPO_FILTER is configured (e.g. 'backend'), only review matching URLs
            if Config.REPO_FILTER:
                filtered_urls = [u for u in pr_urls if Config.REPO_FILTER in u.lower()]
                if not filtered_urls:
                    log(f"Skipping post {post['id']}: no PR/MR URLs match REPO_FILTER='{Config.REPO_FILTER}'")
                    continue
                pr_urls = filtered_urls

            for url in pr_urls:
                key = self.state_manager.make_key(post["id"], url)
                if key in done:
                    continue

                # Check if this thread already has an automated response for this URL
                if not self.dry_run and self.mm.has_bot_replied_for_url(post, url):
                    log(f"Skipping {url}: thread for post {post['id']} already contains a bot reply.")
                    done.add(key)
                    self.state_manager.record_reviewed(state, post["id"], url, status="already_replied_in_thread")
                    self.state_manager.save(state, dry_run=self.dry_run)
                    continue

                log(f"Found candidate: {url} from post {post['id']}")
                try:
                    pr = self.git_resolver.get_details(url)

                    # Deduplication: Skip if this MR at this commit SHA has already been reviewed by the bot
                    if self.state_manager.is_url_reviewed(state, url, pr.head_sha):
                        sha_label = pr.head_sha[:8] if pr.head_sha else "HEAD"
                        log(f"Skipping {url}: already reviewed by bot at commit {sha_label}.")
                        done.add(key)
                        self.state_manager.save(state, dry_run=self.dry_run)
                        continue

                    is_valid_branch, actual_branch = self.git_resolver.validate_target_branch(pr, Config.TARGET_BRANCH)

                    # If open MR targets the wrong branch, post a warning so author can retarget before merging
                    if not is_valid_branch and pr.is_open:
                        log(f"Branch mismatch: {url} targets '{actual_branch}' (expected '{Config.TARGET_BRANCH}')")
                        warning_msg = (
                            f":warning: {url} targets `{actual_branch}`, not `{Config.TARGET_BRANCH}`. "
                            f"Please retarget it to `{Config.TARGET_BRANCH}` and re-share for review."
                        )
                        self.mm.reply_in_thread(channel_id, post, warning_msg, dry_run=self.dry_run)
                        self.state_manager.record_reviewed(state, post["id"], url, head_sha=pr.head_sha, status="warned_branch")
                    else:
                        # Proceed with full review (open MR on valid branch, or already merged/approved MR)
                        if pr.state == "merged":
                            log(f"MR {url} is merged into '{actual_branch}'. Executing review on merged code...")
                        else:
                            log(f"Target branch '{actual_branch}' verified. Running automated review for {url}...")

                        if self.dry_run and not self.reviewer:
                            review_output = f"[Simulated Review: pr-review rubric applied to {url} with diff length {len(pr.diff)} chars]"
                        else:
                            if not self.reviewer:
                                self.reviewer = LLMReviewer()
                            review_output = self.reviewer.review_pr(pr)

                        header_notes = []
                        if pr.state == "merged":
                            header_notes.append("*(Note: MR is already merged)*")
                        if pr.is_approved:
                            header_notes.append("*(Note: MR is already approved on Git)*")
                        if not is_valid_branch:
                            header_notes.append(f"*(Note: target branch is `{actual_branch}`, expected `{Config.TARGET_BRANCH}`)*")

                        extra_header = f" {' '.join(header_notes)}\n\n" if header_notes else "\n\n"
                        reply_msg = f"**Automated review for** {url}{extra_header}{review_output}"
                        self.mm.reply_in_thread(channel_id, post, reply_msg, dry_run=self.dry_run)
                        self.state_manager.record_reviewed(state, post["id"], url, head_sha=pr.head_sha, status="reviewed")

                    done.add(key)
                    self.state_manager.save(state, dry_run=self.dry_run)
                    processed_count += 1

                except Exception as e:
                    # Leave unprocessed so next run retries, as designed in reference bot
                    log(f"ERROR processing {url}: {e}")

        # Set last_run_ms with 1 min overlap for safety
        state["last_run_ms"] = run_started - 60_000
        self.state_manager.save(state, dry_run=self.dry_run)
        log(f"Cycle completed. Successfully processed {processed_count} PR/MR(s).")
