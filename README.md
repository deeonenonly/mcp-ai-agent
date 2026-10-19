# MCP-Enabled AI Agent for Automated Test Execution, Failure Diagnosis, and Intelligent Reporting

## Overview
This project uses the Model Context Protocol (MCP) to connect an AI client with an automated software testing tool. It executes pytest tests, captures individual results, uses a local Ollama model to diagnose failures, and generates reports for review.

## Objectives
- Automate test execution through an MCP tool.
- Capture test outcomes and execution status.
- Diagnose failures using a local language model.
- Generate timestamped JSON reports.
- Compare historical test results to identify failure and recovery.
- Generate a human-readable Markdown summary.
- Keep AI suggestions separate from code changes and verified results.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core implementation |
| MCP | Client-server tool communication |
| pytest | Automated test execution |
| JUnit XML | Structured test-result extraction |
| Ollama (`llama3.2:3b`) | Local AI failure diagnosis |
| JSON | Structured reports |
| Markdown | Readable summaries |

## Architecture
See [System Architecture](docs/architecture.md) for the Mermaid diagram and component descriptions.

## Project Structure
- `server.py` — MCP server that runs pytest and returns test evidence.
- `client.py` — MCP client, AI diagnosis, and JSON report generation.
- `compare_reports.py` — Compares historical reports and checks recovery.
- `generate_summary.py` — Generates a Markdown testing summary.
- `sample_project/` — Sample application and automated tests.
- `reports/` — Timestamped JSON reports and summary files.
- `requirements.txt` — Python dependencies.
- `docs/architecture.md` — System architecture diagram.

## Prerequisites
- Python 3.10 or a compatible version supported by the installed packages.
- Ollama installed locally.
- The `llama3.2:3b` model available in Ollama for failure diagnosis.

## Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
