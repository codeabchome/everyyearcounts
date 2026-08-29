#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EveryYearCounts — upload.py
YouTube Data API v3 ile yukleme. Kimlik bilgileri GitHub Secrets'tan gelir:
  YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
(Refresh token OAuth Playground ile bir kez uretilir — fikra kanalindaki akisin aynisi.)
"""
import json
import os

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def _client():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload_video(path, meta, category="27", privacy=None, thumbnail=None):
    """
    privacy: None ise EYC_PRIVACY ortam degiskeni kullanilir (varsayilan 'private').
    Ilk testlerde video gizli kalir; public'e gecmek icin workflow'da
    EYC_PRIVACY: public yaz.
    """
    privacy = privacy or os.environ.get("EYC_PRIVACY", "private")
    yt = _client()
    body = {
        "snippet": {
            "title": meta["title"][:100],
            "description": meta["description"][:5000],
            "tags": meta.get("tags", [])[:30],
            "categoryId": category,
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(path, chunksize=8 * 1024 * 1024, resumable=True,
                            mimetype="video/mp4")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = req.next_chunk()
        if status:
            print(f"  yukleniyor: %{int(status.progress() * 100)}")
    video_id = response["id"]

    # Kapak ayarlamak kanalin dogrulanmis olmasini gerektirir. Basarisiz
    # olursa video zaten yuklenmistir; islemi cokertme, sadece uyar.
    if thumbnail and os.path.exists(thumbnail):
        try:
            yt.thumbnails().set(videoId=video_id,
                                media_body=MediaFileUpload(thumbnail)).execute()
            print("  kapak ayarlandi")
        except Exception as exc:
            print(f"  [uyari] kapak ayarlanamadi (kanal dogrulamasi gerekebilir): "
                  f"{str(exc)[:160]}")
    return video_id
