"""One bounded local-model transport for advice and test authoring."""
import json
import urllib.request

from jsonschema import validate


def chat(model, system, packet, schema, timeout=180):
    if not model.strip() or len(model) > 200:
        raise ValueError("Provide an installed local Ollama model name")
    payload = {"model": model, "stream": False, "format": schema,
               "options": {"temperature": 0, "num_ctx": 16384},
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": json.dumps(packet)}]}
    request = urllib.request.Request("http://127.0.0.1:11434/api/chat",
                                     data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(1_000_001)
    if len(raw) > 1_000_000:
        raise ValueError("Model response exceeded 1 MB")
    try:
        envelope = json.loads(raw)
        result = json.loads(envelope["message"]["content"])
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError("Model must return the requested JSON object") from exc
    validate(result, schema)
    return result
