#!/usr/bin/env python3
"""Verify GlobalInstrumentationPlugin uses ADK BasePlugin hooks and SQLite helpers."""

import inspect
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SRC_ROOT))


def test_plugin_implements_adk_callbacks():
    from shared.instrumentation_plugin import GlobalInstrumentationPlugin

    required = (
        "before_run_callback",
        "after_run_callback",
        "before_tool_callback",
        "after_tool_callback",
        "after_model_callback",
        "on_tool_error_callback",
        "on_model_error_callback",
    )
    for name in required:
        method = getattr(GlobalInstrumentationPlugin, name)
        assert inspect.iscoroutinefunction(method), f"{name} must be async"
    print("ADK callback surface: OK")


def test_shared_audit_db_singleton():
    from shared.local_audit_db import get_shared_audit_db

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test_audit.db")
        db1 = get_shared_audit_db(path)
        db2 = get_shared_audit_db(path)
        assert db1 is db2
    print("Shared audit DB: OK")


def test_audit_context():
    from shared.audit_context import begin_audit_invocation, clear_audit_invocation, get_audit_context

    rid = begin_audit_invocation(source="test", oidc_claims={"sub": "operator@test"})
    ctx = get_audit_context()
    assert ctx["request_id"] == rid
    assert ctx["source"] == "test"
    clear_audit_invocation()
    assert get_audit_context() == {}
    print("Audit context: OK")


def main() -> int:
    test_plugin_implements_adk_callbacks()
    test_shared_audit_db_singleton()
    test_audit_context()
    print("Instrumentation tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
