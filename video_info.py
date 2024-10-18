def get_video_channels(video_ids, youtube):
    video_ids_str = ",".join(video_ids)
    response = youtube.videos().list(part="snippet", id=video_ids_str).execute()
    
    channels = []
    for item in response.get("items", []):
        video_id = item["id"]
        channel_title = item["snippet"]["channelTitle"]
        channel_id = item["snippet"]["channelId"]
        video_title = item["snippet"]["title"]
        channels.append({
            "video_id": video_id,
            "channel_title": channel_title,
            "channel_id": channel_id,
            "video_title": video_title
        })
    return channels
