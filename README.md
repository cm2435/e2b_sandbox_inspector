# e2b-sandbox-inspector

A Python package for debugging, monitoring, and interacting with running E2B sandboxes. Provides both programmatic API and CLI for inspecting sandbox state, executing commands, and managing sandbox lifecycle.

## Installation

```bash
pip install e2b-sandbox-inspector
```

Or with uv:
```bash
uv add e2b-sandbox-inspector
```

## Quick Start

### CLI

```bash
# Set your API key
export E2B_API_KEY=your_key_here

# List all running sandboxes
e2b-inspect list

# Get detailed info on a sandbox
e2b-inspect info sbx_abc123

# Run a command inside a sandbox
e2b-inspect exec sbx_abc123 "ls -la /workspace"

# Run Python code
e2b-inspect python sbx_abc123 "import os; print(os.getcwd())"

# Get resource metrics
e2b-inspect metrics sbx_abc123

# List files in sandbox
e2b-inspect files sbx_abc123 /workspace

# Download a file
e2b-inspect download sbx_abc123 /workspace/output.csv ./local_output.csv

# Kill a sandbox
e2b-inspect kill sbx_abc123

# Kill all sandboxes (with confirmation)
e2b-inspect kill-all
```

### Python API (Async)

```python
from e2b_sandbox_inspector import AsyncSandboxInspector

async def debug_sandbox():
    inspector = AsyncSandboxInspector()  # Uses E2B_API_KEY from env
    
    # List all running sandboxes
    sandboxes = await inspector.list_sandboxes()
    for sbx in sandboxes:
        print(f"{sbx.sandbox_id}: up {sbx.uptime}, {sbx.time_remaining} remaining")
    
    # Get metrics for a specific sandbox
    metrics = await inspector.metrics("sbx_abc123")
    print(f"CPU: {metrics.cpu_pct}%, Mem: {metrics.mem_used_mb}/{metrics.mem_total_mb}MB")
    
    # Execute a bash command
    result = await inspector.exec("sbx_abc123", "ps aux")
    print(result.stdout)
    
    # Execute Python code
    result = await inspector.python("sbx_abc123", "print('hello from sandbox')")
    print(result.stdout)
    
    # List files
    files = await inspector.files("sbx_abc123", "/workspace")
    for f in files:
        print(f"{f.name} ({f.size_bytes} bytes)")
    
    # Download a file
    content = await inspector.download("sbx_abc123", "/workspace/output.csv")
    
    # Kill sandbox
    await inspector.kill("sbx_abc123")
```

### Python API (Sync)

```python
from e2b_sandbox_inspector import SandboxInspector

def debug_sandbox():
    inspector = SandboxInspector()
    
    # Same API as async, but synchronous
    sandboxes = inspector.list_sandboxes()
    for sbx in sandboxes:
        print(f"{sbx.sandbox_id}: {sbx.state}")
    
    result = inspector.exec("sbx_abc123", "echo hello")
    print(result.stdout)
```

## API Reference

### Client Classes

The package provides two client classes that mirror E2B's SDK pattern:

| Class | Use Case |
|-------|----------|
| `SandboxInspector` | Sync contexts (scripts, CLI, simple tools) |
| `AsyncSandboxInspector` | Async contexts (FastAPI, async agents, high concurrency) |

Both classes share the same method signatures - the only difference is that `AsyncSandboxInspector` methods are coroutines.

### Methods

#### `list_sandboxes(state: str | None = None, metadata: dict | None = None) -> list[SandboxInfo]`

List all sandboxes, optionally filtered by state or metadata.

```python
# List all
all_sandboxes = inspector.list_sandboxes()

# List only running
running = inspector.list_sandboxes(state="running")

# Filter by metadata
tagged = inspector.list_sandboxes(metadata={"project": "my-project"})
```

**Returns:** List of `SandboxInfo` objects with fields:
- `sandbox_id: str` - Unique sandbox identifier
- `template_id: str` - Template used to create sandbox
- `name: str | None` - Optional sandbox name
- `metadata: dict[str, str]` - User-defined metadata
- `state: str` - "running" or "paused"
- `started_at: datetime` - When sandbox was created
- `end_at: datetime` - When sandbox will timeout
- `cpu_count: int` - Number of CPU cores
- `memory_mb: int` - Memory allocation in MB
- `uptime: timedelta` - Time since creation (computed)
- `time_remaining: timedelta` - Time until timeout (computed)

---

#### `info(sandbox_id: str) -> SandboxInfo`

