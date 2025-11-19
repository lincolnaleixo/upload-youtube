#!/usr/bin/env python3
"""
Test YouTube API authentication and permissions
"""

import os
import json
import httplib2
import urllib3
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.transport import requests as google_requests
from google_auth_httplib2 import AuthorizedHttp

# Disable SSL verification warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_auth():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    token_file = os.path.join(script_dir, "token.json")

    # Load the token file
    with open(token_file, 'r') as f:
        token_data = json.load(f)

    creds = Credentials(
        token=token_data.get('token'),
        refresh_token=token_data.get('refresh_token'),
        token_uri=token_data.get('token_uri'),
        client_id=token_data.get('client_id'),
        client_secret=token_data.get('client_secret'),
        scopes=token_data.get('scopes')
    )

    # Create httplib2 with SSL disabled
    http = httplib2.Http(disable_ssl_certificate_validation=True)
    authed_http = AuthorizedHttp(creds, http=http)

    # Build YouTube service
    youtube = build("youtube", "v3", http=authed_http)

    # Test: Get authenticated user's channel
    print("Testing: Get authenticated user's channel info...")
    try:
        response = youtube.channels().list(
            part="snippet,contentDetails,statistics",
            mine=True
        ).execute()

        if 'items' in response and len(response['items']) > 0:
            channel = response['items'][0]
            print(f"Channel ID: {channel['id']}")
            print(f"Channel Title: {channel['snippet']['title']}")
            print(f"Subscriber Count: {channel['statistics'].get('subscriberCount', 'Hidden')}")
            print("\nAuthentication successful!")
            return True
        else:
            print("No channel found for this user")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    test_auth()
