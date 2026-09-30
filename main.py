#!/usr/bin/env python3
"""
Mattermost PR/MR Review Automation Entrypoint.

Usage:
    python3 main.py               # Runs in scheduler daemon mode (everyday at 8:00 PM)
    python3 main.py --now         # Runs one review cycle immediately and exits
    python3 main.py --now --dry-run # Runs one cycle in simulation mode without posting replies
"""

import sys
import time
import signal
import argparse
from datetime import datetime
import pytz
import schedule

from app.config import Config
from app.bot import PRReviewBot, log


def run_job(dry_run: bool = False):
    try:
        bot = PRReviewBot(dry_run=dry_run)
        bot.run_once()
    except Exception as e:
        log(f"Fatal error during review cycle: {e}")


def main():
    parser = argparse.ArgumentParser(description="Mattermost PR/MR Automated Reviewer")
    parser.add_argument("--now", action="store_true", help="Run a review cycle immediately and exit")
    parser.add_argument("--dry-run", action="store_true", help="Print thread replies instead of posting them to Mattermost")
    args = parser.parse_args()

    if not args.dry_run:
        try:
            Config.validate_for_live_run()
        except ValueError as e:
            if not args.now:
                log(f"Config Validation Warning: {e}")
            else:
                log(f"Configuration error: {e}")
                sys.exit(1)

    if args.now:
        log(f"Executing immediate run (dry_run={args.dry_run})...")
        run_job(dry_run=args.dry_run)
        sys.exit(0)

    # Daemon scheduler mode (Everyday at 8:00 PM / SCHEDULE_TIME)
    target_time = Config.SCHEDULE_TIME
    tz_name = Config.SCHEDULE_TIMEZONE
    try:
        local_tz = pytz.timezone(tz_name)
    except Exception:
        local_tz = pytz.timezone("Asia/Kolkata")
        tz_name = "Asia/Kolkata"

    log(f"PR Reviewer daemon initialized.")
    log(f"Daily schedule target: Everyday at {target_time} ({tz_name})")
    log("Running scheduler loop. Press Ctrl+C to stop.")

    def handle_exit(signum, frame):
        log("Received termination signal. Exiting scheduler gracefully.")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    # To ensure accurate timezone scheduling regardless of host machine system clock timezone:
    schedule.every().day.at(target_time).do(run_job, dry_run=args.dry_run)

    while True:
        # Check current time in target timezone
        now_in_tz = datetime.now(local_tz)
        current_time_str = now_in_tz.strftime("%H:%M")

        # When the minute strikes SCHEDULE_TIME and hasn't run this minute, run job
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
