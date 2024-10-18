from googleapiclient.errors import HttpError
from utils import log, parse_datetime, exponential_backoff

@exponential_backoff
def get_channel_details(youtube, channel_id):
    try:
        response = youtube.channels().list(
            part="snippet,statistics,contentDetails",
            id=channel_id
        ).execute()
        
        if 'items' in response and len(response['items']) > 0:
            channel = response['items'][0]
            snippet = channel['snippet']
            statistics = channel['statistics']
            content_details = channel['contentDetails']
            
            created_at = snippet['publishedAt']
            total_videos = statistics.get('videoCount', 'N/A')
            
            last_upload_date = get_last_upload_date(youtube, content_details, channel_id)
            
            upload_frequency = calculate_upload_frequency(created_at, last_upload_date, total_videos)
            
            return {
                'created_at': created_at,
                'total_videos': total_videos,
                'last_upload_date': last_upload_date,
                'upload_frequency': upload_frequency
            }
        else:
            return None
    except HttpError as e:
        log(f"An error occurred while fetching channel details for {channel_id}: {e}")
        return None

def get_last_upload_date(youtube, content_details, channel_id):
    playlist_id = content_details['relatedPlaylists']['uploads']
    try:
        last_video = youtube.playlistItems().list(
            part="snippet",
            playlistId=playlist_id,
            maxResults=1
        ).execute()
        
        if 'items' in last_video and len(last_video['items']) > 0:
            return last_video['items'][0]['snippet']['publishedAt']
    except HttpError as e:
        if e.resp.status == 404:
            log(f"Playlist not found for channel {channel_id}. Skipping last upload date.")
        else:
            raise
    return 'N/A'

def calculate_upload_frequency(created_at, last_upload_date, total_videos):
    if last_upload_date != 'N/A' and total_videos != 'N/A':
        start_date = parse_datetime(created_at)
        end_date = parse_datetime(last_upload_date)
        days_active = (end_date - start_date).days
        if days_active > 0:
            upload_frequency = float(total_videos) / days_active
        else:
            upload_frequency = 0
    else:
        upload_frequency = 0
    
    return f"{upload_frequency:.2f} videos per day"
