"""Stage 10 — RLS migration presence check."""

from pathlib import Path


def test_rls_migration_exists_and_enables_policies():
    root = Path(__file__).resolve().parents[2]
    # When run from services/*/tests this may differ; locate from rag-platform
    candidates = list(Path("C:/Users/TISED-014/Desktop/RAG HRMS/RAG HRMS/rag-platform").glob(
        "data/postgres/alembic/versions/0005*.py"
    ))
    if not candidates:
        # relative from repo when pytest cwd is rag-platform
        candidates = list(Path("data/postgres/alembic/versions").glob("0005*.py"))
    if not candidates:
        here = Path(__file__).resolve()
        for parent in here.parents:
            hit = list((parent / "data/postgres/alembic/versions").glob("0005*.py"))
            if hit:
                candidates = hit
                break
    assert candidates, "migration 0005 (RLS) missing"
    text = candidates[0].read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in text
    assert "app_current_tenant_id" in text
    assert "tenant_isolation" in text
    assert "FORCE ROW LEVEL SECURITY" in text
