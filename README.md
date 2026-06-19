# Secure Microgrid AI Agent System

This project is a research platform that uses a team of 4 autonomous AI agents to help operators manage a localized microgrid. Renewable energy sources like solar and wind fluctuate constantly, making it a major challenge to balance power generation and load in real time. This project looks at how a connected group of AI agents can process grid data to help humans make faster, safer decisions.

The agents talk to each other over a secure HTTPS network using **mutual TLS (mTLS)** to verify each other's identity. Their messages are structured using a standard format called **KQML (Knowledge Query and Manipulation Language)**.

---

## The 4 Agent Team

Instead of building a separate agent for every individual solar panel or battery, the system relies on a core team of 4 integrated agents to coordinate and manage the grid:

1. **Microgrid Agent:** Handles long term strategy across hours, days, or weeks. It tracks broad, high level grid patterns and has the ultimate authority to override the system or set new operational rules.
2. **Control Agent:** Makes the minute by minute tactical choices to keep power supply, electricity usage, and battery storage perfectly balanced. It must explicitly explain its reasoning before moving forward with an action.
3. **Researcher Agent:** Uses RAG to look up grid standards, documentation, and past fixes. It delivers clear, unbiased facts to the Control Agent without injecting its own opinions or suggestions.
4. **Monitor Agent:** Has full visibility into the entire system. It reviews the Control Agent's decisions, weighs the pros and cons, checks for safety violations, and flags risks for human operators.

---

## Security and System Tracking

* **Identity Verification:** Every agent must show a valid cryptographic certificate to talk to another agent over HTTPS. This keeps the internal communication secure.
* **Structured Messaging:** Agents package their requests inside clear KQML templates, making their interactions highly predictable and easy to parse.
* **Step-by-Step History:** A custom tracking plugin intercepts agent conversations and saves their reasoning process inside a local database file (`audit_trail.db`) for easy review.

---

## Current Project Status and Next Steps

### The Token and Rate Limit Problem

Because a multi agent system requires a lot of continuous back and forth conversation, safety auditing, and documentation lookups, it needs quite a number of tokens. Right now, the free Google Gemini API is highly restricted and does not provide enough room for the agents to successfully interact with existing grid data. The system hits provider rate limits almost immediately, stopping the agents from finishing real tasks.

### Next Steps and Known gaps

- I need to optimize the agent prompts and limit how often the Monitor and Researcher agents run. Delimma: lower token counts while keeping decision quality high.
- I am looking for a more sustainable source of API tokens or credits so the multi-agent team can run uninterrupted.
- My initial tests proved that having the agents read static text logs wasn't useful for realistic grid management. I am now working to integrate actual time series datasets (from Kaggle and elsewhere) so the system can process real, constantly fluctuating numbers like solar output, battery percentages, and power load.
- UI auth uses a placeholder `demo-token`; production path needs Keycloak tokens wired in the UI.
- Monitor auto review on every control decision requires Control to call `record_control_decision` and Monitor to be invoked (not a background agent yet).
- No cloud deployment or production hardening.
- Still developing corpus for RAG: deciding on what documents and size of corpus.

---

## Getting Started

For a guide on how to generate the security certificates, spin up the backend services via Docker, and launch the user interface, please see the Technical_ReadME.md in this directory.

---
