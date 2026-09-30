import re
import requests
from typing import Dict, Any, List, Optional
from app.config import Config


class MattermostClient:
    MM_MAX_POST_LEN = 16000  # Mattermost limit is 16383

    def __init__(self, base_url: str = Config.MM_URL, token: str = Config.MM_TOKEN):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        })

    def request(self, method: str, path: str, json_data: Any = None, params: Dict[str, Any] = None) -> Any:
        url = f"{self.base_url}/api/v4{path}"
        response = self.session.request(method, url, json=json_data, params=params, timeout=30)
        if not response.ok:
            raise RuntimeError(f"Mattermost API {method} {path} failed ({response.status_code}): {response.text}")
        if response.content:
            return response.json()
        return None

    def get_me(self) -> Dict[str, Any]:
        """Retrieves authenticated user information."""
        return self.request("GET", "/users/me")

    def get_user(self, user_id: str) -> Dict[str, Any]:
        """Retrieves user profile by unique user ID."""
        return self.request("GET", f"/users/{user_id}")

    def find_channel_id(self, channel_name: str = Config.MM_CHANNEL_NAME, channel_id: str = Config.MM_CHANNEL_ID) -> str:
        """Finds channel ID by name across user's teams or returns explicit channel_id."""
        if channel_id:
            return channel_id

        teams = self.request("GET", "/users/me/teams") or []
        for team in teams:
            team_id = team.get("id")
            channels = self.request("GET", f"/users/me/teams/{team_id}/channels") or []
            for ch in channels:
                display_name = ch.get("display_name", "").strip().lower()
                name = ch.get("name", "").strip().lower()
                target = channel_name.strip().lower()
                if display_name == target or name == target:
                    return ch["id"]

        raise ValueError(f"Mattermost channel '{channel_name}' not found. Check MM_CHANNEL_NAME or set MM_CHANNEL_ID.")

    def get_posts_since(self, channel_id: str, since_ms: int) -> List[Dict[str, Any]]:
        """Fetches posts in the specified channel created or updated since since_ms."""
        data = self.request("GET", f"/channels/{channel_id}/posts", params={"since": since_ms}) or {}
        posts_map = data.get("posts", {})
        # Sort posts by creation timestamp ascending
        sorted_posts = sorted(posts_map.values(), key=lambda p: p.get("create_at", 0))
        return sorted_posts

    def reply_in_thread(self, channel_id: str, post: Dict[str, Any], message: str, dry_run: bool = False) -> Optional[Dict[str, Any]]:
        """Replies to a post within its thread."""
        root_id = post.get("root_id") or post.get("id")
        if len(message) > self.MM_MAX_POST_LEN:
            message = message[:self.MM_MAX_POST_LEN] + "\n\n...(truncated due to Mattermost length limit)"

        if dry_run:
            print(f"\n[DRY RUN] Would post reply to thread {root_id}:\n{'-'*60}\n{message}\n{'-'*60}\n")
            return {"id": "dry-run-post-id", "root_id": root_id, "message": message}

        payload = {
            "channel_id": channel_id,
            "root_id": root_id,
            "message": message
        }
        return self.request("POST", "/posts", json_data=payload)

    @staticmethod
    def build_mention_regex(username: str) -> re.Pattern:
        """Constructs an exact-word mention regex for @username or multiple comma-separated usernames."""
        parts = [u.strip().lstrip("@") for u in username.split(",") if u.strip()]
        expanded = set(parts)
        for p in list(parts):
            # Auto-expand known aliases / variations for mayank.kumar
            if "mayank" in p.lower():
                expanded.add("mayank.kumar")
                expanded.add("mayank.kumar1")
                expanded.add("Mayank Kumar")
                expanded.add("Mayank.Kumar")
                expanded.add("mayank")

        escaped = [re.escape(x) for x in expanded]
        pattern = f"(?:{'|'.join(escaped)})"
        return re.compile(rf"(?<![\w.\-])@{pattern}(?![\w\-]|\.\w)", re.IGNORECASE)
