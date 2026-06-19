#!/usr/bin/env python3
"""
Integration test: each orchestration agent creates, sends, and receives messages.

Layers (run in order; later layers skip gracefully when deps are missing):
  1. KQML create → parse round-trip for every agent pair
  2. Redis structured message (control decision → monitor read)
  3. KQML inform delivery (local timeline + optional HTTP)
  4. ADK agent natural-language round-trip (requires GEMINI_API_KEY)
  5. Docker HTTP /health (optional, when compose is up)

Usage:
  python3 src/tests/test_agent_messaging.py
  python3 src/tests/test_agent_messaging.py --skip-llm    # skip Gemini calls
  python3 src/tests/test_agent_messaging.py --require-llm # fail if LLM tests cannot run
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SRC_ROOT))


def load_env_file() -> None:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip("'\"")
        os.environ.setdefault(key, value)


load_env_file()
os.environ.setdefault("ENABLE_LOCAL_INSTRUMENTATION", "false")
os.environ.setdefault("AUTH_MODE", "local")

ORCHESTRATION_AGENTS = [
    "microgrid-agent",
    "control-agent",
    "researcher-agent",
    "monitor-agent",
]

AGENT_HTTP_HEALTH = {
    "microgrid-agent": "http://127.0.0.1:8000/health",
    "control-agent": "http://127.0.0.1:8001/health",
    "researcher-agent": "http://127.0.0.1:8002/health",
    "monitor-agent": "http://127.0.0.1:8006/health",
    "mcp-grid-state": "http://127.0.0.1:8010/health",
}

ADK_AGENT_CASES = [
    ("microgrid-agent", "microgrid_agent", "microgrid_agent", "Reply in one short sentence. Start with: MICROGRID-ACK"),
    ("control-agent", "control_agent", "control_agent", "Reply in one short sentence. Start with: CONTROL-ACK"),
    ("researcher-agent", "research_agent", "researcher_agent", "Reply in one short sentence. Start with: RESEARCH-ACK"),
    ("monitor-agent", "monitor_agent", "monitor_agent", "Reply in one short sentence. Start with: MONITOR-ACK"),
]


@dataclass
class TestResult:
    name: str
    status: str  # passed | failed | skipped
    detail: str = ""


@dataclass
class TestReport:
    results: List[TestResult] = field(default_factory=list)

    def add(self, name: str, status: str, detail: str = "") -> None:
        self.results.append(TestResult(name=name, status=status, detail=detail))
        icon = {"passed": "✓", "failed": "✗", "skipped": "○"}.get(status, "?")
        suffix = f" — {detail}" if detail else ""
        print(f"  {icon} {name}{suffix}")

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == "failed")

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == "passed")


def test_kqml_round_trip(report: TestReport) -> None:
    print("\n[1] KQML create / send / receive")
    from shared import kqml

    for sender in ORCHESTRATION_AGENTS:
        for receiver in ORCHESTRATION_AGENTS:
            if sender == receiver:
                continue
            subject = f"ping-{sender}-to-{receiver}"
            content = f"Test message from {sender} to {receiver}"
            try:
                msg = kqml.inform(
                    sender_id=sender,
                    receiver_id=receiver,
                    subject=subject,
                    content=content,
                    priority="low",
                )
                raw = msg.to_string()
                parsed = kqml.parse_kqml(raw)
                assert parsed.performative == "inform"
                assert parsed.sender_id == sender
                assert parsed.receiver_id == receiver
                assert parsed.subject == subject
                assert parsed.content == content
                report.add(f"kqml:{sender}->{receiver}", "passed")
            except Exception as exc:
                report.add(f"kqml:{sender}->{receiver}", "failed", str(exc))


def test_redis_control_monitor_message(report: TestReport) -> None:
    print("\n[2] Redis control decision → monitor read")
    import redis as redis_lib
    from shared import config

    candidates = []
    env_host = os.environ.get("REDIS_HOST", "localhost")
    env_port = int(os.environ.get("REDIS_PORT", 6379))
    candidates.append((env_host, env_port))
    if env_host not in ("localhost", "127.0.0.1"):
        candidates.append(("127.0.0.1", 6379))

    client = None
    for host, port in candidates:
        try:
            probe = redis_lib.Redis(
                host=host, port=port, decode_responses=True, socket_connect_timeout=2
            )
            probe.ping()
            client = probe
            config.redis_client = probe
            break
        except Exception:
            continue

    if client is None:
        report.add("redis:ping", "skipped", "Redis unavailable (start redis or docker compose)")
        return

    from shared.control_decisions import (
        list_control_decisions,
        record_control_decision,
    )

    marker = f"integration-test-{uuid.uuid4().hex[:8]}"
    try:
        sent = record_control_decision(
            action=f"test-action {marker}",
            rationale="Integration test decision for monitor visibility",
            inputs_considered={"test": True, "marker": marker},
        )
        assert sent["status"] == "success", sent
        decision_id = sent["decision_id"]

        received = list_control_decisions(limit=10, unreviewed_only=False)
        assert received["status"] == "success"
        ids = [d["decision_id"] for d in received.get("decisions", [])]
        assert decision_id in ids, "Monitor read path did not return new decision"

        report.add("redis:control->monitor", "passed", f"decision_id={decision_id}")
    except Exception as exc:
        report.add("redis:control->monitor", "failed", str(exc))


def test_kqml_inform_delivery(report: TestReport) -> None:
    print("\n[3] KQML inform delivery (monitor → control, monitor → microgrid)")
    from shared.monitor_comms import deliver_kqml_inform

    cases = [
        ("control-agent", "decision-review-test", "Monitor test feedback to control"),
        ("microgrid-agent", "system-pattern-alert-test", "Monitor test pattern alert"),
    ]
    for receiver, subject, content in cases:
        try:
            result = deliver_kqml_inform(
                receiver_id=receiver,
                subject=subject,
                content=content,
                priority="low",
            )
            assert result["status"] == "success", result
            assert "kqml_message" in result
            assert subject in result.get("subject", subject)
            http = result.get("http_delivery", "unknown")
            report.add(f"inform:monitor->{receiver}", "passed", f"http={http}")
        except Exception as exc:
            report.add(f"inform:monitor->{receiver}", "failed", str(exc))


async def _run_adk_message(runner, message: str, timeout: float = 90.0) -> str:
    from google.genai import types

    session = await runner.session_service.create_session(
        app_name=runner.app_name,
        user_id="integration-test",
    )
    user_message = types.Content(
        role="user",
        parts=[types.Part(text=message)],
    )
    collected: List[str] = []
    async with asyncio.timeout(timeout):
        async for event in runner.run_async(
            user_id=session.user_id,
            session_id=session.id,
            new_message=user_message,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text and not getattr(part, "thought", False):
                        collected.append(part.text)
    await runner.close()
    return (collected[-1] if collected else "").strip()


async def test_adk_agents_async(report: TestReport, require_llm: bool) -> None:
    print("\n[4] ADK agent message round-trip (Gemini)")
    if not os.environ.get("GEMINI_API_KEY"):
        msg = "GEMINI_API_KEY not set"
        status = "failed" if require_llm else "skipped"
        report.add("adk:all-agents", status, msg)
        return

    from google.adk.runners import InMemoryRunner
    from shared.runner_plugins import build_adk_plugins

    for agent_id, module_name, attr_name, prompt in ADK_AGENT_CASES:
        try:
            module = __import__(module_name, fromlist=[attr_name])
            agent = getattr(module, attr_name)
            plugins = build_adk_plugins(
                agent_id=agent_id,
                agent_role=agent_id.split("-")[0],
                verified_account=f"{agent_id}@test.local",
                enable_console_audit=False,
            )
            runner = InMemoryRunner(agent=agent, plugins=plugins)
            reply = await _run_adk_message(runner, prompt)
            if not reply:
                raise AssertionError("empty agent response")
            report.add(f"adk:{agent_id}", "passed", reply[:80].replace("\n", " "))
        except Exception as exc:
            report.add(f"adk:{agent_id}", "failed", str(exc))


def test_http_health(report: TestReport) -> None:
    print("\n[5] HTTP health (Docker optional)")
    try:
        import requests
    except ImportError:
        report.add("http:requests", "skipped", "requests not installed")
        return

    any_up = False
    for agent_id, url in AGENT_HTTP_HEALTH.items():
        try:
            resp = requests.get(url, timeout=3)
            if resp.status_code == 200:
                any_up = True
                body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                report.add(f"http:{agent_id}", "passed", str(body.get("status", resp.status_code)))
            else:
                report.add(f"http:{agent_id}", "failed", f"HTTP {resp.status_code}")
        except Exception as exc:
            report.add(f"http:{agent_id}", "skipped", str(exc))

    if not any_up:
        print("  (no Docker services detected — start with: docker compose up -d)")


def run_all(skip_llm: bool, require_llm: bool) -> int:
    report = TestReport()
    print("Agent messaging integration test")
    print("=" * 60)

    test_kqml_round_trip(report)
    test_redis_control_monitor_message(report)
    test_kqml_inform_delivery(report)

    if skip_llm:
        report.add("adk:all-agents", "skipped", "--skip-llm")
    else:
        asyncio.run(test_adk_agents_async(report, require_llm=require_llm))

    test_http_health(report)

    print("\n" + "=" * 60)
    print(
        f"Results: {report.passed} passed, "
        f"{sum(1 for r in report.results if r.status == 'failed')} failed, "
        f"{sum(1 for r in report.results if r.status == 'skipped')} skipped"
    )

    if report.failed:
        print("\nFailures:")
        for r in report.results:
            if r.status == "failed":
                print(f"  - {r.name}: {r.detail}")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent messaging integration test")
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip ADK/Gemini agent round-trip tests",
    )
    parser.add_argument(
        "--require-llm",
        action="store_true",
        help="Fail if GEMINI_API_KEY is missing (default: skip LLM tests)",
    )
    args = parser.parse_args()
    return run_all(skip_llm=args.skip_llm, require_llm=args.require_llm)


if __name__ == "__main__":
    raise SystemExit(main())
