"""
CLI Interface for Event Storming Agent

Provides an interactive terminal experience for running the
Event Storming LangGraph workflow with human-in-the-loop support.

Usage:
    uv run msaez run          # Start the Event Storming workflow
    uv run msaez status       # Check Neo4j connection and graph stats
    uv run msaez visualize    # Show the workflow graph
"""

from __future__ import annotations

import sys
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.tree import Tree

from .graph import EventStormingRunner, get_graph_visualization
from .neo4j_client import get_neo4j_client
from .state import WorkflowPhase

app = typer.Typer(
    name="msaez",
    help="🎯 Event Storming LangGraph Agent - Generate domain models from user stories",
    add_completion=False,
)

console = Console()


def print_header():
    """Print the application header."""
    console.print()
    console.print(
        Panel.fit(
            "[bold blue]🎯 Event Storming LangGraph Agent[/bold blue]\n"
            "[dim]Generate domain models from user stories with human-in-the-loop[/dim]",
            border_style="blue",
        )
    )
    console.print()


def print_phase(phase: WorkflowPhase):
    """Print the current workflow phase."""
    phase_labels = {
        WorkflowPhase.INIT: "🚀 Initializing",
        WorkflowPhase.LOAD_USER_STORIES: "📋 Loading User Stories",
        WorkflowPhase.SELECT_USER_STORY: "👆 Selecting User Story",
        WorkflowPhase.IDENTIFY_BC: "🔍 Identifying Bounded Contexts",
        WorkflowPhase.APPROVE_BC: "✋ Awaiting BC Approval",
        WorkflowPhase.BREAKDOWN_USER_STORY: "📝 Breaking Down User Stories",
        WorkflowPhase.EXTRACT_AGGREGATES: "📦 Extracting Aggregates",
        WorkflowPhase.APPROVE_AGGREGATES: "✋ Awaiting Aggregate Approval",
        WorkflowPhase.EXTRACT_COMMANDS: "⚡ Extracting Commands",
        WorkflowPhase.EXTRACT_EVENTS: "📨 Extracting Events",
        WorkflowPhase.IDENTIFY_POLICIES: "🔗 Identifying Policies",
        WorkflowPhase.APPROVE_POLICIES: "✋ Awaiting Policy Approval",
        WorkflowPhase.SAVE_TO_GRAPH: "💾 Saving to Neo4j",
        WorkflowPhase.COMPLETE: "✅ Complete",
    }
    label = phase_labels.get(phase, str(phase))
    console.print(f"\n[bold cyan]Phase:[/bold cyan] {label}")


def display_message(content: str):
    """Display a message from the agent."""
    console.print()
    console.print(Panel(Markdown(content), border_style="green", title="🤖 Agent"))


def get_human_input(prompt_text: str = "Your response") -> str:
    """Get input from the user."""
    console.print()
    return Prompt.ask(f"[bold yellow]{prompt_text}[/bold yellow]")


