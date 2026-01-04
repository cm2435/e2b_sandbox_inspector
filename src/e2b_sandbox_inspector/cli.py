"""CLI for E2B Sandbox Inspector."""

import json
from datetime import timedelta
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from e2b_sandbox_inspector.sync_client import SandboxInspector

app = typer.Typer(
    name="e2b-inspect",
    help="Debug, monitor, and interact with running E2B sandboxes.",
    no_args_is_help=True,
)
console = Console()


def _format_timedelta(td: timedelta | None) -> str:
    """Format timedelta as human-readable string."""
    if td is None:
        return "-"
    total_seconds = int(td.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds}s"
    elif total_seconds < 3600:
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}m {seconds}s"
    else:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours}h {minutes}m"


@app.command()
def list(
    state: Annotated[str | None, typer.Option(help="Filter by state (running, paused)")] = None,
    format: Annotated[str, typer.Option(help="Output format (table, json)")] = "table",
    api_key: Annotated[str | None, typer.Option(envvar="E2B_API_KEY", help="E2B API key")] = None,
):
    """List all sandboxes."""
    inspector = SandboxInspector(api_key=api_key)
    sandboxes = inspector.list_sandboxes(state=state)

    if format == "json":
        output = [s.model_dump(mode="json") for s in sandboxes]
        console.print_json(json.dumps(output, default=str))
        return

    if not sandboxes:
        console.print("[dim]No sandboxes found[/dim]")
        return

    table = Table(title=f"E2B Sandboxes ({len(sandboxes)} total)")
    table.add_column("Sandbox ID", style="cyan")
    table.add_column("State", style="green")
    table.add_column("Template")
    table.add_column("CPU")
    table.add_column("Memory")
    table.add_column("Uptime")
    table.add_column("Remaining")

    for sbx in sandboxes:
        state_style = "green" if sbx.state == "running" else "yellow"
        table.add_row(
            sbx.sandbox_id,
            f"[{state_style}]{sbx.state}[/{state_style}]",
            sbx.template_id[:20] + "..." if len(sbx.template_id) > 20 else sbx.template_id,
            str(sbx.cpu_count),
            f"{sbx.memory_mb}MB",
            _format_timedelta(sbx.uptime),
            _format_timedelta(sbx.time_remaining),
        )

    console.print(table)


@app.command()
def info(
    sandbox_id: Annotated[str, typer.Argument(help="Sandbox ID to inspect")],
    format: Annotated[str, typer.Option(help="Output format (table, json)")] = "table",
    api_key: Annotated[str | None, typer.Option(envvar="E2B_API_KEY", help="E2B API key")] = None,
):
    """Show detailed sandbox info."""
    inspector = SandboxInspector(api_key=api_key)
    sbx = inspector.info(sandbox_id)

    if format == "json":
        console.print_json(json.dumps(sbx.model_dump(mode="json"), default=str))
        return

    table = Table(title=f"Sandbox: {sandbox_id}")
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    table.add_row("Sandbox ID", sbx.sandbox_id)
    table.add_row("State", f"[green]{sbx.state}[/green]" if sbx.state == "running" else sbx.state)
    table.add_row("Template", sbx.template_id)
    table.add_row("Name", sbx.name or "-")
    table.add_row("CPU", f"{sbx.cpu_count} cores")
    table.add_row("Memory", f"{sbx.memory_mb} MB")
    table.add_row("Started", str(sbx.started_at))
    table.add_row("Timeout", str(sbx.end_at))
    table.add_row("Uptime", _format_timedelta(sbx.uptime))
    table.add_row("Remaining", _format_timedelta(sbx.time_remaining))
    if sbx.metadata:
        table.add_row("Metadata", json.dumps(sbx.metadata, indent=2))

    console.print(table)


