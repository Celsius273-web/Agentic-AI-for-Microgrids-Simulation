#!/usr/bin/env python3
"""Verify repo layout and key file contents (no Docker or Gemini required)."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check_file_structure() -> bool:
    required = [
        "shared/docs/grid_standards.md",
        "shared/docs/best_practices.md",
        "shared/docs/past_decisions.md",
        "microgrid_ui/src/ChatInterface.jsx",
        "microgrid_ui/package.json",
        "monitor_agent.py",
        "control_agent.py",
        "chat_server.py",
        "demo_chat_simple.py",
        "shared/control_decisions.py",
        "shared/monitor_data.py",
        "shared/rag.py",
        "requirements.txt",
        "README.md",
    ]
    missing = [p for p in required if not (ROOT / p).exists()]
    if missing:
        print("Missing:", ", ".join(missing))
        return False
    return True


def check_content() -> bool:
    ok = True
    chat_ui = (ROOT / "microgrid_ui/src/ChatInterface.jsx").read_text()
    if not all(s in chat_ui for s in ("useState", "axios", "/chat")):
        print("ChatInterface.jsx missing expected hooks/API usage")
        ok = False

    chat_server = (ROOT / "chat_server.py").read_text()
    if not all(s in chat_server for s in ("FastAPI", "/chat", "microgrid_agent")):
        print("chat_server.py missing expected FastAPI/agent wiring")
        ok = False

    rag = (ROOT / "shared/rag.py").read_text()
    if not all(s in rag for s in ("chromadb", "search_docs", "SentenceTransformer")):
        print("shared/rag.py missing expected RAG components")
        ok = False
    return ok


def main() -> int:
    os.chdir(ROOT)
    structure_ok = check_file_structure()
    content_ok = check_content() if structure_ok else False
    if structure_ok and content_ok:
        print("Structure check passed.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
