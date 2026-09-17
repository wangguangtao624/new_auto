# Domain Adaptation Methodology

> How to adapt AI capabilities to specific domains.

---

## 1. Domain Knowledge Integration

### Knowledge Sources

| Source | Integration Method |
|--------|-------------------|
| Documentation | RAG / Context injection |
| Code examples | Few-shot prompting |
| Domain rules | System prompt constraints |
| Terminology | Glossary in context |

---

## 2. Context Injection

```python
def build_context(domain: str) -> str:
    context_parts = [
        load_domain_rules(domain),
        load_terminology(domain),
        load_examples(domain),
    ]
    return "\n\n".join(context_parts)

prompt = f"""
Domain Context:
{build_context("finance")}

Task: {user_task}
"""
```

---

## 3. RAG Pattern

```python
# 1. Embed query
query_embedding = embed(user_query)

# 2. Retrieve relevant docs
relevant_docs = vector_store.search(query_embedding, top_k=5)

# 3. Build context
context = "\n".join(doc.content for doc in relevant_docs)

# 4. Generate response
response = llm.complete(f"""
Context:
{context}

Question: {user_query}
Answer:
""")
```

---

## 4. Evaluation

| Metric | Description |
|--------|-------------|
| Accuracy | Domain-specific correctness |
| Relevance | Appropriate terminology use |
| Consistency | Alignment with domain rules |

---

*See also: llm-client.md, prompt-engineering.md*
