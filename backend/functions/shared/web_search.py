"""Public web search, enabled only when a server-side Tavily key is configured."""
import json
import os
import urllib.request
import urllib.error
from shared.utils import now_iso

def search(query, topic="general", time_range=None):
    key=os.environ.get('TAVILY_API_KEY','')
    if not key: raise ValueError('Live web research is not configured yet. Add a Tavily key; saved-document search still works.')
    if not isinstance(query,str) or not 1<=len(query.strip())<=400: raise ValueError('Use a public search query of 1–400 characters.')
    if topic not in ('general','news'): raise ValueError('Search topic must be general or news.')
    if time_range not in (None,'day','week','month','year'): raise ValueError('Choose a supported search time range.')
    parameters={'query':query,'search_depth':'basic','max_results':4,'include_answer':False,'include_raw_content':False,'topic':topic}
    if time_range: parameters['time_range']=time_range
    request=urllib.request.Request('https://api.tavily.com/search',data=json.dumps(parameters).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key},method='POST')
    try:
        with urllib.request.urlopen(request,timeout=15) as response: data=json.load(response)
    except (urllib.error.URLError, ValueError) as exc:
        raise ValueError('Web research is unavailable right now. Check your search key or free-credit balance and try again.') from exc
    return [{'id':'W'+str(i+1),'title':row.get('title','Web source'),'url':row.get('url',''),'passage':row.get('content','')[:1800],'source':'web','published_date':row.get('published_date'),'retrieved_at':now_iso()} for i,row in enumerate(data.get('results',[])[:4])]
