from gemini_compat_proxy import sanitize_payload


def test_sanitize_payload_removes_only_unsupported_penalties():
    source = {
        "model": "gemini-2.5-flash-lite",
        "messages": [{"role": "user", "content": "hola"}],
        "temperature": 0.0,
        "frequency_penalty": 0,
        "presence_penalty": 0,
    }
    sanitized = sanitize_payload(source)
    assert "frequency_penalty" not in sanitized
    assert "presence_penalty" not in sanitized
    assert sanitized["model"] == source["model"]
    assert sanitized["messages"] == source["messages"]
