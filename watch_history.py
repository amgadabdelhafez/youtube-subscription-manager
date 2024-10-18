from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from utils import log

def get_watch_history(credentials_path, max_results=50):
    try:
        # Set up credentials
        credentials = Credentials.from_authorized_user_file(credentials_path)

        # Build the YouTube API client
        youtube = build('youtube', 'v3', credentials=credentials)

        # Retrieve the watch history
        request = youtube.playlistItems().list(
            part='snippet',
            playlistId='HL',  # 'HL' is a special playlist ID for watch history
            maxResults=max_results
        )

        response = request.execute()
        watch_history = []

        # Process the response
        for item in response['items']:
            video_title = item['snippet']['title']
            video_id = item['snippet']['resourceId']['videoId']
            watch_history.append({
                'title': video_title,
                'url': f"https://www.youtube.com/watch?v={video_id}"
            })

        # Handle pagination if needed
        while 'nextPageToken' in response:
            request = youtube.playlistItems().list(
                part='snippet',
                playlistId='HL',
                maxResults=max_results,
                pageToken=response['nextPageToken']
            )
            response = request.execute()
            for item in response['items']:
                video_title = item['snippet']['title']
                video_id = item['snippet']['resourceId']['videoId']
                watch_history.append({
                    'title': video_title,
                    'url': f"https://www.youtube.com/watch?v={video_id}"
                })

        return watch_history

    except Exception as e:
        log(f"An error occurred while fetching watch history: {str(e)}")
        return None

def print_watch_history(watch_history):
    if watch_history:
        for item in watch_history:
            print(f"Watched: {item['title']} ({item['url']})")
    else:
        print("No watch history available or an error occurred.")
