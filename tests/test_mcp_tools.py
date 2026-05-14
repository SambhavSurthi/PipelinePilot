import os
import pytest
from unittest.mock import patch, MagicMock
from mcp_server.tools.github_tools import (
    list_repos,
    get_workflow_run_logs,
    read_repo_file,
)
from mcp_server.tools.git_tools import create_branch
from mcp_server.tools.filesystem_tools import write_file, read_file
from git import Repo

# --- GitHub Tools Tests ---

@patch("mcp_server.tools.github_tools.get_github_client")
def test_list_repos(mock_get_client):
    mock_g = MagicMock()
    mock_user = MagicMock()
    mock_repo1 = MagicMock()
    mock_repo1.name = "repo1"
    mock_repo1.full_name = "owner/repo1"
    mock_repo1.default_branch = "main"
    mock_repo1.private = False
    mock_repo1.description = "Test Repo 1"
    
    mock_user.get_repos.return_value = [mock_repo1]
    mock_g.get_user.return_value = mock_user
    mock_get_client.return_value = mock_g
    
    repos = list_repos("dummy_pat")
    
    assert len(repos) == 1
    assert repos[0]["name"] == "repo1"
    assert repos[0]["full_name"] == "owner/repo1"
    assert repos[0]["private"] is False

@patch("mcp_server.tools.github_tools.requests.get")
@patch("mcp_server.tools.github_tools.get_github_client")
def test_get_workflow_run_logs_truncation(mock_get_client, mock_requests_get):
    import zipfile
    import io
    
    mock_g = MagicMock()
    mock_repo = MagicMock()
    mock_run = MagicMock()
    mock_run.logs_url = "http://fake-logs-url"
    mock_repo.get_workflow_run.return_value = mock_run
    mock_g.get_repo.return_value = mock_repo
    mock_get_client.return_value = mock_g
    
    # Create a dummy zip file with a large text file
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as z:
        # Create a file with 400 lines
        content = "\n".join([f"Line {i}" for i in range(1, 401)])
        z.writestr("1_step.txt", content)
    
    mock_response = MagicMock()
    mock_response.content = zip_buffer.getvalue()
    mock_response.raise_for_status.return_value = None
    mock_requests_get.return_value = mock_response
    
    logs = get_workflow_run_logs("dummy_pat", "owner/repo", 1)
    
    lines = logs.splitlines()
    # 50 lines (including header) + 1 line for TRUNCATED + 250 lines = 301 lines
    assert len(lines) == 301
    assert "--- 1_step.txt ---" in lines[0]
    assert "Line 1" in lines[1]
    assert "... [TRUNCATED] ..." in lines
    assert "Line 400" in lines[-1]

@patch("mcp_server.tools.github_tools.get_github_client")
def test_read_repo_file(mock_get_client):
    mock_g = MagicMock()
    mock_repo = MagicMock()
    mock_file = MagicMock()
    
    mock_file.decoded_content = b"file content"
    mock_repo.get_contents.return_value = mock_file
    mock_g.get_repo.return_value = mock_repo
    mock_get_client.return_value = mock_g
    
    content = read_repo_file("dummy_pat", "owner/repo", "README.md")
    
    assert content == "file content"
    mock_repo.get_contents.assert_called_once_with("README.md", ref="main")

# --- Git Tools Tests ---

def test_create_branch(tmp_path):
    repo_path = str(tmp_path / "test_repo")
    repo = Repo.init(repo_path)
    
    # Create an initial commit so we have a base branch (master/main)
    file_path = os.path.join(repo_path, "test.txt")
    with open(file_path, "w") as f:
        f.write("Initial commit")
    repo.index.add(["test.txt"])
    repo.index.commit("Initial commit")
    
    active_branch = repo.active_branch.name
    
    # Use our tool
    result = create_branch(repo_path, "new-feature", base_branch=active_branch)
    
    assert result["success"] is True
    assert result["branch_name"] == "new-feature"
    assert repo.active_branch.name == "new-feature"

# --- Filesystem Tools Tests ---

def test_write_read_file_roundtrip(tmp_path):
    file_path = str(tmp_path / "test_rw.txt")
    content = "Hello, filesystem tools!\nTesting 123."
    
    # Write file
    write_result = write_file(file_path, content)
    assert write_result["success"] is True
    assert write_result["path"] == file_path
    
    # Read file
    read_content = read_file(file_path)
    assert read_content == content
