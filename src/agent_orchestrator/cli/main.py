"""Main CLI application."""

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from agent_orchestrator import __version__
from agent_orchestrator.config import get_settings

app = typer.Typer(
    name="agent-orchestrator",
    help="Distributed AI Agent Orchestrator CLI",
    add_completion=False,
)
console = Console()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-v", help="Show version and exit"
    ),
) -> None:
    """Distributed AI Agent Orchestrator CLI."""
    if version:
        console.print(f"agent-orchestrator version {__version__}")
        raise typer.Exit()


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind to"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload"),
    workers: int = typer.Option(1, "--workers", "-w", help="Number of workers"),
) -> None:
    """Start the API server."""
    import uvicorn

    console.print(f"[green]Starting API server on {host}:{port}[/green]")

    uvicorn.run(
        "agent_orchestrator.api.app:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,
    )


@app.command()
def worker(
    worker_id: Optional[str] = typer.Option(
        None, "--id", help="Worker ID (auto-generated if not provided)"
    ),
    concurrency: int = typer.Option(
        5, "--concurrency", "-c", help="Number of concurrent tasks"
    ),
) -> None:
    """Start an agent worker."""
    from uuid import uuid4

    worker_id = worker_id or str(uuid4())[:8]
    console.print(f"[green]Starting agent worker: {worker_id}[/green]")

    async def run_worker() -> None:
        from agent_orchestrator.workers.agent_worker import AgentWorker

        settings = get_settings()
        w = AgentWorker(
            worker_id=worker_id,
            settings=settings,
            concurrency=concurrency,
        )
        await w.start()

    asyncio.run(run_worker())


@app.command()
def config() -> None:
    """Show current configuration."""
    settings = get_settings()

    table = Table(title="Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Environment", settings.environment)
    table.add_row("API Host", settings.api.host)
    table.add_row("API Port", str(settings.api.port))
    table.add_row("NATS Servers", ", ".join(settings.nats.servers))
    table.add_row("Database Host", settings.database.host)
    table.add_row("Redis Host", settings.redis.host)
    table.add_row("Default LLM Provider", settings.llm.default_provider)
    table.add_row("Default Model", settings.llm.default_model)
    table.add_row("Telemetry Enabled", str(settings.telemetry.enabled))

    console.print(table)


@app.command()
def migrate(
    revision: str = typer.Option("head", "--revision", "-r", help="Target revision"),
) -> None:
    """Run database migrations."""
    import subprocess
    import sys

    console.print(f"[green]Running migrations to: {revision}[/green]")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        console.print("[green]Migrations completed successfully[/green]")
        if result.stdout:
            console.print(result.stdout)
    else:
        console.print("[red]Migration failed[/red]")
        if result.stderr:
            console.print(result.stderr)
        raise typer.Exit(1)


@app.command()
def check() -> None:
    """Check system health and connectivity."""
    import asyncio

    async def run_checks() -> bool:
        settings = get_settings()
        all_ok = True

        # Check NATS
        console.print("Checking NATS connection...", end=" ")
        try:
            from agent_orchestrator.infrastructure.messaging.nats_client import NATSClient

            nats = NATSClient(settings.nats)
            await nats.connect()
            await nats.close()
            console.print("[green]OK[/green]")
        except Exception as e:
            console.print(f"[red]FAILED: {e}[/red]")
            all_ok = False

        # Check Redis
        console.print("Checking Redis connection...", end=" ")
        try:
            from agent_orchestrator.infrastructure.cache.redis_client import RedisClient

            redis = RedisClient(settings.redis)
            await redis.connect()
            await redis.close()
            console.print("[green]OK[/green]")
        except Exception as e:
            console.print(f"[red]FAILED: {e}[/red]")
            all_ok = False

        # Check PostgreSQL
        console.print("Checking PostgreSQL connection...", end=" ")
        try:
            from agent_orchestrator.infrastructure.persistence.database import (
                close_database,
                init_database,
            )

            await init_database(settings.database)
            await close_database()
            console.print("[green]OK[/green]")
        except Exception as e:
            console.print(f"[red]FAILED: {e}[/red]")
            all_ok = False

        return all_ok

    ok = asyncio.run(run_checks())
    if ok:
        console.print("\n[green]All checks passed![/green]")
    else:
        console.print("\n[red]Some checks failed![/red]")
        raise typer.Exit(1)


