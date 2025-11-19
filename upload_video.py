#!/usr/bin/env python3
"""
YouTube Video Uploader - Upload videos to YouTube as draft (private)
Uses the official Google/YouTube Data API v3
"""

import os
import sys
import json
import http.client
import httplib2
import random
import time
import ssl
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.transport import requests as google_requests
from google_auth_httplib2 import AuthorizedHttp
import urllib.parse

# Disable SSL verification warnings (needed for some environments)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Maximum number of retries for resumable upload
MAX_RETRIES = 10

# Explicitly tell the underlying HTTP transport library not to retry
httplib2.RETRIES = 1

# Always retry when these exceptions are raised.
RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError, http.client.NotConnected,
                        http.client.IncompleteRead, http.client.ImproperConnectionState,
                        http.client.CannotSendRequest, http.client.CannotSendHeader,
                        http.client.ResponseNotReady, http.client.BadStatusLine)

# Always retry when an apiclient.errors.HttpError with one of these status codes is raised.
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]

# YouTube API service name and version
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

# Valid privacy statuses
VALID_PRIVACY_STATUSES = ("public", "private", "unlisted")


def get_proxy_info():
    """Get proxy information from environment variables."""
    proxy_url = os.environ.get('https_proxy') or os.environ.get('HTTPS_PROXY')
    if not proxy_url:
        return None

    # Parse proxy URL
    parsed = urllib.parse.urlparse(proxy_url)

    proxy_info = httplib2.ProxyInfo(
        proxy_type=httplib2.socks.PROXY_TYPE_HTTP,
        proxy_host=parsed.hostname,
        proxy_port=parsed.port or 8080,
        proxy_user=parsed.username if parsed.username else None,
        proxy_pass=parsed.password if parsed.password else None
    )

    return proxy_info


def get_authenticated_service(token_file, client_secret_file):
    """
    Create an authenticated YouTube service using stored credentials.

    Args:
        token_file: Path to the token.json file with OAuth credentials
        client_secret_file: Path to the client_secret.json file

    Returns:
        Authenticated YouTube service object
    """
    creds = None

    # Load the token file
    if os.path.exists(token_file):
        with open(token_file, 'r') as f:
            token_data = json.load(f)

        # Parse expiry if available
        from datetime import datetime, timezone
        expiry = None
        if 'expiry' in token_data:
            expiry = datetime.fromisoformat(token_data['expiry'].replace('Z', '+00:00'))

        creds = Credentials(
            token=token_data.get('token'),
            refresh_token=token_data.get('refresh_token'),
            token_uri=token_data.get('token_uri'),
            client_id=token_data.get('client_id'),
            client_secret=token_data.get('client_secret'),
            scopes=token_data.get('scopes'),
            expiry=expiry
        )

        # Force token refresh if we have a refresh token
        # This ensures we always have a fresh token
        if creds.refresh_token:
            print("Refreshing access token...")
            import requests
            session = requests.Session()
            session.verify = False
            auth_request = google_requests.Request(session=session)
            creds.refresh(auth_request)

            # Save the refreshed token
            token_data = {
                'token': creds.token,
                'refresh_token': creds.refresh_token,
                'token_uri': creds.token_uri,
                'client_id': creds.client_id,
                'client_secret': creds.client_secret,
                'scopes': list(creds.scopes) if creds.scopes else [],
                'expiry': creds.expiry.isoformat() if creds.expiry else None
            }
            with open(token_file, 'w') as f:
                json.dump(token_data, f, indent=2)
            print("Token refreshed and saved.")

    # Refresh the token if expired
    if creds and creds.expired and creds.refresh_token:
        print("Refreshing expired access token...")
        # Create a session that doesn't verify SSL (for environments with proxy issues)
        import requests
        session = requests.Session()
        session.verify = False
        auth_request = google_requests.Request(session=session)
        creds.refresh(auth_request)

        # Save the refreshed token
        token_data = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': list(creds.scopes) if creds.scopes else [],
            'expiry': creds.expiry.isoformat() if creds.expiry else None
        }
        with open(token_file, 'w') as f:
            json.dump(token_data, f, indent=2)
        print("Token refreshed and saved.")

    if not creds or not creds.valid:
        # Try to refresh the token
        if creds and creds.refresh_token:
            print("Token invalid, attempting refresh...")
            # Create a session that doesn't verify SSL (for environments with proxy issues)
            import requests
            session = requests.Session()
            session.verify = False
            auth_request = google_requests.Request(session=session)
            creds.refresh(auth_request)

            # Save the refreshed token
            token_data = {
                'token': creds.token,
                'refresh_token': creds.refresh_token,
                'token_uri': creds.token_uri,
                'client_id': creds.client_id,
                'client_secret': creds.client_secret,
                'scopes': list(creds.scopes) if creds.scopes else [],
                'expiry': creds.expiry.isoformat() if creds.expiry else None
            }
            with open(token_file, 'w') as f:
                json.dump(token_data, f, indent=2)
            print("Token refreshed and saved.")
        else:
            raise Exception("No valid credentials available. Please re-authenticate.")

    # Build YouTube service using default HTTP transport
    return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, credentials=creds)


