"""Bounded, owner-scoped passage retrieval with source attribution."""
import math
import re
from collections import Counter
from shared.db import query_pk, get_item

STOP = set('the and for that this with from have what when where which about your you are can could would should please tell does how my'.split())

def words(text):
    return [w for w in re.findall(r"[\w]+", str(text).lower()) if len(w) > 1 and w not in STOP]

def retrieve_documents(user_id, query, limit=4):
    terms = set(words(query))
    if not terms:
        return []
    passages = []
    notion = get_item(f'USER#{user_id}', 'INTEGRATION#notion') or {}
    for doc in query_pk(f'USER#{user_id}', sk_prefix='DOC#', limit=200):
        if doc.get('PK') != f'USER#{user_id}' or doc.get('kb_status') in ('failed', 'pending'):
            continue
        if doc.get('source') == 'notion' and notion.get('status') != 'connected':
            continue
        text = (doc.get('extracted_text') or '')[:200000]
        for offset in range(0, len(text), 700):
            passage = text[offset:offset + 1000]
            counts = Counter(words(passage + ' ' + doc.get('file_name','')))
            passages.append((doc, offset, passage, counts))
    frequencies = {term: sum(term in p[3] for p in passages) for term in terms}
    scored = []
    for doc, offset, passage, counts in passages:
        length = max(1, sum(counts.values()))
        score = sum(math.log(1 + (len(passages) - frequencies[t] + .5) / (frequencies[t] + .5)) *
                    counts[t] * 2.2 / (counts[t] + 1.2 * (.25 + .75 * length / 160))
                    for t in terms if counts[t])
        if score > 0:
            scored.append((score, doc, offset, passage))
    if not scored and any(term in query.lower() for term in ('saved documents','saved notes','my documents','my notes','knowledge base')):
        seen=set()
        for doc,offset,passage,counts in passages:
            if doc['SK'] not in seen:
                scored.append((0,doc,offset,passage)); seen.add(doc['SK'])
                if len(scored)>=limit: break
    scored.sort(key=lambda p: -p[0])
    return [{'id': f'S{i+1}', 'doc_id': doc['SK'][4:], 'title': doc.get('file_name', 'Document'),
             'url': f"https://www.notion.so/{doc['notion_id'].replace('-', '')}" if doc.get('notion_id') else None,
             'passage': passage, 'offset': offset, 'source': doc.get('source', 'upload')}
            for i, (_, doc, offset, passage) in enumerate(scored[:limit])]