@app.command()
def run(
    thread_id: str = typer.Option("default", "--thread", "-t", help="Thread ID for session persistence"),
):
    """
    🚀 Run the Event Storming workflow.

    This command starts an interactive session that:
    1. Loads user stories from Neo4j
    2. Identifies Bounded Contexts (with your approval)
    3. Breaks down user stories
    4. Extracts Aggregates, Commands, Events (with approvals)
    5. Identifies cross-BC Policies
    6. Saves everything to Neo4j
    """
    print_header()

    # Check Neo4j connection
    console.print("[dim]Checking Neo4j connection...[/dim]")
    client = get_neo4j_client()
    if not client.verify_connection():
        console.print("[bold red]❌ Cannot connect to Neo4j![/bold red]")
        console.print("[dim]Make sure Neo4j is running at bolt://localhost:7687[/dim]")
        raise typer.Exit(1)
    console.print("[green]✓ Connected to Neo4j[/green]")

    # Initialize the runner
    runner = EventStormingRunner(thread_id=thread_id)

    try:
        # Start the workflow
        console.print("\n[bold]Starting Event Storming workflow...[/bold]")
        state = runner.start()

        # Main interaction loop
        while not runner.is_complete():
            state = runner.get_state()
            if state is None:
                break

            # Show current phase
            print_phase(state.phase)

            # Display the last message
            if state.messages:
                last_msg = state.messages[-1]
                display_message(last_msg.content)

            # Check for errors
            if state.error:
                console.print(f"\n[bold red]Error: {state.error}[/bold red]")
                break

            # Check if waiting for human input
            if state.awaiting_human_approval:
                console.print("\n[bold yellow]🔔 Human approval required![/bold yellow]")
                console.print("[dim]Type 'APPROVED' to continue, or provide feedback for changes.[/dim]")
                console.print("[dim]Type 'quit' to exit.[/dim]")

                feedback = get_human_input("Your decision")

                if feedback.lower() in ("quit", "exit", "q"):
                    console.print("\n[yellow]Workflow paused. You can resume later.[/yellow]")
                    break

                # Provide feedback and continue
                state = runner.provide_feedback(feedback)
            else:
                # If not waiting for human, something might be wrong
                break

        # Final state
        state = runner.get_state()
        if state and state.phase == WorkflowPhase.COMPLETE:
            console.print("\n")
            console.print(
                Panel.fit(
                    "[bold green]🎉 Event Storming Complete![/bold green]\n\n"
                    "Your domain model has been saved to Neo4j.\n"
                    "View it at: [link=http://localhost:7474]http://localhost:7474[/link]",
                    border_style="green",
                )
            )

            # Show final message
            if state.messages:
                display_message(state.messages[-1].content)

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        raise typer.Exit(0)
    except Exception as e:
        console.print(f"\n[bold red]Error: {e}[/bold red]")
        raise typer.Exit(1)


@app.command()
def status():
    """
    📊 Check Neo4j connection and display graph statistics.
    """
    print_header()

    client = get_neo4j_client()

    # Check connection
    console.print("[dim]Checking Neo4j connection...[/dim]")
    if not client.verify_connection():
        console.print("[bold red]❌ Cannot connect to Neo4j![/bold red]")
        console.print("\n[dim]Make sure Neo4j is running:")
        console.print("  URI: bolt://localhost:7687")
        console.print("  User: neo4j[/dim]")
        raise typer.Exit(1)

    console.print("[green]✓ Connected to Neo4j[/green]\n")

    # Get statistics
    stats = client.get_graph_statistics()

    if not stats:
        console.print("[yellow]No nodes in the database.[/yellow]")
        console.print("[dim]Run 'python scripts/load_all.py' to load sample data.[/dim]")
        return

    # Display node counts
    table = Table(title="📦 Node Counts", show_header=True)
    table.add_column("Type", style="cyan")
    table.add_column("Count", justify="right", style="green")

    for label, count in sorted(stats.items()):
        table.add_row(label, str(count))

    console.print(table)

    # Get bounded contexts
    bcs = client.get_all_bounded_contexts()
    if bcs:
        console.print("\n")
        tree = Tree("🏢 [bold]Bounded Contexts[/bold]")
        for bc in bcs:
            bc_branch = tree.add(f"[cyan]{bc['name']}[/cyan] ({bc['id']})")
            if bc.get("aggregates"):
                for agg in bc["aggregates"]:
                    if agg.get("name"):
                        bc_branch.add(f"📦 {agg['name']}")
        console.print(tree)

    # Get event chain info
    chains = client.get_full_event_chain()
    if chains:
        console.print("\n")
        console.print("[bold]🔗 Cross-BC Event Chains:[/bold]")
        for chain in chains[:5]:  # Show first 5
            console.print(
                f"  {chain['source_bc']}.{chain['source_command']} "
                f"→ {chain['event']} "
                f"→ {chain['target_bc']}.{chain['policy']}"
            )
        if len(chains) > 5:
            console.print(f"  [dim]... and {len(chains) - 5} more[/dim]")


@app.command()
def visualize():
    """
    🎨 Display the workflow graph as a Mermaid diagram.
    """
    print_header()
    console.print("[bold]LangGraph Workflow Diagram:[/bold]\n")

    mermaid = get_graph_visualization()
    console.print(Panel(mermaid, title="Mermaid Diagram", border_style="blue"))

    console.print("\n[dim]Copy this diagram to https://mermaid.live to visualize[/dim]")


