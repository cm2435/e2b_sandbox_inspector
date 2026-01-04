"""Async client for E2B sandbox inspection."""

from __future__ import annotations

import os
from datetime import datetime

from e2b import AsyncSandbox
from e2b.api.client.models.sandbox_state import SandboxState
from e2b.sandbox.sandbox_api import SandboxQuery
from e2b_code_interpreter import AsyncSandbox as AsyncCodeSandbox

from e2b_sandbox_inspector.schemas import (
    CodeResult,
    CommandResult,
    FileInfo,
    SandboxInfo,
    SandboxMetrics,
    Summary,
)


class AsyncSandboxInspector:
    """Async client for inspecting and interacting with E2B sandboxes.

    Usage:
        inspector = AsyncSandboxInspector()
        sandboxes = await inspector.list_sandboxes()
        result = await inspector.exec("sbx_abc", "ls -la")
    """

    def __init__(self, api_key: str | None = None, default_timeout: int = 60):
        """Initialize the inspector.

        Args:
            api_key: E2B API key. Defaults to E2B_API_KEY environment variable.
            default_timeout: Default timeout for operations in seconds.
        """
        self.api_key = api_key or os.environ.get("E2B_API_KEY")
        if not self.api_key:
            raise ValueError(
                "E2B API key required. Pass api_key or set E2B_API_KEY environment variable."
            )
        self.default_timeout = default_timeout

    async def list_sandboxes(
        self,
        state: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> list[SandboxInfo]:
        """List all sandboxes, optionally filtered.

        Args:
            state: Filter by state ("running" or "paused")
            metadata: Filter by metadata key-value pairs

        Returns:
            List of SandboxInfo objects
        """
        query = None
        if state or metadata:
            state_filter = None
            if state:
                state_enum = SandboxState.RUNNING if state == "running" else SandboxState.PAUSED
                state_filter = [state_enum]
            query = SandboxQuery(state=state_filter, metadata=metadata)

        paginator = AsyncSandbox.list(query=query, api_key=self.api_key)
        sandboxes: list[SandboxInfo] = []

        # Fetch first page
        items = await paginator.next_items()
        while items:
            for sbx in items:
                sandboxes.append(
                    SandboxInfo(
                        sandbox_id=sbx.sandbox_id,
                        template_id=sbx.template_id,
                        name=sbx.name,
                        metadata=sbx.metadata,
                        state=sbx.state.value,
                        started_at=sbx.started_at,
                        end_at=sbx.end_at,
                        cpu_count=sbx.cpu_count,
                        memory_mb=sbx.memory_mb,
                    )
                )
            # Check if there are more pages
            if paginator.has_next:
                items = await paginator.next_items()
            else:
                break

        return sandboxes

    async def info(self, sandbox_id: str) -> SandboxInfo:
        """Get detailed information about a specific sandbox.

        Args:
            sandbox_id: The sandbox ID to inspect

        Returns:
            SandboxInfo object with sandbox details
        """
        sandbox = await AsyncSandbox.connect(sandbox_id=sandbox_id, api_key=self.api_key)
        sbx_info = await sandbox.get_info()  # type: ignore[call-overload]

        return SandboxInfo(
            sandbox_id=sbx_info.sandbox_id,
            template_id=sbx_info.template_id,
            name=sbx_info.name,
            metadata=sbx_info.metadata,
            state=sbx_info.state.value,
            started_at=sbx_info.started_at,
            end_at=sbx_info.end_at,
            cpu_count=sbx_info.cpu_count,
            memory_mb=sbx_info.memory_mb,
        )

    async def metrics(
        self,
        sandbox_id: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> SandboxMetrics | list[SandboxMetrics]:
        """Get resource usage metrics for a sandbox.

        Args:
            sandbox_id: The sandbox ID to get metrics for
            start: Start time for historical metrics (optional)
            end: End time for historical metrics (optional)

        Returns:
            SandboxMetrics object (current) or list of SandboxMetrics (historical)
        """
        sandbox = await AsyncSandbox.connect(sandbox_id=sandbox_id, api_key=self.api_key)
        raw_metrics = await sandbox.get_metrics(start=start, end=end)  # type: ignore[call-overload]

        results = [
            SandboxMetrics(
                cpu_count=m.cpu_count,
                cpu_pct=m.cpu_used_pct,
                mem_total_mb=m.mem_total // (1024 * 1024),
                mem_used_mb=m.mem_used // (1024 * 1024),
                disk_total_mb=m.disk_total // (1024 * 1024),
                disk_used_mb=m.disk_used // (1024 * 1024),
                timestamp=m.timestamp,
            )
            for m in raw_metrics
        ]

        # Return single metric if no time range specified, otherwise list
        if start is None and end is None and len(results) == 1:
            return results[0]
        return results

    async def exec(
        self,
        sandbox_id: str,
        command: str,
        timeout: int | None = None,
    ) -> CommandResult:
        """Execute a bash command inside a sandbox.

        Args:
            sandbox_id: The sandbox ID to execute in
            command: Bash command to execute
            timeout: Command timeout in seconds

        Returns:
            CommandResult with stdout, stderr, and exit_code
        """
        sandbox = await AsyncSandbox.connect(sandbox_id=sandbox_id, api_key=self.api_key)
        result = await sandbox.commands.run(
            command,
            timeout=timeout or self.default_timeout,
        )

        return CommandResult(
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            exit_code=result.exit_code,
        )

    async def python(
        self,
        sandbox_id: str,
        code: str,
        timeout: int | None = None,
    ) -> CodeResult:
        """Execute Python code inside a sandbox.

        Args:
            sandbox_id: The sandbox ID to execute in
            code: Python code to execute
            timeout: Execution timeout in seconds

        Returns:
            CodeResult with stdout, stderr, error, and results
        """
        # Use code interpreter sandbox for Python execution
        sandbox = await AsyncCodeSandbox.connect(sandbox_id=sandbox_id, api_key=self.api_key)
        execution = await sandbox.run_code(
            code,
            language="python",
            timeout=timeout or self.default_timeout,
        )

        stdout = ""
        stderr = ""
        if execution.logs:
            stdout = "".join(execution.logs.stdout) if execution.logs.stdout else ""
            stderr = "".join(execution.logs.stderr) if execution.logs.stderr else ""

        results = []
        if execution.results:
            results = [r.text if hasattr(r, "text") else str(r) for r in execution.results]

        return CodeResult(
            stdout=stdout,
            stderr=stderr,
            error=str(execution.error) if execution.error else None,
            results=results,
        )

    async def files(self, sandbox_id: str, path: str = "/") -> list[FileInfo]:
        """List files in a sandbox directory.

        Args:
            sandbox_id: The sandbox ID to list files in
            path: Directory path to list (default: root)

        Returns:
            List of FileInfo objects
        """
        sandbox = await AsyncSandbox.connect(sandbox_id=sandbox_id, api_key=self.api_key)

        # Use find command to get file info
        result = await sandbox.commands.run(
            f'find {path} -maxdepth 1 -printf "%y %s %p\\n" 2>/dev/null || ls -la {path}'
        )

        files: list[FileInfo] = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split(None, 2)
            if len(parts) >= 3:
                file_type, size, filepath = parts
                name = filepath.split("/")[-1] or filepath
                files.append(
                    FileInfo(
                        name=name,
                        path=filepath,
                        is_dir=file_type == "d",
                        size_bytes=int(size) if size.isdigit() else 0,
                    )
                )

        return files

    async def download(self, sandbox_id: str, remote_path: str) -> bytes:
        """Download a file from a sandbox.

        Args:
            sandbox_id: The sandbox ID to download from
            remote_path: Path to file in sandbox

        Returns:
            File contents as bytes
        """
        sandbox = await AsyncSandbox.connect(sandbox_id=sandbox_id, api_key=self.api_key)
        content = await sandbox.files.read(remote_path)
        if isinstance(content, str):
            return content.encode("utf-8")
        return content

    async def upload(self, sandbox_id: str, remote_path: str, content: bytes) -> None:
        """Upload a file to a sandbox.

        Args:
            sandbox_id: The sandbox ID to upload to
            remote_path: Destination path in sandbox
            content: File contents as bytes
        """
        sandbox = await AsyncSandbox.connect(sandbox_id=sandbox_id, api_key=self.api_key)
        await sandbox.files.write(remote_path, content)

    async def kill(self, sandbox_id: str) -> bool:
        """Terminate a sandbox.

        Args:
            sandbox_id: The sandbox ID to terminate

        Returns:
            True if killed, False if not found or already terminated
        """
        try:
            await AsyncSandbox.kill(sandbox_id=sandbox_id, api_key=self.api_key)
            return True
        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                return False
            raise

    async def kill_all(self, confirm: bool = False) -> int:
        """Terminate all sandboxes.

        Args:
            confirm: Must be True to actually kill (safety measure)

        Returns:
            Number of sandboxes terminated

        Raises:
            ValueError: If confirm is not True
        """
        if not confirm:
            raise ValueError("Must pass confirm=True to kill all sandboxes")

        sandboxes = await self.list_sandboxes()
        count = 0
        for sbx in sandboxes:
            if await self.kill(sbx.sandbox_id):
                count += 1
        return count

    async def summary(self) -> Summary:
        """Get an overview summary of all sandboxes.

        Returns:
            Summary object with aggregate statistics
        """
        sandboxes = await self.list_sandboxes()

        running = [s for s in sandboxes if s.state == "running"]
        paused = [s for s in sandboxes if s.state == "paused"]

        total_cpu = sum(s.cpu_count for s in sandboxes)
        total_memory = sum(s.memory_mb for s in sandboxes)

        oldest = min(sandboxes, key=lambda s: s.started_at) if sandboxes else None
        newest = max(sandboxes, key=lambda s: s.started_at) if sandboxes else None

        return Summary(
            running_count=len(running),
            paused_count=len(paused),
            total_count=len(sandboxes),
            total_cpu=total_cpu,
            total_memory_mb=total_memory,
            oldest_sandbox_id=oldest.sandbox_id if oldest else None,
            oldest_uptime=oldest.uptime if oldest else None,
            newest_sandbox_id=newest.sandbox_id if newest else None,
            newest_uptime=newest.uptime if newest else None,
        )
