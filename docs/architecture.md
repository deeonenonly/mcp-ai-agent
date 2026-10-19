# System Architecture

```mermaid
flowchart TD
    U["User"]
    C["MCP Client<br/>client.py"]
    S["MCP Server<br/>server.py"]
    P["pytest Test Runner"]
    T["Sample Application<br/>app.py and test_app.py"]
    R["Verified Test Results<br/>JUnit XML and pytest output"]
    O["Local Ollama Model<br/>llama3.2:3b"]
    J["Timestamped JSON Reports"]
    H["Report Comparison<br/>compare_reports.py"]
    M["Markdown Summary<br/>generate_summary.py"]

    U -->|"Testing request"| C
    C <-->|"MCP over stdio"| S
    S --> P
    P --> T
    T --> R
    R --> S
    S -->|"Test evidence"| C
    C -->|"Only when tests fail"| O
    O -->|"Suggested diagnosis"| C
    C --> J
    J --> H
    H -->|"Comparison results"| M
    J --> M
    M -->|"latest_test_summary.md"| U
