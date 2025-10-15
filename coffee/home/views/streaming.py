import json


def sse_event(event: str, data: dict | str) -> bytes:
    if not isinstance(data, str):
        data = json.dumps(data, ensure_ascii=False)
    # Each \n must be split into multiple "data:" lines (SSE specification)
    lines = data.split("\n")
    payload = "\n".join(f"data: {line}" for line in lines)
    return f"event: {event}\n{payload}\n\n".encode("utf-8")