import sys
sys.path.insert(0, '.')
from app.integrations.ai.registry import get_text_provider
from app.integrations.ai.base import TextGenerationRequest
import json

p = get_text_provider()
title = "ጠቅላይ ሚኒስትር ዐቢይ አሕመድ በማዕከላዊ ኢትዮጵያ ክልል የተከናወኑ የልማት ሥራዎችን ጎበኙ"
prompt = f"""You are an editorial photo desk director.
Extract the main person/subject and 3 photographic search queries in English from this news headline:
Headline: {title}

Output valid JSON only:
{{
  "main_person": "Full English Name if person mentioned, or null",
  "topic": "Clean English Topic Name",
  "queries": ["query 1", "query 2", "query 3"]
}}
"""
res = p.generate_text(TextGenerationRequest(prompt=prompt))
print("LLM Response:\n", res.text)
