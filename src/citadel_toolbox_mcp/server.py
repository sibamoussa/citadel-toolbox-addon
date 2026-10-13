from __future__ import annotations

from mcp.server import MCPServer

from citadel_toolbox_mcp.services import GovernmentService

mcp = MCPServer("Citadel Government Systems")
service = GovernmentService()


@mcp.tool()
def get_application_status(application_id: str) -> dict[str, str]:
    """Get the current status and next step for a government application."""
    return service.get_application_status(application_id)


@mcp.tool()
def create_service_request(service_name: str, summary: str) -> dict[str, str]:
    """Create a government service request after the agent obtains explicit user approval."""
    return service.create_service_request(service_name, summary)


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()