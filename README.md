# YouTube Subscription Manager

This Python script helps manage YouTube subscriptions, allowing users to update a local database of subscriptions, import subscriptions between accounts, and process watch history.

## Features

- Update local database with YouTube subscriptions
- Import subscriptions from one YouTube account to another
- Process watch history from Google Takeout
- Respect YouTube API quota limits

## Requirements

- Python 3.7+
- Google account with YouTube Data API v3 enabled

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
   - Download the client configuration and save it as `client_secret_source.json` in the project directory
   - If you plan to use the import feature, create another set of credentials and save it as `client_secret_target.json`

## Usage

The script has three modes of operation:

1. Update mode:

   ```
   python yt_subs.py update [--max-ops NUMBER]
   ```

2. Import mode:

   ```
   python yt_subs.py import [--max-ops NUMBER]
   ```

3. History mode:
   ```
   python yt_subs.py history --history-file "/path/to/watch-history.html"
   ```

Use the `--max-ops` argument to limit the number of channels processed in a single run.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
