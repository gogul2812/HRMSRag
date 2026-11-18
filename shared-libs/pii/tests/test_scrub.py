"""Stage 10 — PII scrubbing tests."""

import os

os.environ["PII_SCRUB_MODE"] = "regex"

from rag_platform_pii import scrub, scrub_messages


def test_scrub_masks_email_and_phone():
    text = "Contact Ava at ava.chen@example.com or +1 (555) 123-4567 today."
    out = scrub(text)
    assert "ava.chen@example.com" not in out
    assert "[EMAIL]" in out
    assert "[PHONE]" in out


def test_scrub_masks_labeled_name():
    text = "Employee Name: Marcus Lee is available Q3."
    out = scrub(text)
    assert "Marcus Lee" not in out
    assert "[NAME]" in out


def test_scrub_messages_skips_when_force_local():
    msgs = [{"role": "user", "content": "email me at secret@corp.test"}]
    out = scrub_messages(msgs, force_local=True)
    assert out[0]["content"] == msgs[0]["content"]


def test_scrub_messages_cloud_path():
    msgs = [{"role": "user", "content": "email me at secret@corp.test"}]
    out = scrub_messages(msgs, force_local=False)
    assert "secret@corp.test" not in out[0]["content"]
    assert "[EMAIL]" in out[0]["content"]