@app.command()
def metrics(
    sandbox_id: Annotated[str, typer.Argument(help="Sandbox ID to get metrics for")],
    watch: Annotated[bool, typer.Option(help="Continuously update (every 2s)")] = False,
    api_key: Annotated[str | None, typer.Option(envvar="E2B_API_KEY", help="E2B API key")] = None,
):
    """Show resource metrics for a sandbox."""
    import time

    inspector = SandboxInspector(api_key=api_key)

    def show_metrics():
        m = inspector.metrics(sandbox_id)
        if isinstance(m, list):
            m = m[0] if m else None
        if m is None:
            console.print("[red]No metrics available[/red]")
            return

        table = Table(title=f"Metrics: {sandbox_id}")
        table.add_column("Metric", style="cyan")
        table.add_column("Value")
        table.add_column("Usage")

        table.add_row("CPU", f"{m.cpu_count} cores", f"[yellow]{m.cpu_pct:.1f}%[/yellow]")
        table.add_row(
            "Memory",
            f"{m.mem_used_mb}/{m.mem_total_mb} MB",
            f"[yellow]{m.mem_pct:.1f}%[/yellow]",
        )
        table.add_row(
            "Disk",
            f"{m.disk_used_mb}/{m.disk_total_mb} MB",
            f"[yellow]{m.disk_pct:.1f}%[/yellow]",
        )
        table.add_row("Timestamp", str(m.timestamp), "")

        console.print(table)

    if watch:
        with console.status("[bold green]Watching metrics..."):
            while True:
                console.clear()
                show_metrics()
                time.sleep(2)
    else:
        show_metrics()


@app.command("exec")
def exec_cmd(
    sandbox_id: Annotated[str, typer.Argument(help="Sandbox ID to execute in")],
    command: Annotated[str, typer.Argument(help="Bash command to execute")],
    timeout: Annotated[int, typer.Option(help="Command timeout in seconds")] = 60,
    api_key: Annotated[str | None, typer.Option(envvar="E2B_API_KEY", help="E2B API key")] = None,
):
    """Execute a bash command in a sandbox."""
    inspector = SandboxInspector(api_key=api_key)
    result = inspector.exec(sandbox_id, command, timeout=timeout)

    if result.stdout:
        console.print(result.stdout)
    if result.stderr:
        console.print(f"[red]{result.stderr}[/red]")

    if result.exit_code != 0:
        raise typer.Exit(result.exit_code)


@app.command("python")
def python_cmd(
    sandbox_id: Annotated[str, typer.Argument(help="Sandbox ID to execute in")],
    code: Annotated[str, typer.Argument(help="Python code to execute")],
    timeout: Annotated[int, typer.Option(help="Execution timeout in seconds")] = 60,
    api_key: Annotated[str | None, typer.Option(envvar="E2B_API_KEY", help="E2B API key")] = None,
):
    """Execute Python code in a sandbox."""
    inspector = SandboxInspector(api_key=api_key)
    result = inspector.python(sandbox_id, code, timeout=timeout)

    if result.stdout:
        console.print(result.stdout)
    if result.stderr:
        console.print(f"[dim]{result.stderr}[/dim]")
    if result.results:
        console.print("[cyan]Results:[/cyan]")
        for r in result.results:
            console.print(f"  {r}")
    if result.error:
        console.print(f"[red]Error: {result.error}[/red]")
        raise typer.Exit(1)


@app.command()
def files(
    sandbox_id: Annotated[str, typer.Argument(help="Sandbox ID to list files in")],
    path: Annotated[str, typer.Argument(help="Directory path to list")] = "/",
    api_key: Annotated[str | None, typer.Option(envvar="E2B_API_KEY", help="E2B API key")] = None,
):
    """List files in a sandbox directory."""
    inspector = SandboxInspector(api_key=api_key)
    file_list = inspector.files(sandbox_id, path)

    if not file_list:
        console.print("[dim]No files found[/dim]")
        return

    table = Table(title=f"Files in {path}")
    table.add_column("Type", width=4)
    table.add_column("Name")
    table.add_column("Size", justify="right")

    for f in sorted(file_list, key=lambda x: (not x.is_dir, x.name)):
        icon = "📁" if f.is_dir else "📄"
        size = "-" if f.is_dir else f"{f.size_bytes:,}"
        table.add_row(icon, f.name, size)

    console.print(table)


