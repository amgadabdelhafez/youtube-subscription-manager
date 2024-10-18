# YouTube Subscription Manager

This Python script helps manage YouTube subscriptions, allowing users to update a local database of subscriptions, import subscriptions between accounts, and process watch history. It now supports managing subscriptions for multiple accounts.

## Features

- Update local database with YouTube subscriptions for multiple accounts
- Import subscriptions from one YouTube account to another
- Process watch history from Google Takeout
- Respect YouTube API quota limits
- Support for subscriptions shared between two accounts

## Requirements

- Python 3.7+
- Google account(s) with YouTube Data API v3 enabled

## Installation

1. Clone this repository:

   ```
   git clone https://github.com/yourusername/youtube-subscription-manager.git
   cd youtube-subscription-manager
   ```

2. Install required packages:

   ```
   pip install -r requirements.txt
   ```

3. Set up Google OAuth 2.0 credentials:
   - Go to the [Google Developers Console](https://console.developers.google.com/)
   - Create a new project and enable the YouTube Data API v3
   - Create OAuth 2.0 credentials (OAuth client ID)
   - Download the client configuration and save it as `client_secret_{account_name}.json` in the project directory
   - Repeat this process for each YouTube account you want to manage

## Usage

The script has two main commands: `get` and `import`.

1. Get subscriptions or watch history:

   ```
   python yt_subs.py get --subscriptions --account ACCOUNT_NAME --format {api|csv} [--max-ops NUMBER] [--csv-file FILE_PATH]
   python yt_subs.py get --watched --account ACCOUNT_NAME --format {html|json} [--max-ops NUMBER]
   ```

2. Import subscriptions:

   ```
   python yt_subs.py import --subscriptions --from-account SOURCE_ACCOUNT --to-account TARGET_ACCOUNT [--max-ops NUMBER] [--csv-file FILE_PATH]
   ```

Use the `--max-ops` argument to limit the number of operations processed in a single run.

## Database Schema

The project now uses a SQLite database with the following main tables:

1. `accounts`: Stores information about YouTube accounts.
2. `subscriptions`: Stores channel subscriptions, with support for associating a channel with up to two accounts.
3. `watch_history`: Stores watch history data.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
