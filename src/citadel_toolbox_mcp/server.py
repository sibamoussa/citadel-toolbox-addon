from __future__ import annotations

import argparse

from mcp.server import MCPServer

from citadel_toolbox_mcp.services import GovernmentService

service = GovernmentService()
read_server = MCPServer("Citadel Government Systems (Read Only)")
action_server = MCPServer("Citadel Government Actions")


@read_server.tool()
def get_application_status(application_id: str) -> dict[str, str]:
    """Get the current status and next step for a government application."""
    return service.get_application_status(application_id)


@action_server.tool()
def create_service_request(service_name: str, summary: str) -> dict[str, str]:
    """Create a government service request after the agent obtains explicit user approval."""
    return service.create_service_request(service_name, summary)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the reference Citadel MCP provider.")
    parser.add_argument(
        "--profile",
        choices=("read", "actions"),
        default="read",
        help="Expose read-only tools (default) or state-changing action tools.",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="streamable-http",
    )
    args = parser.parse_args()
    server = read_server if args.profile == "read" else action_server
    server.run(transport=args.transport)


if __name__ == "__main__":
    main()