from googleapiclient.errors import HttpError
from utils import log, exponential_backoff, parse_datetime, check_quota_status, get_quota_usage, update_quota_usage, save_progress
from datetime import datetime, timedelta
import time

QUOTA_COST_LIST = 1
QUOTA_COST_CHANNEL = 1
QUOTA_COST_PLAYLIST_ITEMS = 1

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
            
            # Get the last video upload date
            playlist_id = content_details['relatedPlaylists']['uploads']
            last_upload_date = 'N/A'
            try:
                last_video = youtube.playlistItems().list(
                    part="snippet",
                    playlistId=playlist_id,
                    maxResults=1
                ).execute()
                
                if 'items' in last_video and len(last_video['items']) > 0:
                    last_upload_date = last_video['items'][0]['snippet']['publishedAt']
            except HttpError as e:
                if e.resp.status == 404:
                    log(f"Playlist not found for channel {channel_id}. Skipping last upload date.")
                else:
                    raise
            
            # Calculate upload frequency (very rough estimate)
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
            
            return {
                'created_at': created_at,
                'total_videos': total_videos,
                'last_upload_date': last_upload_date,
                'upload_frequency': f"{upload_frequency:.2f} videos per day"
            }
        else:
            return None
    except HttpError as e:
        log(f"An error occurred while fetching channel details for {channel_id}: {e}")
        return None

def list_subscriptions(youtube, existing_subs, account_id, max_ops=None):
    log("Listing subscriptions...")
    if not check_quota_status():
        return []

    request = youtube.subscriptions().list(
        part="snippet",
        mine=True,
        maxResults=50
    )
    subscriptions = []
    quota_usage = get_quota_usage()
    
    try:
        while request and (max_ops is None or len(subscriptions) < max_ops):
            if not check_quota_status():
                break

            log("Executing API request...")
            response = request.execute()
            log(f"API response received. Status: {response.get('kind', 'Unknown')}")
            
            quota_usage += QUOTA_COST_LIST
            update_quota_usage(quota_usage)

            if 'items' not in response:
                log(f"Unexpected API response: {response}")
                break

            for item in response['items']:
                if max_ops is not None and len(subscriptions) >= max_ops:
                    break

                channel_id = item['snippet']['resourceId']['channelId']
                channel_info = {
                    'channel_id': channel_id,
                    'title': item['snippet']['title'],
                    'description': item['snippet']['description'],
                    'published_at': item['snippet']['publishedAt']
                }
                
                log(f"Processing channel: {channel_info['title']} ({channel_id})")
                
                # Check if we need to update the channel details
                if channel_id not in existing_subs or (
                    existing_subs[channel_id] != 'N/A' and
                    existing_subs[channel_id] is not None and
                    parse_datetime(existing_subs[channel_id]) < datetime.now() - timedelta(days=7)
                ):
                    if not check_quota_status():
                        break
                    # Get additional channel details
                    details = get_channel_details(youtube, channel_id)
                    if details:
                        channel_info.update(details)
                        quota_usage += QUOTA_COST_CHANNEL + QUOTA_COST_PLAYLIST_ITEMS
                        update_quota_usage(quota_usage)
                
                subscriptions.append(channel_info)
                save_progress(channel_id)
                time.sleep(2)  # Add a delay to avoid hitting rate limits
            
            if not check_quota_status() or (max_ops is not None and len(subscriptions) >= max_ops):
                break
            request = youtube.subscriptions().list_next(request, response)
    except HttpError as e:
        if e.resp.status == 403 and 'quotaExceeded' in str(e):
            log("Quota exceeded. Stopping the process.")
        else:
            log(f"An error occurred while listing subscriptions: {e}")
    except Exception as e:
        log(f"An unexpected error occurred: {str(e)}")
    except KeyboardInterrupt:
        log("Script interrupted. Saving progress...")
    
    log(f"Found {len(subscriptions)} subscriptions.")
    return subscriptions

def import_subscriptions(source_youtube, target_youtube, source_account_id, target_account_id, max_ops=None):
    log("Importing subscriptions from source to target account...")
    existing_subs = get_existing_subscriptions(source_account_id)
    source_subscriptions = list_subscriptions(source_youtube, existing_subs, source_account_id, max_ops)
    
    if not source_subscriptions:
        log("No subscriptions found in the source account.")
        return
    
    for sub in source_subscriptions:
        try:
            target_youtube.subscriptions().insert(
                part="snippet",
                body={
                    "snippet": {
                        "resourceId": {
                            "kind": "youtube#channel",
                            "channelId": sub['channel_id']
                        }
                    }
                }
            ).execute()
            log(f"Subscribed to {sub['title']} in target account.")
        except HttpError as e:
            if e.resp.status == 400 and 'subscriptionDuplicate' in str(e):
                log(f"Already subscribed to {sub['title']} in target account.")
            else:
                log(f"Failed to subscribe to {sub['title']}: {e}")
        
        time.sleep(1)  # Add a delay to avoid hitting rate limits
    
    log("Subscription import completed.")