@app.command()
def download(
    sandbox_id: Annotated[str, typer.Argument(help="Sandbox ID to download from")],
    remote_path: Annotated[str, typer.Argument(help="Path to file in sandbox")],
    local_path: Annotated[str, typer.Argument(help="Local destination path")],
    api_key: Annotated[str | None, typer.Option(envvar="E2B_API_KEY", help="E2B API key")] = None,
):
    """Download a file from a sandbox."""
    inspector = SandboxInspector(api_key=api_key)
    content = inspector.download(sandbox_id, remote_path)

    with open(local_path, "wb") as f:
        f.write(content)

    console.print(f"[green]Downloaded {len(content):,} bytes to {local_path}[/green]")


@app.command()
def upload(
    sandbox_id: Annotated[str, typer.Argument(help="Sandbox ID to upload to")],
    local_path: Annotated[str, typer.Argument(help="Local file path")],
    remote_path: Annotated[str, typer.Argument(help="Destination path in sandbox")],
    api_key: Annotated[str | None, typer.Option(envvar="E2B_API_KEY", help="E2B API key")] = None,
):
    """Upload a file to a sandbox."""
    with open(local_path, "rb") as f:
        content = f.read()

    inspector = SandboxInspector(api_key=api_key)
    inspector.upload(sandbox_id, remote_path, content)

    console.print(f"[green]Uploaded {len(content):,} bytes to {remote_path}[/green]")


@app.command()
def kill(
    sandbox_id: Annotated[str, typer.Argument(help="Sandbox ID to terminate")],
    force: Annotated[bool, typer.Option(help="Skip confirmation")] = False,
    api_key: Annotated[str | None, typer.Option(envvar="E2B_API_KEY", help="E2B API key")] = None,
):
    """Terminate a sandbox."""
    if not force:
        confirm = typer.confirm(f"Are you sure you want to kill sandbox {sandbox_id}?")
        if not confirm:
            raise typer.Abort()

    inspector = SandboxInspector(api_key=api_key)
    killed = inspector.kill(sandbox_id)

    if killed:
        console.print(f"[green]Terminated sandbox {sandbox_id}[/green]")
    else:
        console.print(f"[yellow]Sandbox {sandbox_id} not found or already terminated[/yellow]")


@app.command("kill-all")
def kill_all(
    force: Annotated[bool, typer.Option(help="Skip confirmation (dangerous!)")] = False,
    api_key: Annotated[str | None, typer.Option(envvar="E2B_API_KEY", help="E2B API key")] = None,
):
    """Terminate ALL sandboxes."""
    inspector = SandboxInspector(api_key=api_key)
    sandboxes = inspector.list_sandboxes()

    if not sandboxes:
        console.print("[dim]No sandboxes to kill[/dim]")
        return

    if not force:
        console.print(f"[red bold]This will terminate {len(sandboxes)} sandbox(es)![/red bold]")
        confirm = typer.confirm("Are you absolutely sure?")
        if not confirm:
            raise typer.Abort()

    count = inspector.kill_all(confirm=True)
    console.print(f"[green]Terminated {count} sandbox(es)[/green]")


@app.command()
def summary(
    format: Annotated[str, typer.Option(help="Output format (table, json)")] = "table",
    api_key: Annotated[str | None, typer.Option(envvar="E2B_API_KEY", help="E2B API key")] = None,
):
    """Show overview of all sandboxes."""
    inspector = SandboxInspector(api_key=api_key)
    s = inspector.summary()

    if format == "json":
        console.print_json(json.dumps(s.model_dump(mode="json"), default=str))
        return

    table = Table(title="E2B Sandbox Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value")

    table.add_row("Running", f"[green]{s.running_count}[/green]")
    table.add_row("Paused", f"[yellow]{s.paused_count}[/yellow]")
    table.add_row("Total", str(s.total_count))
    table.add_row("Total CPU", f"{s.total_cpu} cores")
    table.add_row("Total Memory", f"{s.total_memory_mb} MB")
    if s.oldest_sandbox_id:
        table.add_row("Oldest", f"{s.oldest_sandbox_id} ({_format_timedelta(s.oldest_uptime)})")
    if s.newest_sandbox_id:
        table.add_row("Newest", f"{s.newest_sandbox_id} ({_format_timedelta(s.newest_uptime)})")

    console.print(table)


if __name__ == "__main__":
    app()