Get detailed information about a specific sandbox.

```python
info = inspector.info("sbx_abc123")
print(f"Template: {info.template_id}")
print(f"Uptime: {info.uptime}")
```

---

#### `metrics(sandbox_id: str, start: datetime | None = None, end: datetime | None = None) -> SandboxMetrics | list[SandboxMetrics]`

Get resource usage metrics for a sandbox.

```python
# Current metrics
m = inspector.metrics("sbx_abc123")
print(f"CPU: {m.cpu_pct}%")
print(f"Memory: {m.mem_used_mb}/{m.mem_total_mb} MB ({m.mem_pct}%)")
print(f"Disk: {m.disk_used_mb}/{m.disk_total_mb} MB")

# Historical metrics (time series)
from datetime import datetime, timedelta
history = inspector.metrics(
    "sbx_abc123",
    start=datetime.now() - timedelta(minutes=10),
    end=datetime.now()
)
for point in history:
    print(f"{point.timestamp}: CPU {point.cpu_pct}%")
```

**Returns:** `SandboxMetrics` object with fields:
- `cpu_count: int` - Number of CPU cores
- `cpu_pct: float` - CPU usage percentage
- `mem_total_mb: int` - Total memory in MB
- `mem_used_mb: int` - Used memory in MB
- `mem_pct: float` - Memory usage percentage (computed)
- `disk_total_mb: int` - Total disk in MB
- `disk_used_mb: int` - Used disk in MB
- `disk_pct: float` - Disk usage percentage (computed)
- `timestamp: datetime` - When metrics were captured

---

#### `exec(sandbox_id: str, command: str, timeout: int = 60) -> CommandResult`

Execute a bash command inside a sandbox.

```python
result = inspector.exec("sbx_abc123", "ls -la /workspace")
print(result.stdout)
if result.exit_code != 0:
    print(f"Error: {result.stderr}")
```

**Returns:** `CommandResult` object with fields:
- `stdout: str` - Standard output
- `stderr: str` - Standard error
- `exit_code: int` - Exit code (0 = success)

---

#### `python(sandbox_id: str, code: str, timeout: int = 60) -> CodeResult`

Execute Python code inside a sandbox.

```python
result = inspector.python("sbx_abc123", """
import sys
print(f"Python {sys.version}")
print(f"Path: {sys.path}")
""")
print(result.stdout)
```

**Returns:** `CodeResult` object with fields:
- `stdout: str` - Standard output
- `stderr: str` - Standard error
- `error: str | None` - Execution error if any
- `results: list[Any]` - Return values from code cells

---

#### `files(sandbox_id: str, path: str = "/") -> list[FileInfo]`

List files in a sandbox directory.

```python
files = inspector.files("sbx_abc123", "/workspace")
for f in files:
    print(f"{'📁' if f.is_dir else '📄'} {f.name} ({f.size_bytes} bytes)")
```

**Returns:** List of `FileInfo` objects with fields:
- `name: str` - File/directory name
- `path: str` - Full path
- `is_dir: bool` - True if directory
- `size_bytes: int` - Size in bytes (0 for directories)

---

#### `download(sandbox_id: str, remote_path: str) -> bytes`

Download a file from a sandbox.

```python
content = inspector.download("sbx_abc123", "/workspace/output.csv")
with open("local.csv", "wb") as f:
    f.write(content)
```

---

#### `upload(sandbox_id: str, remote_path: str, content: bytes) -> None`

Upload a file to a sandbox.

```python
with open("config.json", "rb") as f:
    inspector.upload("sbx_abc123", "/workspace/config.json", f.read())
```

---

#### `kill(sandbox_id: str) -> bool`

Terminate a sandbox.

```python
killed = inspector.kill("sbx_abc123")
print("Killed" if killed else "Not found or already terminated")
```

---

#### `kill_all(confirm: bool = False) -> int`

Terminate all sandboxes. Requires `confirm=True` as a safety measure.

```python
count = inspector.kill_all(confirm=True)
print(f"Terminated {count} sandboxes")
```

---

#### `summary() -> Summary`

Get an overview of all sandboxes.

```python
s = inspector.summary()
print(f"Running: {s.running_count}")
print(f"Paused: {s.paused_count}")
print(f"Total CPU cores: {s.total_cpu}")
print(f"Total memory: {s.total_memory_mb} MB")
print(f"Oldest: {s.oldest_sandbox_id} ({s.oldest_uptime})")
```