@app.command(name="console")
def interactive_console() -> None:
    """Start an interactive console for managing the orchestrator."""
    from datetime import datetime, timezone

    from rich.live import Live
    from rich.panel import Panel
    from rich.prompt import Prompt

    settings = get_settings()

    def show_banner() -> None:
        banner = """
╔═══════════════════════════════════════════════════════════════╗
║        🤖 Agent Orchestrator Interactive Console 🤖           ║
╚═══════════════════════════════════════════════════════════════╝
        """
        console.print(banner, style="bold cyan")

    def show_menu() -> None:
        menu = Table(show_header=False, box=None, padding=(0, 2))
        menu.add_column("Option", style="bold yellow")
        menu.add_column("Description", style="white")

        menu.add_row("[1]", "Create a new task")
        menu.add_row("[2]", "Create a new agent")
        menu.add_row("[3]", "List agents")
        menu.add_row("[4]", "List tasks")
        menu.add_row("[5]", "System status")
        menu.add_row("[6]", "Monitor workers (live)")
        menu.add_row("[7]", "View streams info")
        menu.add_row("[8]", "Configuration")
        menu.add_row("[q]", "Quit")

        console.print(Panel(menu, title="Menu", border_style="blue"))

    async def create_task() -> None:
        console.print("\n[bold cyan]Create New Task[/bold cyan]")
        name = Prompt.ask("[yellow]Task name[/yellow]")
        description = Prompt.ask("[yellow]Description[/yellow]")

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"http://{settings.api.host}:{settings.api.port}/tasks",
                    json={
                        "name": name,
                        "description": description,
                    },
                    timeout=10.0,
                )
                if response.status_code == 201:
                    data = response.json()
                    console.print("\n[green]✓ Task created![/green]")
                    console.print(f"  ID: {data['task_id']}")
                    console.print(f"  Status: {data['status']}")
                else:
                    console.print(f"[red]✗ Failed: {response.text}[/red]")
        except Exception as e:
            console.print(f"[red]✗ Error: {e}[/red]")
            console.print(
                "[dim]Make sure the API server is running (agent-orchestrator serve)[/dim]"
            )

    async def create_agent() -> None:
        console.print("\n[bold cyan]Create New Agent[/bold cyan]")
        name = Prompt.ask("[yellow]Agent name[/yellow]")
        role = Prompt.ask("[yellow]Role[/yellow]", default="General assistant")
        goal = Prompt.ask(
            "[yellow]Goal[/yellow]", default="Help complete tasks efficiently"
        )

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"http://{settings.api.host}:{settings.api.port}/agents",
                    json={
                        "name": name,
                        "role": role,
                        "goal": goal,
                    },
                    timeout=10.0,
                )
                if response.status_code == 201:
                    data = response.json()
                    console.print("\n[green]✓ Agent created![/green]")
                    console.print(f"  ID: {data['agent_id']}")
                    console.print(f"  Name: {data['name']}")
                else:
                    console.print(f"[red]✗ Failed: {response.text}[/red]")
        except Exception as e:
            console.print(f"[red]✗ Error: {e}[/red]")
            console.print(
                "[dim]Make sure the API server is running (agent-orchestrator serve)[/dim]"
            )

    async def list_agents() -> None:
        console.print("\n[bold cyan]Agents[/bold cyan]")
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"http://{settings.api.host}:{settings.api.port}/agents",
                    timeout=10.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    if data["items"]:
                        table = Table(title="Registered Agents")
                        table.add_column("ID", style="dim")
                        table.add_column("Name", style="cyan")
                        table.add_column("Role", style="green")
                        table.add_column("Status", style="yellow")

                        for agent in data["items"]:
                            table.add_row(
                                agent["agent_id"][:8] + "...",
                                agent["name"],
                                agent.get("role", "-"),
                                agent.get("status", "unknown"),
                            )
                        console.print(table)
                    else:
                        console.print("[dim]No agents registered yet[/dim]")
                else:
                    console.print(f"[red]✗ Failed: {response.text}[/red]")
        except Exception as e:
            console.print(f"[red]✗ Error: {e}[/red]")
            console.print("[dim]Make sure the API server is running[/dim]")

    async def list_tasks() -> None:
        console.print("\n[bold cyan]Tasks[/bold cyan]")
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"http://{settings.api.host}:{settings.api.port}/tasks",
                    timeout=10.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    if data["items"]:
                        table = Table(title="Tasks")
                        table.add_column("ID", style="dim")
                        table.add_column("Name", style="cyan")
                        table.add_column("Status", style="yellow")
                        table.add_column("Created", style="dim")

                        for task in data["items"]:
                            table.add_row(
                                task["task_id"][:8] + "...",
                                task["name"],
                                task["status"],
                                task.get("created_at", "-")[:19],
                            )
                        console.print(table)
                    else:
                        console.print("[dim]No tasks created yet[/dim]")
                else:
                    console.print(f"[red]✗ Failed: {response.text}[/red]")
        except Exception as e:
            console.print(f"[red]✗ Error: {e}[/red]")
            console.print("[dim]Make sure the API server is running[/dim]")

    async def system_status() -> None:
        console.print("\n[bold cyan]System Status[/bold cyan]")

        status_table = Table(show_header=False, box=None)
        status_table.add_column("Service", style="cyan", width=20)
        status_table.add_column("Status", style="white")

        # Check API
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"http://{settings.api.host}:{settings.api.port}/health",
                    timeout=5.0,
                )
                if response.status_code == 200:
                    status_table.add_row("API Server", "[green]● Running[/green]")
                else:
                    status_table.add_row("API Server", "[red]● Error[/red]")
        except Exception:
            status_table.add_row("API Server", "[red]● Offline[/red]")

        # Check NATS
        try:
            from agent_orchestrator.infrastructure.messaging.nats_client import (
                NATSClient,
            )

            nats = NATSClient(settings.nats)
            await nats.connect()
            await nats.close()
            status_table.add_row("NATS", "[green]● Connected[/green]")
        except Exception:
            status_table.add_row("NATS", "[red]● Offline[/red]")

        # Check Redis
        try:
            from agent_orchestrator.infrastructure.cache.redis_client import RedisClient

            redis = RedisClient(settings.redis)
            await redis.connect()
            await redis.close()
            status_table.add_row("Redis", "[green]● Connected[/green]")
        except Exception:
            status_table.add_row("Redis", "[red]● Offline[/red]")

        # Check PostgreSQL
        try:
            from agent_orchestrator.infrastructure.persistence.database import (
                close_database,
                init_database,
            )

            await init_database(settings.database)
            await close_database()
            status_table.add_row("PostgreSQL", "[green]● Connected[/green]")
        except Exception:
            status_table.add_row("PostgreSQL", "[red]● Offline[/red]")

        console.print(Panel(status_table, title="Services", border_style="green"))

    async def monitor_workers() -> None:
        console.print(
            "\n[bold cyan]Worker Monitor[/bold cyan] [dim](Press Ctrl+C to stop)[/dim]\n"
        )

        from agent_orchestrator.infrastructure.messaging.nats_client import NATSClient

        try:
            nats = NATSClient(settings.nats)
            await nats.connect()

            workers: dict[str, dict] = {}

            def generate_table() -> Table:
                table = Table(
                    title=f"Active Workers - {datetime.now(timezone.utc).strftime('%H:%M:%S')}"
                )
                table.add_column("Worker ID", style="cyan")
                table.add_column("Active Tasks", style="yellow")
                table.add_column("Capacity", style="green")
                table.add_column("Last Seen", style="dim")

                now = datetime.now(timezone.utc)
                for wid, info in workers.items():
                    age = (now - info["last_seen"]).total_seconds()
                    status = "🟢" if age < 5 else "🟡" if age < 15 else "🔴"
                    table.add_row(
                        f"{status} {wid}",
                        str(info.get("active_tasks", 0)),
                        str(info.get("capacity", 0)),
                        f"{age:.0f}s ago",
                    )

                if not workers:
                    table.add_row("[dim]No workers detected[/dim]", "", "", "")

                return table

            async def heartbeat_handler(data: dict) -> None:
                worker_id = data.get("worker_id", "unknown")
                workers[worker_id] = {
                    **data,
                    "last_seen": datetime.now(timezone.utc),
                }

            await nats.subscribe(
                "WORKERS.heartbeat",
                queue="console-monitor",
                handler=heartbeat_handler,
                durable="console-monitor",
            )

            with Live(generate_table(), refresh_per_second=1, console=console) as live:
                try:
                    while True:
                        await asyncio.sleep(1)
                        # Remove stale workers (>30s)
                        now = datetime.now(timezone.utc)
                        stale_workers = [
                            k
                            for k, v in workers.items()
                            if (now - v["last_seen"]).total_seconds() >= 30
                        ]
                        for k in stale_workers:
                            del workers[k]
                        live.update(generate_table())
                except KeyboardInterrupt:
                    pass

            await nats.close()
        except Exception as e:
            console.print(f"[red]✗ Error: {e}[/red]")

    async def view_streams() -> None:
        console.print("\n[bold cyan]NATS JetStream Info[/bold cyan]")

        try:
            from agent_orchestrator.infrastructure.messaging.nats_client import (
                NATSClient,
            )

            nats = NATSClient(settings.nats)
            await nats.connect()

            table = Table(title="Streams")
            table.add_column("Stream", style="cyan")
            table.add_column("Subjects", style="yellow")
            table.add_column("Messages", style="green")
            table.add_column("Bytes", style="dim")

            for stream_name in ["TASKS", "AGENTS", "WORKFLOWS", "RESULTS", "WORKERS"]:
                try:
                    info = await nats.js.stream_info(stream_name)
                    subjects = ", ".join(info.config.subjects or [])
                    table.add_row(
                        stream_name,
                        subjects[:40] + "..." if len(subjects) > 40 else subjects,
                        str(info.state.messages),
                        f"{info.state.bytes / 1024:.1f} KB",
                    )
                except Exception:
                    table.add_row(stream_name, "[red]Not found[/red]", "-", "-")

            console.print(table)
            await nats.close()
        except Exception as e:
            console.print(f"[red]✗ Error: {e}[/red]")

    def show_config() -> None:
        table = Table(title="Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Environment", settings.environment)
        table.add_row(
            "API Endpoint", f"http://{settings.api.host}:{settings.api.port}"
        )
        table.add_row("NATS Servers", ", ".join(settings.nats.servers))
        table.add_row("Redis", f"{settings.redis.host}:{settings.redis.port}")
        table.add_row(
            "PostgreSQL",
            f"{settings.database.host}:{settings.database.port}/{settings.database.name}",
        )
        table.add_row(
            "Default LLM",
            f"{settings.llm.default_provider}/{settings.llm.default_model}",
        )
        table.add_row(
            "Telemetry", "Enabled" if settings.telemetry.enabled else "Disabled"
        )

        console.print(table)

    async def main_loop() -> None:
        show_banner()

        while True:
            console.print()
            show_menu()
            choice = Prompt.ask("\n[bold]Select option[/bold]", default="q")

            if choice == "1":
                await create_task()
            elif choice == "2":
                await create_agent()
            elif choice == "3":
                await list_agents()
            elif choice == "4":
                await list_tasks()
            elif choice == "5":
                await system_status()
            elif choice == "6":
                await monitor_workers()
            elif choice == "7":
                await view_streams()
            elif choice == "8":
                show_config()
            elif choice.lower() == "q":
                console.print("\n[cyan]Goodbye! 👋[/cyan]\n")
                break
            else:
                console.print("[red]Invalid option[/red]")

            input("\nPress Enter to continue...")

    asyncio.run(main_loop())


if __name__ == "__main__":
    app()
