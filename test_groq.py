import httpx
import os
from dotenv import load_dotenv

load_dotenv("d:/facts/ytclfr/.env", override=True)
key = os.getenv("OPENROUTER_API_KEY")
url = os.getenv("OPENROUTER_BASE_URL")
model = os.getenv("OPENROUTER_MODEL")

print(f"URL:   {url}")
print(f"Model: {model}")
print(f"Key:   {key[:8]}...{key[-4:]}" if key and len(key) > 12 else f"Key: {key}")
print()

r = httpx.post(
    f"{url}/chat/completions",
    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    json={"model": model, "messages": [{"role": "user", "content": "Say hello in one word"}], "max_tokens": 10},
    timeout=15,
)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    reply = data["choices"][0]["message"]["content"]
    print(f"Response: {reply}")
    print("\nGroq API is working!")
else:
    print(f"Error: {r.text}")