**Returns:** `Summary` object with fields:
- `running_count: int`
- `paused_count: int`
- `total_count: int`
- `total_cpu: int` - Sum of all CPU cores
- `total_memory_mb: int` - Sum of all memory allocations
- `oldest_sandbox_id: str | None`
- `oldest_uptime: timedelta | None`
- `newest_sandbox_id: str | None`
- `newest_uptime: timedelta | None`

---

## CLI Reference

```
e2b-inspect - Debug and manage E2B sandboxes

COMMANDS:
  list                    List all sandboxes
    --state TEXT          Filter by state (running, paused)
    --format TEXT         Output format (table, json)
  
  info SANDBOX_ID         Show detailed sandbox info
    --format TEXT         Output format (table, json)
  
  metrics SANDBOX_ID      Show resource metrics
    --watch               Continuously update (every 2s)
  
  exec SANDBOX_ID CMD     Execute bash command
    --timeout INT         Command timeout in seconds (default: 60)
  
  python SANDBOX_ID CODE  Execute Python code
    --timeout INT         Execution timeout in seconds (default: 60)
  
  files SANDBOX_ID [PATH] List files in directory
    --recursive           List recursively
  
  download SANDBOX_ID REMOTE LOCAL
                          Download file from sandbox
  
  upload SANDBOX_ID LOCAL REMOTE
                          Upload file to sandbox
  
  kill SANDBOX_ID         Terminate a sandbox
    --force               Skip confirmation
  
  kill-all                Terminate ALL sandboxes
    --force               Skip confirmation (dangerous!)
  
  summary                 Show overview of all sandboxes
    --format TEXT         Output format (table, json)

GLOBAL OPTIONS:
  --api-key TEXT          E2B API key (default: $E2B_API_KEY)
  --help                  Show help message
```

## Package Structure

```
e2b_sandbox_inspector/
├── pyproject.toml
├── README.md
├── src/
│   └── e2b_sandbox_inspector/
│       ├── __init__.py           # Public exports
│       ├── schemas.py            # Pydantic models (SandboxInfo, Metrics, etc.)
│       ├── async_client.py       # AsyncSandboxInspector
│       ├── sync_client.py        # SandboxInspector  
│       └── cli.py                # Typer CLI
└── tests/
    ├── __init__.py
    ├── test_async_client.py
    ├── test_sync_client.py
    ├── test_schemas.py
    └── test_cli.py
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `E2B_API_KEY` | Your E2B API key | Yes |

### Programmatic Configuration

```python
from e2b_sandbox_inspector import SandboxInspector

# Explicit API key
inspector = SandboxInspector(api_key="e2b_...")

# Custom timeout for all operations
inspector = SandboxInspector(default_timeout=120)
```

## Use Cases

### Debugging a Stuck Job

```bash
# Find your sandbox
e2b-inspect list --state running

# Check what's running
e2b-inspect exec sbx_abc123 "ps aux"

# Check resource usage
e2b-inspect metrics sbx_abc123

# Look at the workspace
e2b-inspect files sbx_abc123 /workspace

# Read a log file
e2b-inspect exec sbx_abc123 "cat /workspace/debug.log"
```

### Monitoring Active Sandboxes

```bash
# Quick summary
e2b-inspect summary

# Watch metrics in real-time
e2b-inspect metrics sbx_abc123 --watch
```

### Emergency Cleanup

```bash
# See what's running
e2b-inspect list

# Kill everything (careful!)
e2b-inspect kill-all --force
```

### Programmatic Monitoring

```python
from e2b_sandbox_inspector import AsyncSandboxInspector
import asyncio

async def monitor_sandboxes():
    inspector = AsyncSandboxInspector()
    
    while True:
        summary = await inspector.summary()
        print(f"Active: {summary.running_count}, Memory: {summary.total_memory_mb}MB")
        
        # Alert on high resource usage
        for sbx in await inspector.list_sandboxes(state="running"):
            metrics = await inspector.metrics(sbx.sandbox_id)
            if metrics.cpu_pct > 90:
                print(f"⚠️  High CPU on {sbx.sandbox_id}: {metrics.cpu_pct}%")
        
        await asyncio.sleep(30)
```

## Development

```bash
# Clone and install
git clone https://github.com/yourorg/e2b-sandbox-inspector
cd e2b-sandbox-inspector
uv sync

# Run tests
uv run pytest

# Run linting
uv run ruff check src/
uv run ruff format src/

# Type checking
uv run ty check src/
```

## License

MIT

