from googleapiclient.errors import HttpError
import time
from utils import log
from quota_management import check_quota_status, use_quota, can_perform_operation
from progress_tracking import save_progress, load_progress
from channel_details import get_channel_details

def list_subscriptions(youtube, existing_subs, account_name, max_ops=None):
    log("Listing subscriptions...")
    if not can_perform_operation('SEARCH'):
        log("Not enough quota to perform search operation.")
        return []

    progress = load_progress()
    last_processed, page_token = progress.get('channel_id'), progress.get('page_token')

    if last_processed:
        log(f"Resuming from last processed channel ID: {last_processed}")
    else:
        log("Starting from the beginning of the subscription list")

    request = youtube.subscriptions().list(
        part="snippet",
        mine=True,
        maxResults=50,
        pageToken=page_token
    )

    subscriptions = []

    try:
        while request:
            if not can_perform_operation('SEARCH'):
                log("Quota limit reached. Stopping the process.")
                break

            if max_ops is not None and len(subscriptions) >= max_ops:
                log(f"Reached max-ops limit of {max_ops}. Stopping the process.")
                break

            log("Executing API request...")
            response = request.execute()
            use_quota('SEARCH')
            log(f"API response received. Status: {response.get('kind', 'Unknown')}")

            if 'items' not in response:
                log(f"Unexpected API response: {response}")
                break

            for item in response['items']:
                if max_ops is not None and len(subscriptions) >= max_ops:
                    break

                channel_id = item['snippet']['resourceId']['channelId']
                
                channel_info = process_channel_item(youtube, item, channel_id, existing_subs, account_name)
                
                if channel_info:
                    subscriptions.append(channel_info)
                    save_progress({'channel_id': channel_id, 'page_token': response.get('nextPageToken')})
                    # time.sleep(.1)  # Add a delay to avoid hitting rate limits
            
            if max_ops is not None and len(subscriptions) >= max_ops:
                break
            request = youtube.subscriptions().list_next(request, response)
    except HttpError as e:
        handle_http_error(e)
    except Exception as e:
        log(f"An unexpected error occurred: {str(e)}")
    except KeyboardInterrupt:
        log("Script interrupted. Saving progress...")
    
    log(f"Found {len(subscriptions)} subscriptions.")
    return subscriptions

def process_channel_item(youtube, item, channel_id, existing_subs, account_name):
    channel_info = {
        'channel_id': channel_id,
        'title': item['snippet']['title'],
        'description': item['snippet']['description'],
        'published_at': item['snippet']['publishedAt']
    }
    
    log(f"Processing channel: {channel_info['title']} ({channel_id})")
    
    # Check if we need to update the channel details
    if channel_id not in existing_subs:
        if not can_perform_operation('READ'):
            log("Not enough quota to fetch channel details.")
            return None
        # Get additional channel details
        details = get_channel_details(youtube, channel_id)
        if details:
            channel_info.update(details)
            use_quota('READ')
    
    return channel_info

def handle_http_error(e):
    if e.resp.status == 403 and 'quotaExceeded' in str(e):
        log("Quota exceeded. Stopping the process.")
    else:
        log(f"An error occurred while listing subscriptions: {e}")
