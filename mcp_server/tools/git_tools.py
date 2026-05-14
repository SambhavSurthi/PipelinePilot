import os
from git import Repo
from github import Github

def create_branch(repo_path: str, branch_name: str, base_branch: str = "main") -> dict:
    """
    Create a new branch from a base branch using GitPython.
    
    Args:
        repo_path: Local path to the repository.
        branch_name: Name of the new branch to create.
        base_branch: Branch to branch off from (default "main").
        
    Returns:
        Dictionary indicating success, branch name, and message.
    """
    try:
        repo = Repo(repo_path)
        
        # Ensure we are on the base branch and it's up to date
        repo.git.checkout(base_branch)
        try:
            repo.remotes.origin.pull(base_branch)
        except Exception:
            pass # Might not have remote or network access
            
        new_branch = repo.create_head(branch_name, base_branch)
        new_branch.checkout()
        
        return {
            "success": True,
            "branch_name": branch_name,
            "message": f"Successfully created and checked out branch {branch_name}"
        }
    except Exception as e:
        return {"success": False, "branch_name": branch_name, "message": str(e)}

def apply_patch_and_commit(repo_path: str, file_path: str, new_content: str, commit_message: str, branch_name: str) -> dict:
    """
    Writes new_content to file_path in the local repo, stages, and commits on branch_name.
    
    Args:
        repo_path: Local path to the repository.
        file_path: Relative path to the file to modify.
        new_content: The new content of the file.
        commit_message: The commit message.
        branch_name: The branch to commit to.
        
    Returns:
        Dictionary indicating success, commit SHA, and message.
    """
    try:
        repo = Repo(repo_path)
        
        # Checkout branch if not already on it
        if repo.active_branch.name != branch_name:
            repo.git.checkout(branch_name)
            
        full_file_path = os.path.join(repo_path, file_path)
        with open(full_file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        repo.index.add([file_path])
        commit = repo.index.commit(commit_message)
        
        return {
            "success": True,
            "commit_sha": commit.hexsha,
            "message": f"Successfully committed changes to {file_path}"
        }
    except Exception as e:
        return {"success": False, "commit_sha": None, "message": str(e)}

def push_branch(repo_path: str, branch_name: str, github_pat: str, remote: str = "origin") -> dict:
    """
    Pushes branch to remote using PAT for auth.
    
    Args:
        repo_path: Local path to the repository.
        branch_name: Name of the branch to push.
        github_pat: GitHub Personal Access Token for authentication.
        remote: Remote name (default "origin").
        
    Returns:
        Dictionary indicating success and message.
    """
    try:
        repo = Repo(repo_path)
        remote_obj = repo.remotes[remote]
        
        # Update the remote URL to include the PAT
        remote_url = remote_obj.url
        if remote_url.startswith("https://"):
            # Strip any existing credentials and insert PAT
            base_url = remote_url.split("@")[-1] if "@" in remote_url else remote_url.replace("https://", "")
            auth_url = f"https://oauth2:{github_pat}@{base_url}"
            with repo.git.custom_environment(GIT_ASKPASS='echo'):
                repo.git.push(auth_url, branch_name, set_upstream=True)
        else:
            # Assuming SSH or other configured auth
            repo.git.push(remote, branch_name, set_upstream=True)
            
        return {
            "success": True,
            "message": f"Successfully pushed {branch_name} to {remote}"
        }
    except Exception as e:
        return {"success": False, "message": str(e)}

def create_pull_request(github_pat: str, repo: str, title: str, body: str, head_branch: str, base_branch: str = "main") -> dict:
    """
    Creates a pull request via PyGithub.
    
    Args:
        github_pat: GitHub Personal Access Token.
        repo: Repository format "owner/repo".
        title: PR title.
        body: PR body description.
        head_branch: Branch containing the changes.
        base_branch: Target branch for the PR (default "main").
        
    Returns:
        Dictionary indicating success, PR URL, and PR number.
    """
    try:
        g = Github(github_pat)
        r = g.get_repo(repo)
        
        pr = r.create_pull(title=title, body=body, head=head_branch, base=base_branch)
        
        return {
            "success": True,
            "pr_url": pr.html_url,
            "pr_number": pr.number,
            "message": "Successfully created PR"
        }
    except Exception as e:
        return {"success": False, "pr_url": None, "pr_number": None, "message": str(e)}
