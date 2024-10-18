import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from utils import log

# Define the scope for YouTube Data API
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

def authenticate_youtube(account_name):
    creds = None
    token_file = f'token_{account_name}.json'
    client_secret_file = f'client_secret_{account_name}.json'
    log(f"Authenticating {account_name} account...")
    if os.path.exists(token_file):
        log(f"Token file found. Loading credentials...")
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            log("Refreshing expired credentials...")
            creds.refresh(Request())
        else:
            log(f"Starting new authentication flow for {account_name} account...")
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
            creds = flow.run_local_server(port=0)
        log(f"Saving new credentials to {token_file}...")
        with open(token_file, 'w') as token:
            token.write(creds.to_json())
    log(f"Authentication for {account_name} account completed.")
    return build('youtube', 'v3', credentials=creds)
