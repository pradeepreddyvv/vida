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
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Vida could not read the AI response. Please try again; no plan was applied.") from exc
    if not isinstance(parsed, dict): raise ValueError("Vida received an incomplete AI response. Please try again.")
    return parsed


def chat_turn(system_prompt, user_message, history=None, max_tokens=1024):
    messages = []
    # A bounded history can start halfway through a turn. Bedrock requires a
    # user first; receipts and retried requests can also repeat a role.
    for msg in [*(history or []), {"role": "user", "content": user_message}]:
        role, text = msg.get("role"), msg.get("content")
        if role not in ("user", "assistant") or not isinstance(text, str) or not text.strip():
            continue
        if not messages and role != "user":
            continue
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"][0]["text"] += "\n\n" + text
        else:
            messages.append({"role": role, "content": [{"text": text}]})
    if not messages:
        raise ValueError("Enter a message for Vida.")
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
