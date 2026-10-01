import json
import os
import logging
import boto3

logger = logging.getLogger(__name__)

_bedrock = None


def _get_client():
    global _bedrock
    if _bedrock is None:
        _bedrock = boto3.client(
            "bedrock-runtime",
            region_name=os.environ.get("REGION", "us-east-2"),
        )
    return _bedrock


def converse(system_prompt, messages, model_id=None, max_tokens=2048, temperature=0.3):
    model_id = model_id or os.environ.get("BEDROCK_MODEL_ID", "us.amazon.nova-lite-v1:0")
    client = _get_client()

    kwargs = {
        "modelId": model_id,
        "messages": messages,
        "inferenceConfig": {
            "maxTokens": max_tokens,
            "temperature": temperature,
        },
    }
    if system_prompt:
        kwargs["system"] = [{"text": system_prompt}]

    resp = client.converse(**kwargs)
    output = resp.get("output", {}).get("message", {})
    content_blocks = output.get("content", [])
    text = ""
    for block in content_blocks:
        if "text" in block:
            text += block["text"]
    return text


def converse_json(system_prompt, messages, model_id=None, max_tokens=2048, temperature=0.1):
    raw = converse(system_prompt, messages, model_id, max_tokens, temperature)
    raw = raw.strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()
    return json.loads(raw)


def chat_turn(system_prompt, user_message, history=None, max_tokens=1024):
    messages = []
    if history:
        for msg in history:
            messages.append({
                "role": msg["role"],
                "content": [{"text": msg["content"]}],
            })
    messages.append({"role": "user", "content": [{"text": user_message}]})
    return converse(system_prompt, messages, max_tokens=max_tokens)


def retrieve_from_kb(query, kb_id=None, top_k=5):
    kb_id = kb_id or os.environ.get("BEDROCK_KB_ID") or os.environ.get("KB_ID", "")
    if not kb_id:
        logger.warning("No Knowledge Base ID configured, skipping RAG retrieve")
        return []

    client = boto3.client(
        "bedrock-agent-runtime",
        region_name=os.environ.get("REGION", "us-east-1"),
    )

    try:
        resp = client.retrieve(
            knowledgeBaseId=kb_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {
                    "numberOfResults": top_k,
                }
            },
        )
        results = []
        for r in resp.get("retrievalResults", []):
            results.append({
                "text": r.get("content", {}).get("text", ""),
                "score": float(r.get("score", 0)),
                "source": r.get("location", {}).get("s3Location", {}).get("uri", ""),
            })
        return results
    except Exception as e:
        logger.error(f"KB retrieve failed: {e}")
        return []
