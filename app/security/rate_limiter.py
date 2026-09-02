import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class RequestInfo:
    """Information about a single request for rate limiting/spam detection."""
    timestamp: float
    agent_id: str
    user_id: str
    request_hash: str  # hash of the request (agent_id for now)


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    pass


class SpamDetected(Exception):
    """Raised when spam pattern is detected."""
    pass


class TemporarilyBlocked(Exception):
    """Raised when user/session is temporarily blocked."""
    pass


class RateLimiter:
    """
    Simple in-memory rate limiter with spam detection.
    
    Configuration:
    - max_requests_per_window: Max conversation-start requests per time window
    - window_seconds: Time window for rate limiting (seconds)
    - spam_threshold: Number of identical requests to trigger spam flag
    - spam_window_seconds: Time window for spam detection (seconds)
    - block_duration_seconds: How long to block after spam is detected
    """

    def __init__(
        self,
        max_requests_per_window: int = 5,
        window_seconds: int = 60,
        spam_threshold: int = 3,
        spam_window_seconds: int = 30,
        block_duration_seconds: int = 300,  # 5 minutes
    ):
        self.max_requests_per_window = max_requests_per_window
        self.window_seconds = window_seconds
        self.spam_threshold = spam_threshold
        self.spam_window_seconds = spam_window_seconds
        self.block_duration_seconds = block_duration_seconds

        # Track all requests per user_id
        self.user_requests: dict[str, list[RequestInfo]] = {}

        # Track blocked users and when block expires
        self.blocked_users: dict[str, float] = {}

    def check_and_record(
        self,
        user_id: str,
        agent_id: str,
    ) -> None:
        """
        Check if request should be allowed, record it if allowed.
        
        Raises:
            TemporarilyBlocked: If user is in cooldown period
            RateLimitExceeded: If user exceeded rate limit
            SpamDetected: If spam pattern detected
        """
        now = time.time()
        
        # Check if user is temporarily blocked
        if user_id in self.blocked_users:
            block_expiry = self.blocked_users[user_id]
            if now < block_expiry:
                remaining = int(block_expiry - now)
                raise TemporarilyBlocked(
                    f"Your request was temporarily blocked due to suspicious activity. "
                    f"Please try again in {remaining} seconds."
                )
            else:
                # Block expired, remove it
                del self.blocked_users[user_id]

        # Get user's recent requests (clean up old ones first)
        self._cleanup_old_requests(user_id, now)
        recent_requests = self.user_requests.get(user_id, [])

        # Check rate limit: requests in current time window
        requests_in_window = [
            r for r in recent_requests
            if now - r.timestamp < self.window_seconds
        ]

        if len(requests_in_window) >= self.max_requests_per_window:
            raise RateLimitExceeded(
                f"Too many conversation requests. Maximum {self.max_requests_per_window} "
                f"requests allowed per {self.window_seconds} seconds. Please wait a moment."
            )

        # Check spam: identical requests in spam window
        spam_window_start = now - self.spam_window_seconds
        identical_requests = [
            r for r in recent_requests
            if r.agent_id == agent_id and r.timestamp > spam_window_start
        ]

        if len(identical_requests) >= self.spam_threshold:
            # Block the user
            self.blocked_users[user_id] = now + self.block_duration_seconds
            raise SpamDetected(
                f"We detected suspicious activity on your account. "
                f"Please try again later."
            )

        # Record this request
        request_info = RequestInfo(
            timestamp=now,
            agent_id=agent_id,
            user_id=user_id,
            request_hash=agent_id,
        )

        if user_id not in self.user_requests:
            self.user_requests[user_id] = []

        self.user_requests[user_id].append(request_info)

    def _cleanup_old_requests(self, user_id: str, now: float) -> None:
        """Remove requests older than the longest tracking window."""
        if user_id not in self.user_requests:
            return

        # Keep requests from the longest window we care about
        # (max of rate limit window and spam window + block duration)
        max_age = max(self.window_seconds, self.spam_window_seconds) + self.block_duration_seconds

        self.user_requests[user_id] = [
            r for r in self.user_requests[user_id]
            if now - r.timestamp < max_age
        ]

        # Clean up empty user entries
        if not self.user_requests[user_id]:
            del self.user_requests[user_id]

    def cleanup_all(self, now: Optional[float] = None) -> None:
        """
        Periodic cleanup to free memory from old entries and expired blocks.
        Call this occasionally from your application (e.g., every 60 seconds).
        """
        if now is None:
            now = time.time()

        max_age = max(self.window_seconds, self.spam_window_seconds) + self.block_duration_seconds

        # Cleanup old requests
        users_to_remove = []
        for user_id, requests in self.user_requests.items():
            self.user_requests[user_id] = [
                r for r in requests
                if now - r.timestamp < max_age
            ]
            if not self.user_requests[user_id]:
                users_to_remove.append(user_id)

        for user_id in users_to_remove:
            del self.user_requests[user_id]

        # Cleanup expired blocks
        blocks_to_remove = []
        for user_id, block_expiry in self.blocked_users.items():
            if now >= block_expiry:
                blocks_to_remove.append(user_id)

        for user_id in blocks_to_remove:
            del self.blocked_users[user_id]
