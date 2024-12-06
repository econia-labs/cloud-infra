<!-- cspell:word venv -->

# Slack Linear Bot

This bot queries Linear issue metrics from the [Linear GraphQL API] and posts
a summary to Slack.

## Bot permissions

The Slack bot requires the following [permission scopes]:

1. `chat:write`
1. `users:read`
1. `users:read.email`

## Local development

1. Create virtual environment:

   ```sh
   python -m venv linear-slack-bot-venv
   ```

1. Activate virtual environment:

   ```sh
   # On Mac/Linux:
   source linear-slack-bot-venv/bin/activate

   # On Windows:
   linear-slack-bot-venv\Scripts\activate
   ```

1. Install dependencies:

   ```sh
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

1. Create `.env` file:

   ```env
   SLACK_BOT_TOKEN=your-token
   LINEAR_API_TOKEN=your-token
   ```

## Running Locally

With the virtual environment activated:

```sh
python bot/bot.py
```

## Updating Dependencies

With virtual environment activated:

```sh
pip freeze > requirements.txt
```

[linear graphql api]: https://developers.linear.app/docs/graphql/working-with-the-graphql-api
[permission scopes]: https://api.slack.com/scopes
