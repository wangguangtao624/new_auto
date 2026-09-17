# Prompt Engineering Best Practices

> Guidelines for effective prompt design.

---

## 1. Structure

```
[Role/Context]
[Task Description]
[Input Format]
[Output Format]
[Examples (optional)]
[Constraints]
```

---

## 2. Example Prompt

```
You are a code review assistant. Analyze the following code for:
1. Potential bugs
2. Security issues
3. Performance concerns

Code:
```python
{code}
```

Respond in JSON format:
{
  "bugs": [...],
  "security": [...],
  "performance": [...]
}

Be concise and specific.
```

---

## 3. Techniques

### Few-Shot Learning

```
Example 1:
Input: "hello world"
Output: "HELLO WORLD"

Example 2:
Input: "test"
Output: "TEST"

Now process:
Input: "{user_input}"
Output:
```

### Chain of Thought

```
Think step by step:
1. First, analyze the problem
2. Then, identify the key components
3. Finally, provide the solution

Problem: {problem}
```

---

## 4. Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| Vague instructions | Be specific about format and content |
| Missing context | Include relevant background |
| No examples | Add 1-3 examples |
| Long prompts | Break into smaller requests |

---

*See also: llm-client.md, domain-adaptation.md*
