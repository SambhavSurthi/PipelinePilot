from fastmcp import FastMCP

from .tools.github_tools import (
    list_repos,
    list_workflow_runs,
    get_workflow_run_logs,
    get_failed_step_details,
    read_repo_file,
    list_repo_files,
)
from .tools.git_tools import (
    create_branch,
    apply_patch_and_commit,
    push_branch,
    create_pull_request,
)
from .tools.filesystem_tools import (
    read_file,
    write_file,
    list_directory,
)

# Create a FastMCP server
mcp = FastMCP("pipelinepilot")

# Register GitHub tools
mcp.tool()(list_repos)
mcp.tool()(list_workflow_runs)
mcp.tool()(get_workflow_run_logs)
mcp.tool()(get_failed_step_details)
mcp.tool()(read_repo_file)
mcp.tool()(list_repo_files)

# Register Git tools
mcp.tool()(create_branch)
mcp.tool()(apply_patch_and_commit)
mcp.tool()(push_branch)
mcp.tool()(create_pull_request)

# Register Filesystem tools
mcp.tool()(read_file)
mcp.tool()(write_file)
mcp.tool()(list_directory)

def main():
    """Main entry point to run the FastMCP server."""
    mcp.run()

if __name__ == "__main__":
    main()
