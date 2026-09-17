# LLM Client Design Patterns

> Best practices for building LLM/AI service clients.

---

## 1. Client Architecture

```python
from dataclasses import dataclass

@dataclass
class LLMConfig:
    api_key: str
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 2000

class LLMClient:
    def __init__(self, config: LLMConfig):
        self._config = config
        self._session = None
    
    async def complete(self, prompt: str) -> str:
        # Implementation
        ...
```

---

## 2. Error Handling

```python
class LLMError(Exception):
    pass

class RateLimitError(LLMError):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after

async def call_with_retry(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await func()
        except RateLimitError as e:
            await asyncio.sleep(e.retry_after)
    raise LLMError("Max retries exceeded")
```

---

## 3. Response Parsing

```python
import json
import re

def extract_json(response: str) -> dict | None:
    """Extract JSON from LLM response."""
    pattern = r'```(?:json)?\s*([\s\S]*?)```'
    match = re.search(pattern, response)
    content = match.group(1) if match else response
    
    try:
        return json.loads(content.strip())
    except json.JSONDecodeError:
        return None
```

---

## 4. Streaming

```python
async def stream_complete(prompt: str):
    async for chunk in client.stream(prompt):
        yield chunk.content
```

---

## 5. Batch Processing

```python
async def batch_process(items: list, processor, batch_size=10):
    results = []
    for i in range(0, len(items), batch_size):
        batch = items[i:i+batch_size]
        batch_results = await asyncio.gather(*[
            processor(item) for item in batch
        ])
        results.extend(batch_results)
    return results
```

---

*See also: prompt-engineering.md, domain-adaptation.md*
