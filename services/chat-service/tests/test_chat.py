"""Stage 7 DoD tests for chat-service."""

from __future__ import annotations

import json

import pytest


def _parse_sse(raw: str) -> list[dict]:
    """Parse simple SSE text into list of {event, data}."""
    events: list[dict] = []
    event_name = "message"
    data_lines: list[str] = []
    for line in raw.splitlines():
        if line.startswith("event:"):
            event_name = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
        elif line == "" and data_lines:
            raw_data = "\n".join(data_lines)
            data_lines = []
            try:
                parsed = json.loads(raw_data)
            except json.JSONDecodeError:
                parsed = raw_data
            events.append({"event": event_name, "data": parsed})
            event_name = "message"
    if data_lines:
        raw_data = "\n".join(data_lines)
        try:
            parsed = json.loads(raw_data)
        except json.JSONDecodeError:
            parsed = raw_data
        events.append({"event": event_name, "data": parsed})
    return events


@pytest.mark.asyncio
async def test_health(client):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json()["service"] == "chat-service"


@pytest.mark.asyncio
async def test_create_and_list_sessions(client, user_a_headers):
    res = await client.post(
        "/api/v1/chat/sessions",
        headers=user_a_headers,
        json={"title": "Phoenix Q"},
    )
    assert res.status_code == 201, res.text
    session = res.json()
    assert session["title"] == "Phoenix Q"
    assert session["id"]

    listed = await client.get("/api/v1/chat/sessions", headers=user_a_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


@pytest.mark.asyncio
async def test_sse_streams_tokens_incrementally_and_persists_history(
    client, user_a_headers
):
    """DoD: SSE tokens arrive in multiple events; history endpoint shows the turn."""
    create = await client.post(
        "/api/v1/chat/sessions", headers=user_a_headers, json={}
    )
    assert create.status_code == 201
    session_id = create.json()["id"]

    async with client.stream(
        "POST",
        f"/api/v1/chat/sessions/{session_id}/stream",
        headers=user_a_headers,
        json={"content": "What tech stack does Project Phoenix use?"},
    ) as res:
        assert res.status_code == 200
        raw = ""
        async for chunk in res.aiter_text():
            raw += chunk

    events = _parse_sse(raw)
    token_events = [e for e in events if e["event"] == "token"]
    final_events = [e for e in events if e["event"] == "final"]

    # Incremental — not a single dump
    assert len(token_events) >= 2, f"expected multiple token events, got {len(token_events)}"
    assert len(final_events) == 1
    final = final_events[0]["data"]
    assert final["answer"]
    assert final["token_count"] >= 2
    assert final.get("assistant_message_id")

    history = await client.get(
        f"/api/v1/chat/sessions/{session_id}", headers=user_a_headers
    )
    assert history.status_code == 200, history.text
    body = history.json()
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "user"
    assert "Phoenix" in body["messages"][0]["content"]
    assert body["messages"][1]["role"] == "assistant"
    assert body["messages"][1]["content"]
    assert body["messages"][1]["citations"]


@pytest.mark.asyncio
async def test_non_streaming_message(client, user_a_headers):
    create = await client.post(
        "/api/v1/chat/sessions", headers=user_a_headers, json={}
    )
    session_id = create.json()["id"]
    res = await client.post(
        f"/api/v1/chat/sessions/{session_id}/message",
        headers=user_a_headers,
        json={"content": "Summarize Project Phoenix"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["user_message"]["role"] == "user"
    assert body["assistant_message"]["role"] == "assistant"
    assert body["assistant_message"]["citations"]


@pytest.mark.asyncio
async def test_feedback(client, user_a_headers):
    create = await client.post(
        "/api/v1/chat/sessions", headers=user_a_headers, json={}
    )
    session_id = create.json()["id"]
    msg = await client.post(
        f"/api/v1/chat/sessions/{session_id}/message",
        headers=user_a_headers,
        json={"content": "hello"},
    )
    assistant_id = msg.json()["assistant_message"]["id"]
    fb = await client.post(
        f"/api/v1/chat/messages/{assistant_id}/feedback",
        headers=user_a_headers,
        json={"rating": "up"},
    )
    assert fb.status_code == 201, fb.text
    assert fb.json()["rating"] == "up"


@pytest.mark.asyncio
async def test_other_user_cannot_see_session(client, user_a_headers, user_b_headers):
    create = await client.post(
        "/api/v1/chat/sessions", headers=user_a_headers, json={}
    )
    session_id = create.json()["id"]
    res = await client.get(
        f"/api/v1/chat/sessions/{session_id}", headers=user_b_headers
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_missing_token_rejected(client):
    res = await client.post("/api/v1/chat/sessions", json={})
    assert res.status_code in (401, 403)
