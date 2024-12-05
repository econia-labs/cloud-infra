# cspell:word dotenv
import json
import os

import boto3
import requests
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Constants.
SLACK_BOT_TOKEN_ENV = "SLACK_BOT_TOKEN"
LINEAR_API_TOKEN_ENV = "LINEAR_API_TOKEN"
SLACK_SECRET_ID = "LINEAR_SLACK_BOT_TOKEN"
LINEAR_SECRET_ID = "LINEAR_API_TOKEN"
LINEAR_API_ENDPOINT = "https://api.linear.app/graphql"
CONTENT_TYPE_JSON = "application/json"


class SlackBot:
    def __init__(self):
        # Try local .env file first.
        load_dotenv()
        slack_token = os.getenv(SLACK_BOT_TOKEN_ENV)
        linear_token = os.getenv(LINEAR_API_TOKEN_ENV)

        # If no local tokens, try AWS Secrets Manager.
        if not slack_token or not linear_token:
            try:
                session = boto3.session.Session()
                client = session.client("secretsmanager")

                # Get Slack token if needed
                if not slack_token:
                    slack_response = client.get_secret_value(
                        SecretId=SLACK_SECRET_ID
                    )
                    slack_token = json.loads(slack_response["SecretString"])[
                        SLACK_BOT_TOKEN_ENV
                    ]

                # Get Linear token if needed
                if not linear_token:
                    linear_response = client.get_secret_value(
                        SecretId=LINEAR_SECRET_ID
                    )
                    linear_token = json.loads(linear_response["SecretString"])[
                        LINEAR_API_TOKEN_ENV
                    ]

            except Exception as e:
                print(f"Error getting AWS secrets: {e}")

        if not slack_token:
            raise ValueError("No Slack token found")

        if not linear_token:
            raise ValueError("No Linear API token found")

        self.slack_client = WebClient(token=slack_token)
        self.linear_headers = {
            "Authorization": linear_token,
            "Content-Type": CONTENT_TYPE_JSON,
        }
        self.linear_endpoint = LINEAR_API_ENDPOINT

    def send_message(self, channel="#bot-test", text="hello"):
        """Send a message to Slack."""
        try:
            response = self.slack_client.chat_postMessage(
                channel=channel, text=text
            )
            print(f"Message sent: {response['ts']}")
            return response
        except SlackApiError as e:
            print(f"Error: {e.response['error']}")
            raise e

    def query_linear(self, query, variables=None):
        """Send a GraphQL query to Linear API."""
        try:
            response = requests.post(
                self.linear_endpoint,
                headers=self.linear_headers,
                json={"query": query, "variables": variables},
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error querying Linear API: {e}")
            raise e

    def get_linear_schema(self):
        """Query the Linear GraphQL API for its introspection schema."""
        introspection_query = """
        query IntrospectionQuery {
          __schema {
            types {
              name
              description
              fields {
                name
                description
                type {
                  name
                  kind
                }
              }
            }
          }
        }
        """
        return self.query_linear(introspection_query)


if __name__ == "__main__":
    """Local development entry point."""
    bot = SlackBot()

    # Get and print the Linear schema
    schema = bot.get_linear_schema()
    print(json.dumps(schema, indent=2))

    # Send a test message to Slack
    bot.send_message(text="Retrieved Linear schema successfully!")
