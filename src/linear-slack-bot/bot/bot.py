# cspell:word dotenv
import json
import os
from pathlib import Path
from typing import Any
from typing import Dict
from typing import Optional

import boto3
from dotenv import load_dotenv
from gql import Client
from gql import gql
from gql.transport.requests import RequestsHTTPTransport
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from datetime import datetime, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass
import json
from operator import itemgetter

HEADER_EMOJI_COUNT = 5
SECTION_EMOJI_COUNT = 3

@dataclass
class Issue:
    title: str
    identifier: str
    assignee_email: str
    started_at: datetime
    completed_at: Optional[datetime] = None

    @property
    def duration(self) -> float:
        """Returns duration in days since started_at"""
        end = self.completed_at or datetime.now(timezone.utc)
        return (end - self.started_at).total_seconds() / 86400

# Helper function for determining medal based on rank with tie handling
def get_medal_for_rank(current_value: float, previous_value: Optional[float], rank: int) -> str:
    if previous_value is not None and current_value == previous_value:
        return get_medal_for_rank(current_value, None, rank - 1)
    if rank == 1:
        return " :first_place_medal:"
    elif rank == 2:
        return " :second_place_medal:"
    elif rank == 3:
        return " :third_place_medal:"
    return ""

class SlackBot:
    # Constants
    SLACK_BOT_TOKEN_ENV = "SLACK_BOT_TOKEN"
    LINEAR_API_TOKEN_ENV = "LINEAR_API_TOKEN"
    SLACK_SECRET_ID = "LINEAR_SLACK_BOT_TOKEN"
    LINEAR_SECRET_ID = "LINEAR_API_TOKEN"
    LINEAR_API_ENDPOINT = "https://api.linear.app/graphql"
    SECRETS_MANAGER_SERVICE = "secretsmanager"
    SECRET_STRING_KEY = "SecretString"

    def __init__(self, queries_dir: str = None):
        if queries_dir is None:
            # Get the bot.py directory.
            bot_dir = Path(__file__).parent
            # Go up one level and then to queries.
            self.queries_dir = bot_dir.parent / "queries"
        else:
            self.queries_dir = Path(queries_dir)

        self._queries: Dict[str, str] = {}

        # Load tokens.
        self._initialize_tokens()

        # Initialize clients.
        self.slack_client = WebClient(token=self.slack_token)
        self.gql_client = self._initialize_gql_client()

        # Load queries.
        self.load_queries()

        # Get Slack IDs.
        self.email_to_slack_id = {}
        self._cache_user_emails()

    def _initialize_tokens(self):
        """Initialize Slack and Linear tokens from env or AWS."""
        load_dotenv()
        self.slack_token = os.getenv(self.SLACK_BOT_TOKEN_ENV)
        self.linear_token = os.getenv(self.LINEAR_API_TOKEN_ENV)

        if not self.slack_token or not self.linear_token:
            try:
                session = boto3.session.Session()
                client = session.client(self.SECRETS_MANAGER_SERVICE)

                if not self.slack_token:
                    slack_response = client.get_secret_value(
                        SecretId=self.SLACK_SECRET_ID
                    )
                    self.slack_token = json.loads(
                        slack_response[self.SECRET_STRING_KEY]
                    )[self.SLACK_BOT_TOKEN_ENV]

                if not self.linear_token:
                    linear_response = client.get_secret_value(
                        SecretId=self.LINEAR_SECRET_ID
                    )
                    self.linear_token = json.loads(
                        linear_response[self.SECRET_STRING_KEY]
                    )[self.LINEAR_API_TOKEN_ENV]

            except Exception as e:
                print(f"Error getting AWS secrets: {e}")

        if not self.slack_token:
            raise ValueError("No Slack token found")
        if not self.linear_token:
            raise ValueError("No Linear API token found")

    def _cache_user_emails(self):
        """Cache mapping of email addresses to Slack user IDs."""
        try:
            response = self.slack_client.users_list()
            for user in response["members"]:
                if user.get("profile") and user["profile"].get("email"):
                    self.email_to_slack_id[user["profile"]["email"]] = user["id"]
        except SlackApiError as e:
            print(f"Error fetching users: {e.response['error']}")

    def _format_user_tag(self, email: str) -> str:
        """Convert email to Slack user tag if possible, otherwise return email."""
        slack_id = self.email_to_slack_id.get(email)
        if slack_id:
            return f"<@{slack_id}>"
        return email

    def _initialize_gql_client(self) -> Client:
        """Initialize the GraphQL client."""
        transport = RequestsHTTPTransport(
            url=self.LINEAR_API_ENDPOINT, headers={"Authorization": self.linear_token}
        )
        return Client(transport=transport, fetch_schema_from_transport=True)

    def load_queries(self) -> None:
        """Load all .graphql files from the queries directory."""
        for query_file in self.queries_dir.glob("*.graphql"):
            query_name = query_file.stem
            with open(query_file, "r") as f:
                self._queries[query_name] = f.read()

    def get_query(self, name: str) -> str:
        """Get a raw query string by name."""
        if name not in self._queries:
            raise KeyError(f"Query '{name}' not found")
        return self._queries[name]

    def execute_query(
        self, query_name: str, variables: Optional[Dict[str, Any]] = None
    ):
        """Execute a named GraphQL query with optional variables."""
        query = gql(self.get_query(query_name))
        return self.gql_client.execute(query, variable_values=variables)

    def send_message(self, channel: str = "#bot-test", text: str = "hello"):
        """Send a message to Slack."""
        try:
            response = self.slack_client.chat_postMessage(channel=channel, text=text)
            print(f"Message sent: {response['ts']}")
            return response
        except SlackApiError as e:
            print(f"Error: {e.response['error']}")
            raise e

    def reload_queries(self) -> None:
        """Reload all queries from disk."""
        self._queries.clear()
        self.load_queries()

    def parse_issues(self, started_data: Dict, completed_data: Dict) -> List[Issue]:
        issues = []

        # Parse started issues
        for node in started_data['issues']['nodes']:
            issues.append(Issue(
                title=node['title'],
                identifier=node['identifier'],
                assignee_email=node['assignee']['email'],
                started_at=datetime.fromisoformat(node['startedAt'].replace('Z', '+00:00')),
            ))

        # Parse completed issues
        for node in completed_data['issues']['nodes']:
            issues.append(Issue(
                title=node['title'],
                identifier=node['identifier'],
                assignee_email=node['assignee']['email'],
                started_at=datetime.fromisoformat(node['startedAt'].replace('Z', '+00:00')),
                completed_at=datetime.fromisoformat(node['completedAt'].replace('Z', '+00:00'))
            ))

        return issues

    def format_slack_message(self, started_data: Dict, completed_data: Dict) -> str:
        now = datetime.now(timezone.utc)
        completions_24h = {}
        in_progress_by_user = {}

        # Date header.
        header = f"{':bar_chart:' * HEADER_EMOJI_COUNT} *Linear summary {now.strftime('%Y-%m-%d')} *{':bar_chart:' * HEADER_EMOJI_COUNT}\n"
        message_parts = [header]
        message_parts.append("")

        message_parts.append(f"\n{':camera:' * SECTION_EMOJI_COUNT} *Global snapshot* {':camera:' * SECTION_EMOJI_COUNT}\n")
        message_parts.append("")

        issues = self.parse_issues(started_data, completed_data)
        for issue in issues:
            if issue.completed_at and (now - issue.completed_at).total_seconds() <= 86400:
                completions_24h[issue.assignee_email] = completions_24h.get(issue.assignee_email, 0) + 1
            if not issue.completed_at:
                if issue.assignee_email not in in_progress_by_user:
                    in_progress_by_user[issue.assignee_email] = {"count": 0, "time": 0.0}
                in_progress_by_user[issue.assignee_email]["count"] += 1
                in_progress_by_user[issue.assignee_email]["time"] += issue.duration

        # Recent completions.
        if completions_24h:
            message_parts.append("*Issues completed in last 24h:*")
            sorted_completions = sorted(completions_24h.items(), key=lambda x: (-x[1], x[0]))
            prev_count = None
            for idx, (email, count) in enumerate(sorted_completions, 1):
                medal = get_medal_for_rank(count, prev_count, idx)
                message_parts.append(f"{medal}*{self._format_user_tag(email)}* {''.join([':white_check_mark:'] * count)}")
                prev_count = count
            message_parts.append("")
        else:
            message_parts.append("*No issues closed in last 24h*\n")

        # In-progress issues.
        if in_progress_by_user:
            message_parts.append("*In-progress issues:*")
            sorted_users = sorted(in_progress_by_user.items(), key=lambda x: x[1]["time"])
            prev_time = None
            for idx, (email, stats) in enumerate(sorted_users, 1):
                medal = get_medal_for_rank(stats["time"], prev_time, idx)
                clock_emojis = ':clock4: ' * (int(stats["time"] / 3))
                message_parts.append(f"{medal} {self._format_user_tag(email)} : {stats['count']} issues ({stats['time']:.1f} days) {clock_emojis}")
                prev_time = stats["time"]
        else:
            message_parts.append("*No issues in progress*\n")

        message_parts.append("")
        message_parts.append(f"\n{':technologist:' * SECTION_EMOJI_COUNT} *By engineer* {':technologist:' * SECTION_EMOJI_COUNT}\n")
        message_parts.append("")

        # Group issues by assignee.
        issues_by_assignee: Dict[str, List[Issue]] = {}
        for issue in issues:
            if issue.assignee_email not in issues_by_assignee:
                issues_by_assignee[issue.assignee_email] = []
            issues_by_assignee[issue.assignee_email].append(issue)

        # Format message for each assignee
        assignee_info = []
        for email, assignee_issues in issues_by_assignee.items():
            completed_count = len([i for i in assignee_issues if i.completed_at])
            in_progress_duration = sum(i.duration for i in assignee_issues if not i.completed_at)
            assignee_info.append((email, assignee_issues, completed_count, in_progress_duration))

        # Sort by completed count descending, then by in_progress_duration ascending
        for email, assignee_issues, _, _ in sorted(assignee_info,
            key=lambda x: (-x[2], x[3])):  # -x[2] for descending completed count, x[3] for ascending duration
            message_parts.append(f"{self._format_user_tag(email)}:")

            completed = [i for i in assignee_issues if i.completed_at]
            completed.sort(key=lambda x: x.duration)

            if completed:
                message_parts.append("• *Completed issues:*")
                for idx, issue in enumerate(completed, 1):
                    days = issue.duration
                    duration = f"{days:.1f} days" if days >= 1 else f"{days*24:.1f} hours"
                    message_parts.append(f"   {idx}. {issue.identifier}: {issue.title} (took {duration}) :white_check_mark:")

            in_progress = [i for i in assignee_issues if not i.completed_at]
            in_progress.sort(key=lambda x: x.duration, reverse=True)

            if in_progress:
                message_parts.append("• *In-progress issues:*")
                for idx, issue in enumerate(in_progress, 1):
                    days = issue.duration
                    duration = f"{days:.1f} days" if days >= 1 else f"{days*24:.1f} hours"
                    clocks = ':clock4: ' * (int(issue.duration / 2))
                    message_parts.append(f"   {idx}. {issue.identifier}: {issue.title} (open {duration}) {clocks}")

            message_parts.append("")
            message_parts.append("")

        return "\n".join(message_parts)

    def send_formatted_status(self, channel: str = "#bot-test"):
        """Send formatted status message to Slack"""
        started_issues = self.execute_query("started-issues")
        recent_completions = self.execute_query("recent-completions")

        message = self.format_slack_message(started_issues, recent_completions)
        return self.send_message(channel=channel, text=message)


if __name__ == "__main__":
    bot = SlackBot()
    bot.send_formatted_status()
