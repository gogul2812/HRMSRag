import uuid

import pytest

PROMPT_ENDPOINTS = [
    ("GET", "/api/v1/config/prompt"),
    ("POST", "/api/v1/config/prompt"),
    ("GET", "/api/v1/config/prompt/versions"),
]

GUARDRAIL_ENDPOINTS = [
    ("GET", "/api/v1/config/guardrails"),
    ("POST", "/api/v1/config/guardrails"),
    ("GET", "/api/v1/config/guardrails/versions"),
]


@pytest.mark.asyncio
async def test_health(client):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json()["service"] == "admin-config-service"


@pytest.mark.asyncio
async def test_create_two_versions_activate_and_get_active(client, admin_a_headers):
    # Version 1
    r1 = await client.post(
        "/api/v1/config/prompt",
        json={"text": "Rules v1 — be concise"},
        headers=admin_a_headers,
    )
    assert r1.status_code == 201
    v1 = r1.json()
    assert v1["version"] == 1
    assert v1["is_active"] is False

    # Version 2
    r2 = await client.post(
        "/api/v1/config/prompt",
        json={"text": "Rules v2 — be thorough"},
        headers=admin_a_headers,
    )
    assert r2.status_code == 201
    v2 = r2.json()
    assert v2["version"] == 2
    assert v2["is_active"] is False

    # Activate v2
    act = await client.put(
        f"/api/v1/config/prompt/{v2['id']}/activate",
        headers=admin_a_headers,
    )
    assert act.status_code == 200
    assert act.json()["is_active"] is True
    assert act.json()["text"] == "Rules v2 — be thorough"

    # Active GET returns v2
    active = await client.get("/api/v1/config/prompt", headers=admin_a_headers)
    assert active.status_code == 200
    assert active.json()["id"] == v2["id"]
    assert active.json()["version"] == 2

    # List shows both; only one active
    versions = await client.get("/api/v1/config/prompt/versions", headers=admin_a_headers)
    assert versions.status_code == 200
    items = versions.json()
    assert len(items) == 2
    assert sum(1 for i in items if i["is_active"]) == 1

    # Activate v1 instead — only one remains active
    act1 = await client.put(
        f"/api/v1/config/prompt/{v1['id']}/activate",
        headers=admin_a_headers,
    )
    assert act1.status_code == 200
    active2 = await client.get("/api/v1/config/prompt", headers=admin_a_headers)
    assert active2.json()["id"] == v1["id"]
    assert active2.json()["text"] == "Rules v1 — be concise"


@pytest.mark.asyncio
async def test_tenant_isolation_prompt_configs(client, admin_a_headers, admin_b_headers):
    created = await client.post(
        "/api/v1/config/prompt",
        json={"text": "Tenant A secret rules"},
        headers=admin_a_headers,
    )
    assert created.status_code == 201
    config_id = created.json()["id"]

    await client.put(
        f"/api/v1/config/prompt/{config_id}/activate",
        headers=admin_a_headers,
    )

    # Tenant B cannot list A's configs
    listed = await client.get("/api/v1/config/prompt/versions", headers=admin_b_headers)
    assert listed.status_code == 200
    assert listed.json() == []

    # Tenant B cannot read A's config by exact ID
    by_id = await client.get(
        f"/api/v1/config/prompt/{config_id}",
        headers=admin_b_headers,
    )
    assert by_id.status_code == 404

    # Tenant B cannot activate A's config by exact ID
    activate = await client.put(
        f"/api/v1/config/prompt/{config_id}/activate",
        headers=admin_b_headers,
    )
    assert activate.status_code == 404

    # Tenant B active prompt is empty (404), not A's
    active = await client.get("/api/v1/config/prompt", headers=admin_b_headers)
    assert active.status_code == 404


@pytest.mark.asyncio
async def test_guardrail_versioning_and_isolation(
    client, admin_a_headers, admin_b_headers
):
    g1 = await client.post(
        "/api/v1/config/guardrails",
        json={"policy_json": {"refuse_topics": ["medical_advice"], "pii": "redact"}},
        headers=admin_a_headers,
    )
    assert g1.status_code == 201
    assert g1.json()["version"] == 1

    g2 = await client.post(
        "/api/v1/config/guardrails",
        json={"policy_json": {"refuse_topics": ["medical_advice", "legal"], "pii": "block"}},
        headers=admin_a_headers,
    )
    assert g2.status_code == 201
    policy_id = g2.json()["id"]

    act = await client.put(
        f"/api/v1/config/guardrails/{policy_id}/activate",
        headers=admin_a_headers,
    )
    assert act.status_code == 200

    active = await client.get("/api/v1/config/guardrails", headers=admin_a_headers)
    assert active.status_code == 200
    assert active.json()["id"] == policy_id
    assert active.json()["policy_json"]["pii"] == "block"

    # Tenant B cannot touch A's policy by ID
    assert (
        await client.get(
            f"/api/v1/config/guardrails/{policy_id}", headers=admin_b_headers
        )
    ).status_code == 404
    assert (
        await client.put(
            f"/api/v1/config/guardrails/{policy_id}/activate",
            headers=admin_b_headers,
        )
    ).status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", PROMPT_ENDPOINTS + GUARDRAIL_ENDPOINTS)
async def test_end_user_rejected_from_all_list_and_create_endpoints(
    client, end_user_a_headers, method, path
):
    kwargs = {"headers": end_user_a_headers}
    if method == "POST":
        if "prompt" in path:
            kwargs["json"] = {"text": "should fail"}
        else:
            kwargs["json"] = {"policy_json": {"x": 1}}

    res = await client.request(method, path, **kwargs)
    assert res.status_code == 403, f"{method} {path} returned {res.status_code}"


@pytest.mark.asyncio
async def test_end_user_rejected_from_activate_and_get_by_id(
    client, admin_a_headers, end_user_a_headers
):
    created = await client.post(
        "/api/v1/config/prompt",
        json={"text": "admin-only rules"},
        headers=admin_a_headers,
    )
    config_id = created.json()["id"]

    assert (
        await client.get(
            f"/api/v1/config/prompt/{config_id}", headers=end_user_a_headers
        )
    ).status_code == 403
    assert (
        await client.put(
            f"/api/v1/config/prompt/{config_id}/activate",
            headers=end_user_a_headers,
        )
    ).status_code == 403

    g = await client.post(
        "/api/v1/config/guardrails",
        json={"policy_json": {"a": 1}},
        headers=admin_a_headers,
    )
    policy_id = g.json()["id"]

    assert (
        await client.get(
            f"/api/v1/config/guardrails/{policy_id}", headers=end_user_a_headers
        )
    ).status_code == 403
    assert (
        await client.put(
            f"/api/v1/config/guardrails/{policy_id}/activate",
            headers=end_user_a_headers,
        )
    ).status_code == 403


@pytest.mark.asyncio
async def test_missing_token_rejected(client):
    res = await client.get("/api/v1/config/prompt")
    # HTTPBearer may return 401 or 403 depending on FastAPI/starlette version
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_activate_unknown_id_returns_404(client, admin_a_headers):
    fake_id = uuid.uuid4()
    res = await client.put(
        f"/api/v1/config/prompt/{fake_id}/activate",
        headers=admin_a_headers,
    )
    assert res.status_code == 404
