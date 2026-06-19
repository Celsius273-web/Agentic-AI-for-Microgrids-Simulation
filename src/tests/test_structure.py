#!/usr/bin/env python3
"""Verify repo layout and key file contents (no Docker or Gemini required)."""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = Path(__file__).resolve().parents[1]


def check_file_structure() -> bool:
    required = [
        SRC_ROOT / "shared/docs/grid_standards.md",
        SRC_ROOT / "shared/docs/best_practices.md",
        SRC_ROOT / "shared/docs/past_decisions.md",
        SRC_ROOT / "microgrid_ui/src/ChatInterface.jsx",
        SRC_ROOT / "microgrid_ui/package.json",
        REPO_ROOT / "monitor_agent.py",
        REPO_ROOT / "control_agent.py",
        SRC_ROOT / "chat_server.py",
        SRC_ROOT / "demo_chat_simple.py",
        SRC_ROOT / "shared/control_decisions.py",
        SRC_ROOT / "shared/monitor_data.py",
        SRC_ROOT / "shared/runner_plugins.py",
        SRC_ROOT / "shared/audit_context.py",
        SRC_ROOT / "shared/instrumentation_plugin.py",
        SRC_ROOT / "shared/rag.py",
        REPO_ROOT / "requirements.txt",
        REPO_ROOT / "Setup.md",
        REPO_ROOT / "README.md",
    ]
    missing = [str(p.relative_to(REPO_ROOT)) for p in required if not p.exists()]
    if missing:
        print("Missing:", ", ".join(missing))
        return False
    return True


def check_content() -> bool:
    ok = True
    chat_ui = (SRC_ROOT / "microgrid_ui/src/ChatInterface.jsx").read_text()
    if not all(s in chat_ui for s in ("useState", "axios", "/chat")):
        print("ChatInterface.jsx missing expected hooks/API usage")
        ok = False

    chat_server = (SRC_ROOT / "chat_server.py").read_text()
    if not all(s in chat_server for s in ("FastAPI", "/chat", "microgrid_agent")):
        print("chat_server.py missing expected FastAPI/agent wiring")
        ok = False

    rag = (SRC_ROOT / "shared/rag.py").read_text()
    if not all(s in rag for s in ("chromadb", "search_docs", "SentenceTransformer")):
        print("shared/rag.py missing expected RAG components")
        ok = False
    return ok


def main() -> int:
    os.chdir(REPO_ROOT)
    structure_ok = check_file_structure()
    content_ok = check_content() if structure_ok else False
    if structure_ok and content_ok:
        print("Structure check passed.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
