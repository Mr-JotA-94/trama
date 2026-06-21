import httpx, os
from dotenv import load_dotenv
load_dotenv()

r = httpx.post(
    "https://integrate.api.nvidia.com/v1/chat/completions",
    headers={"Authorization": f"Bearer {os.environ['NVIDIA_API_KEY']}"},
    json={
        "model": "meta/llama-3.3-70b-instruct",
        "messages": [{"role": "user",
            "content": 'Responde SOLO este JSON, sin texto extra: {"ok": true, "idioma": "es"}'}],
        "temperature": 0.1, "max_tokens": 50,
    }, timeout=60,
)
print("STATUS:", r.status_code)
print("BODY:", r.text[:400])
print("\n--- HEADERS de rate-limit / créditos ---")
for k, v in r.headers.items():
    if any(t in k.lower() for t in ("rate", "limit", "credit", "remaining", "quota", "reset")):
        print(f"  {k}: {v}")