def initialize_upload(youtube, video_file, title, description, category, tags, privacy_status):
    """
    Initialize and execute the video upload.

    Args:
        youtube: Authenticated YouTube service
        video_file: Path to the video file to upload
        title: Video title
        description: Video description
        category: YouTube category ID (e.g., "22" for People & Blogs)
        tags: List of tags for the video
        privacy_status: "public", "private", or "unlisted"

    Returns:
        Video ID of the uploaded video
    """
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags,
            'categoryId': category
        },
        'status': {
            'privacyStatus': privacy_status,
            'selfDeclaredMadeForKids': False
        }
    }

    # Create the media upload object
    media = MediaFileUpload(
        video_file,
        chunksize=1024*1024,  # 1MB chunks
        resumable=True
    )

    # Call the API's videos.insert method
    insert_request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=media
    )

    return resumable_upload(insert_request)


def resumable_upload(insert_request):
    """
    Execute the resumable upload with retry logic.

    Args:
        insert_request: The API request object

    Returns:
        Video ID of the uploaded video
    """
    response = None
    error = None
    retry = 0

    while response is None:
        try:
            print("Uploading video...")
            status, response = insert_request.next_chunk()

            if status:
                print(f"Upload progress: {int(status.progress() * 100)}%")

            if response is not None:
                if 'id' in response:
                    print(f"\nVideo uploaded successfully!")
                    print(f"Video ID: {response['id']}")
                    print(f"Video URL: https://www.youtube.com/watch?v={response['id']}")
                    return response['id']
                else:
                    raise Exception(f"Upload failed with unexpected response: {response}")

        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                error = f"A retriable HTTP error {e.resp.status} occurred:\n{e.content}"
            else:
                raise

        except RETRIABLE_EXCEPTIONS as e:
            error = f"A retriable error occurred: {e}"

        if error is not None:
            print(error)
            retry += 1

            if retry > MAX_RETRIES:
                raise Exception("Maximum retries exceeded")

            max_sleep = 2 ** retry
            sleep_seconds = random.random() * max_sleep
            print(f"Sleeping {sleep_seconds:.2f} seconds and then retrying...")
            time.sleep(sleep_seconds)


def upload_video(video_file, title="Test Video", description="Uploaded via API",
                 category="22", tags=None, privacy_status="private"):
    """
    Main function to upload a video to YouTube.

    Args:
        video_file: Path to the video file
        title: Video title
        description: Video description
        category: YouTube category ID
        tags: List of tags
        privacy_status: "public", "private", or "unlisted"

    Returns:
        Video ID of the uploaded video
    """
    if tags is None:
        tags = []

    # Validate privacy status
    if privacy_status not in VALID_PRIVACY_STATUSES:
        raise ValueError(f"Invalid privacy status. Must be one of: {VALID_PRIVACY_STATUSES}")

    # Check if video file exists
    if not os.path.exists(video_file):
        raise FileNotFoundError(f"Video file not found: {video_file}")

    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    token_file = os.path.join(script_dir, "token.json")
    client_secret_file = os.path.join(script_dir, "client_secret.json")

    # Get authenticated service
    print("Authenticating with YouTube API...")
    youtube = get_authenticated_service(token_file, client_secret_file)

    # Upload the video
    print(f"\nUploading video: {video_file}")
    print(f"Title: {title}")
    print(f"Privacy: {privacy_status}")
    print("-" * 50)

    video_id = initialize_upload(
        youtube,
        video_file,
        title,
        description,
        category,
        tags,
        privacy_status
    )

    return video_id


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Upload a video to YouTube")
    parser.add_argument("--file", required=True, help="Path to the video file")
    parser.add_argument("--title", default="Test Video Upload", help="Video title")
    parser.add_argument("--description", default="Uploaded via Python API", help="Video description")
    parser.add_argument("--category", default="22", help="YouTube category ID (default: 22 - People & Blogs)")
    parser.add_argument("--tags", default="", help="Comma-separated list of tags")
    parser.add_argument("--privacy", default="private",
                        choices=["public", "private", "unlisted"],
                        help="Video privacy status (default: private for draft)")

    args = parser.parse_args()

    # Parse tags
    tags = [tag.strip() for tag in args.tags.split(",") if tag.strip()] if args.tags else []

    try:
        video_id = upload_video(
            video_file=args.file,
            title=args.title,
            description=args.description,
            category=args.category,
            tags=tags,
            privacy_status=args.privacy
        )
        print(f"\nSuccess! Video ID: {video_id}")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
