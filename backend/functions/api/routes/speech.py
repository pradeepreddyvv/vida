import base64
import json
import hashlib
import hmac
import logging
import os
import urllib.parse
from datetime import datetime, timezone

import boto3

from shared.utils import response, parse_body

logger = logging.getLogger(__name__)

_polly = None


def _get_polly():
    global _polly
    if _polly is None:
        _polly = boto3.client("polly", region_name=os.environ.get("REGION", "us-east-2"))
    return _polly


def synthesize_speech(event, user_id):
    body = parse_body(event)
    text = body.get("text", "")
    if not text:
        return response(400, {"error": "No text provided"})

    text = text[:3000]

    try:
        polly = _get_polly()
        result = polly.synthesize_speech(
            Text=text,
            OutputFormat="mp3",
            VoiceId="Ruth",
            Engine="neural",
        )
        audio_bytes = result["AudioStream"].read()
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

        return response(200, {
            "audio": audio_b64,
            "content_type": "audio/mpeg",
            "voice": "Ruth",
        })
    except Exception as e:
        logger.error(f"Polly synthesis failed: {e}")
        return response(500, {"error": f"Speech synthesis failed: {str(e)}"})


def get_transcribe_config(event, user_id):
    region = os.environ.get("REGION", "us-east-2")
    return response(200, {
        "region": region,
        "language_code": "en-US",
        "sample_rate": 16000,
        "media_encoding": "pcm",
        "endpoint": f"wss://transcribestreaming.{region}.amazonaws.com:8443",
    })
