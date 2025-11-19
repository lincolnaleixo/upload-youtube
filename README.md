# YouTube Video Uploader

A Python script to upload videos to YouTube as draft (private) using the official Google/YouTube Data API v3.

## Requirements

```bash
pip install google-api-python-client google-auth google-auth-httplib2 google-auth-oauthlib
```

## Setup

1. **Create a Google Cloud Project** and enable the YouTube Data API v3
2. **Create OAuth 2.0 credentials** (Desktop application type)
3. Save the credentials as `client_secret.json` in this directory
4. Create a `token.json` file with your OAuth tokens (see format below)

### Token Format

```json
{
  "token": "YOUR_ACCESS_TOKEN",
  "refresh_token": "YOUR_REFRESH_TOKEN",
  "token_uri": "https://oauth2.googleapis.com/token",
  "client_id": "YOUR_CLIENT_ID",
  "client_secret": "YOUR_CLIENT_SECRET",
  "scopes": [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly"
  ]
}
```

## Usage

### Command Line

```bash
python upload_video.py --file VIDEO_FILE --title "Video Title" --description "Video description" --privacy private
```

### Arguments

- `--file` (required): Path to the video file to upload
- `--title`: Video title (default: "Test Video Upload")
- `--description`: Video description (default: "Uploaded via Python API")
- `--category`: YouTube category ID (default: "22" - People & Blogs)
- `--tags`: Comma-separated list of tags
- `--privacy`: Privacy status - "public", "private", or "unlisted" (default: "private")

### Examples

```bash
# Upload as private (draft)
python upload_video.py --file myvideo.mp4 --title "My Video" --privacy private

# Upload as unlisted with tags
python upload_video.py --file myvideo.mp4 --title "My Video" --tags "tag1,tag2,tag3" --privacy unlisted

# Upload as public
python upload_video.py --file myvideo.mp4 --title "My Video" --privacy public
```

### Python Module

```python
from upload_video import upload_video

video_id = upload_video(
    video_file="myvideo.mp4",
    title="My Video",
    description="Video description",
    category="22",
    tags=["tag1", "tag2"],
    privacy_status="private"
)
print(f"Uploaded: https://www.youtube.com/watch?v={video_id}")
```

## YouTube Category IDs

- 1 - Film & Animation
- 2 - Autos & Vehicles
- 10 - Music
- 15 - Pets & Animals
- 17 - Sports
- 19 - Travel & Events
- 20 - Gaming
- 22 - People & Blogs
- 23 - Comedy
- 24 - Entertainment
- 25 - News & Politics
- 26 - Howto & Style
- 27 - Education
- 28 - Science & Technology
- 29 - Nonprofits & Activism

## Notes

- Videos uploaded as "private" appear as drafts in YouTube Studio
- The script automatically refreshes expired access tokens
- Large videos are uploaded in 1MB chunks with retry logic
- SSL verification can be disabled for environments with proxy issues