@app.command()
def add_story(
    role: str = typer.Option(..., "--role", "-r", help="User role (e.g., 'customer')"),
    action: str = typer.Option(..., "--action", "-a", help="What the user wants to do"),
    benefit: Optional[str] = typer.Option(None, "--benefit", "-b", help="Expected benefit"),
    story_id: Optional[str] = typer.Option(None, "--id", help="Custom story ID"),
):
    """
    ➕ Add a new user story to Neo4j.

    Example:
        msaez add-story -r customer -a "track my order" -b "I know when it will arrive"
    """
    print_header()

    client = get_neo4j_client()

    if not client.verify_connection():
        console.print("[bold red]❌ Cannot connect to Neo4j![/bold red]")
        raise typer.Exit(1)

    # Generate ID if not provided
    if not story_id:
        existing = client.get_all_user_stories()
        story_id = f"US-{len(existing) + 1:03d}"

    # Create the story
    story = client.create_user_story(
        id=story_id,
        role=role,
        action=action,
        benefit=benefit,
        priority="medium",
        status="draft",
    )

    console.print("[green]✓ User story created![/green]\n")

    # Display the story
    story_text = f"As a [bold]{role}[/bold], I want to [bold]{action}[/bold]"
    if benefit:
        story_text += f", so that [bold]{benefit}[/bold]"

    console.print(Panel(story_text, title=f"📝 {story_id}", border_style="blue"))


@app.command()
def list_stories():
    """
    📋 List all user stories in Neo4j.
    """
    print_header()

    client = get_neo4j_client()

    if not client.verify_connection():
        console.print("[bold red]❌ Cannot connect to Neo4j![/bold red]")
        raise typer.Exit(1)

    stories = client.get_all_user_stories()

    if not stories:
        console.print("[yellow]No user stories found.[/yellow]")
        console.print("[dim]Use 'msaez add-story' to add new stories.[/dim]")
        return

    table = Table(title="📋 User Stories", show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Role", style="green")
    table.add_column("Action")
    table.add_column("Status", style="yellow")
    table.add_column("Implemented In", style="dim")

    for us in stories:
        impl = ""
        if us.get("implemented_in"):
            impl = ", ".join(
                [f"{i['type']}: {i['name']}" for i in us["implemented_in"] if i.get("name")]
            )
        table.add_row(
            us["id"],
            us.get("role", "-"),
            us.get("action", "-")[:50],
            us.get("status", "-"),
            impl[:30] if impl else "-",
        )

    console.print(table)


@app.command()
def impact(
    event_name: str = typer.Argument(..., help="Event name to analyze (e.g., 'OrderCancelled')"),
):
    """
    🔍 Analyze the impact of changing an event.

    Example:
        msaez impact OrderCancelled
    """
    print_header()

    client = get_neo4j_client()

    if not client.verify_connection():
        console.print("[bold red]❌ Cannot connect to Neo4j![/bold red]")
        raise typer.Exit(1)

    analysis = client.get_impact_analysis(event_name)

    if not analysis:
        console.print(f"[yellow]No event found with name: {event_name}[/yellow]")
        return

    console.print(f"\n[bold]Impact Analysis for Event: [cyan]{event_name}[/cyan][/bold]\n")

    # Impact summary
    affected_count = analysis.get("affected_count", 0)
    risk_level = "🟢 LOW" if affected_count <= 1 else "🟡 MEDIUM" if affected_count <= 2 else "🔴 HIGH"

    console.print(f"  Version: {analysis.get('version', '?')}")
    console.print(f"  Affected BCs: {affected_count}")
    console.print(f"  Risk Level: {risk_level}")

    # Show impacts
    impacts = analysis.get("impacts", [])
    if impacts:
        console.print("\n[bold]Affected Components:[/bold]")
        for imp in impacts:
            console.print(
                f"  • [cyan]{imp['bc']}[/cyan] → "
                f"Policy: {imp['policy']} → "
                f"Command: {imp['command']}"
            )

        console.print("\n[bold yellow]⚠️  Changing this event will require updates in these BCs![/bold yellow]")


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()

