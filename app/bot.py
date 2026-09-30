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
        dry_run: bool = False
    ):
        self.dry_run = dry_run
        self.mm = mm_client or MattermostClient()
        self.state_manager = state_manager or StateManager()
        self.git_resolver = git_resolver or GitResolver()
        self.reviewer = reviewer if reviewer is not None else (None if dry_run else LLMReviewer())

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
        mention_re = self.mm.build_mention_regex(my_username)

        channel_id = self.mm.find_channel_id()
        state = self.state_manager.load()
        done = set(state.get("done", []))
        run_started = int(time.time() * 1000)

        log(f"Authenticated as @{my_username} (ID: {my_id})")
        log(f"Scanning channel '{Config.MM_CHANNEL_NAME}' (ID: {channel_id}) since {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(state['last_run_ms'] / 1000))}")

        posts = self.mm.get_posts_since(channel_id, state["last_run_ms"])
        log(f"Retrieved {len(posts)} new or updated posts since last run")

        processed_count = 0

        for post in posts:
            if post.get("delete_at", 0) > 0 or post.get("user_id") == my_id:
                continue  # Skip deleted posts and bot's own replies

            msg = post.get("message", "")
            if not mention_re.search(msg):
                continue  # Post does not tag the user

            pr_urls = self.git_resolver.extract_pr_urls(msg)
            if not pr_urls:
                continue

            for url in pr_urls:
                key = self.state_manager.make_key(post["id"], url)
                if key in done:
                    continue

                log(f"Found candidate: {url} from post {post['id']}")
                try:
                    pr = self.git_resolver.get_details(url)
                    is_valid_branch, actual_branch = self.git_resolver.validate_target_branch(pr, Config.TARGET_BRANCH)

                    if not is_valid_branch:
                        log(f"Branch mismatch: {url} targets '{actual_branch}' (expected '{Config.TARGET_BRANCH}')")
                        warning_msg = (
                            f":warning: {url} targets `{actual_branch}`, not `{Config.TARGET_BRANCH}`. "
                            f"Please retarget it to `{Config.TARGET_BRANCH}` and re-share for review."
                        )
                        self.mm.reply_in_thread(channel_id, post, warning_msg, dry_run=self.dry_run)
                    else:
                        log(f"Target branch '{Config.TARGET_BRANCH}' verified. Running automated review for {url}...")
                        if self.dry_run and not self.reviewer:
                            review_output = f"[Simulated Review: pr-review rubric applied to {url} with diff length {len(pr.diff)} chars]"
                        else:
                            if not self.reviewer:
                                self.reviewer = LLMReviewer()
                            review_output = self.reviewer.review_pr(pr)

                        reply_msg = f"**Automated review for** {url}\n\n{review_output}"
                        self.mm.reply_in_thread(channel_id, post, reply_msg, dry_run=self.dry_run)

                    done.add(key)
                    state["done"].append(key)
                    self.state_manager.save(state, dry_run=self.dry_run)
                    processed_count += 1

                except Exception as e:
                    # Leave unprocessed so next run retries, as designed in reference bot
                    log(f"ERROR processing {url}: {e}")

        # Set last_run_ms with 1 min overlap for safety
        state["last_run_ms"] = run_started - 60_000
        self.state_manager.save(state, dry_run=self.dry_run)
        log(f"Cycle completed. Successfully processed {processed_count} PR/MR(s).")
