import io
import zipfile
import requests
from github import Github


def _split_owner_repo(repo: str) -> tuple[str, str]:
    parts = (repo or "").strip().split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"Invalid repository slug (expected owner/repo): {repo!r}")
    return parts[0], parts[1]


def _github_http_headers(github_pat: str, *, style: str) -> dict[str, str]:
    """REST headers for Actions log downloads (fine-grained PATs expect Bearer)."""
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "PipelinePilot/1.0",
    }
    if style == "bearer":
        h["Authorization"] = f"Bearer {github_pat}"
    elif style == "token":
        h["Authorization"] = f"token {github_pat}"
    else:
        raise ValueError("style must be 'bearer' or 'token'")
    return h


def _http_get_logs_zip(url: str, github_pat: str) -> tuple[int, bytes]:
    """GET a logs archive URL; try Bearer then classic token. Returns (status, body)."""
    last_status, last_body = 0, b""
    for style in ("bearer", "token"):
        try:
            r = requests.get(
                url,
                headers=_github_http_headers(github_pat, style=style),
                allow_redirects=True,
                timeout=120,
            )
            last_status, last_body = r.status_code, r.content
            if r.status_code == 200 and r.content[:2] == b"PK":
                return r.status_code, r.content
            if r.status_code in (401, 403, 404):
                continue
            return r.status_code, r.content
        except requests.RequestException:
            continue
    return last_status, last_body


def _zip_bytes_to_log_text(content: bytes) -> str:
    if not content or content[:2] != b"PK":
        return ""
    all_logs: list[str] = []
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        for filename in z.namelist():
            if filename.endswith(".txt"):
                with z.open(filename) as f:
                    all_logs.append(f"--- {filename} ---")
                    all_logs.append(f.read().decode("utf-8", errors="replace"))
    full_log_text = "\n".join(all_logs)
    lines = full_log_text.splitlines()
    if len(lines) > 300:
        return "\n".join(
            lines[:50] + ["... [TRUNCATED] ..."] + lines[-250:]
        )
    return full_log_text


def _download_workflow_run_logs_zip(github_pat: str, owner: str, repo: str, run_id: int) -> bytes | None:
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/logs"
    status, body = _http_get_logs_zip(url, github_pat)
    if status == 200 and body[:2] == b"PK":
        return body
    return None


def _download_job_logs_zip(github_pat: str, owner: str, repo: str, job_id: int) -> bytes | None:
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/jobs/{job_id}/logs"
    status, body = _http_get_logs_zip(url, github_pat)
    if status == 200 and body[:2] == b"PK":
        return body
    return None


def _synthetic_logs_from_run(github_pat: str, repo: str, run_id: int, *, reason: str) -> str:
    """Last resort: job/step metadata so RCA can still run without log archives."""
    g = get_github_client(github_pat)
    r = g.get_repo(repo)
    run = r.get_workflow_run(run_id)
    lines = [
        "[PipelinePilot] GitHub Actions log archive could not be downloaded.",
        f"Reason: {reason}",
        "Ensure your token can read Actions logs: fine-grained PAT → Repository → Actions: Read; "
        "or classic PAT with the `repo` scope (and workflow access for private repos).",
        "",
        f"Run #{run_id} workflow={run.name!r} branch={run.head_branch!r} "
        f"status={run.status!r} conclusion={run.conclusion!r}",
        f"URL: {run.html_url}",
        "",
        "--- Jobs / steps (metadata only) ---",
    ]
    try:
        for job in run.jobs():
            lines.append(f"Job: {job.name!r} id={job.id} conclusion={job.conclusion!r}")
            for step in job.steps:
                lines.append(
                    f"  Step {step.number}: {step.name!r} conclusion={step.conclusion!r}"
                )
    except Exception as e:
        lines.append(f"(Could not list jobs: {e})")
    return "\n".join(lines)


def get_github_client(github_pat: str) -> Github:
    if not github_pat:
        raise ValueError("GitHub PAT is required.")
    return Github(github_pat)

def list_repos(github_pat: str) -> list[dict]:
    """
    List all repositories the GitHub PAT has access to.
    
    Args:
        github_pat: GitHub Personal Access Token.
        
    Returns:
        List of dictionaries containing repo details: name, full_name, default_branch, private, description.
    """
    try:
        g = get_github_client(github_pat)
        repos = g.get_user().get_repos()
        return [
            {
                "name": repo.name,
                "full_name": repo.full_name,
                "default_branch": repo.default_branch,
                "private": repo.private,
                "description": repo.description,
            }
            for repo in repos
        ]
    except Exception as e:
        raise ValueError(f"Failed to list repos: {e}")

def list_workflow_runs(github_pat: str, repo: str, status: str = "failure", limit: int = 5) -> list[dict]:
    """
    List recent workflow runs filtered by status.
    
    Args:
        github_pat: GitHub Personal Access Token.
        repo: Repository format "owner/repo".
        status: The status to filter by (e.g., "failure", "success").
        limit: Max number of workflow runs to return.
        
    Returns:
        List of workflow runs containing id, name, status, conclusion, created_at, html_url, head_commit_message.
    """
    try:
        g = get_github_client(github_pat)
        r = g.get_repo(repo)
        runs = r.get_workflow_runs(status=status)
        
        result = []
        for i, run in enumerate(runs):
            if i >= limit:
                break
            commit_message = ""
            if run.head_commit:
                commit_message = run.head_commit.message
            
            result.append({
                "id": run.id,
                "name": run.name,
                "status": run.status,
                "conclusion": run.conclusion,
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "html_url": run.html_url,
                "head_commit_message": commit_message,
            })
        return result
    except Exception as e:
        raise ValueError(f"Failed to list workflow runs: {e}")

def get_workflow_run_logs(github_pat: str, repo: str, run_id: int) -> str:
    """
    Fetch log text for a workflow run: full-run archive, then per-job archives,
    then a metadata-only fallback so the agent can still proceed.
    """
    try:
        owner, repo_name = _split_owner_repo(repo)
        run_url = f"https://api.github.com/repos/{owner}/{repo_name}/actions/runs/{run_id}/logs"
        last_status, _ = _http_get_logs_zip(run_url, github_pat)

        zip_blob = _download_workflow_run_logs_zip(github_pat, owner, repo_name, run_id)
        if zip_blob:
            text = _zip_bytes_to_log_text(zip_blob)
            if text.strip():
                return text

        g = get_github_client(github_pat)
        r_obj = g.get_repo(repo)
        run = r_obj.get_workflow_run(run_id)

        job_chunks: list[str] = []
        for job in run.jobs():
            jz = _download_job_logs_zip(github_pat, owner, repo_name, job.id)
            if not jz:
                continue
            part = _zip_bytes_to_log_text(jz)
            if part.strip():
                job_chunks.append(f"=== JOB {job.name} (id={job.id}) ===\n{part}")

        if job_chunks:
            merged = "\n\n".join(job_chunks)
            lines = merged.splitlines()
            if len(lines) > 300:
                return "\n".join(
                    lines[:50] + ["... [TRUNCATED] ..."] + lines[-250:]
                )
            return merged

        reason = (
            f"run-level log download failed (HTTP {last_status}). "
            "GitHub often returns 404 when the token cannot read Actions artifacts."
        )
        return _synthetic_logs_from_run(github_pat, repo, run_id, reason=reason)
    except Exception as e:
        raise ValueError(f"Failed to get workflow run logs: {e}") from e

def get_failed_step_details(github_pat: str, repo: str, run_id: int) -> dict:
    """
    Return the specific failed job and step name, error message (log excerpt).
    
    Args:
        github_pat: GitHub Personal Access Token.
        repo: Repository format "owner/repo".
        run_id: The ID of the workflow run.
        
    Returns:
        Dictionary containing job_name, step_name, conclusion, log_excerpt.
    """
    try:
        owner, repo_name = _split_owner_repo(repo)
        g = get_github_client(github_pat)
        r_obj = g.get_repo(repo)
        run = r_obj.get_workflow_run(run_id)

        logs_zip = None
        run_zip = _download_workflow_run_logs_zip(github_pat, owner, repo_name, run_id)
        if run_zip:
            try:
                logs_zip = zipfile.ZipFile(io.BytesIO(run_zip))
            except zipfile.BadZipFile:
                logs_zip = None

        for job in run.jobs():
            if job.conclusion != "failure":
                continue
            if logs_zip is None:
                jz = _download_job_logs_zip(github_pat, owner, repo_name, job.id)
                if jz:
                    try:
                        logs_zip = zipfile.ZipFile(io.BytesIO(jz))
                    except zipfile.BadZipFile:
                        logs_zip = None

            for step in job.steps:
                if step.conclusion != "failure":
                    continue
                log_excerpt = (
                    "Log archive not available with this token (enable Actions read / correct scopes). "
                    "Use the workflow run page for full logs."
                )
                if logs_zip:
                    safe_job_name = job.name.replace("/", "")
                    step_number = step.number
                    for filename in logs_zip.namelist():
                        if f"{job.name}/" in filename or safe_job_name in filename:
                            if filename.endswith(".txt") and f"{step_number}_" in filename.split("/")[-1]:
                                with logs_zip.open(filename) as f:
                                    step_log = f.read().decode("utf-8", errors="replace").splitlines()
                                    log_excerpt = "\n".join(step_log[-50:])
                                break

                return {
                    "job_name": job.name,
                    "step_name": step.name,
                    "conclusion": step.conclusion,
                    "log_excerpt": log_excerpt,
                }

        return {"error": "No failed step found"}
    except Exception as e:
        raise ValueError(f"Failed to get failed step details: {e}") from e

def read_repo_file(github_pat: str, repo: str, file_path: str, ref: str = "main") -> str:
    """
    Read a specific file from the GitHub repo at a given ref.
    
    Args:
        github_pat: GitHub Personal Access Token.
        repo: Repository format "owner/repo".
        file_path: Path to the file in the repository.
        ref: The branch or tag to read from.
        
    Returns:
        The content of the file as a string.
    """
    try:
        g = get_github_client(github_pat)
        r = g.get_repo(repo)
        content_file = r.get_contents(file_path, ref=ref)
        if isinstance(content_file, list):
            raise ValueError(f"{file_path} is a directory, not a file.")
        return content_file.decoded_content.decode("utf-8")
    except Exception as e:
        raise ValueError(f"Failed to read repo file: {e}")

def list_repo_files(github_pat: str, repo: str, ref: str = "main", extensions: list[str] = None) -> list[str]:
    """
    List all file paths in the repo (recursive).
    
    Args:
        github_pat: GitHub Personal Access Token.
        repo: Repository format "owner/repo".
        ref: The branch or tag to list files from.
        extensions: Optional list of extensions to filter by (e.g. [".py", ".yml"]).
        
    Returns:
        List of file paths.
    """
    try:
        g = get_github_client(github_pat)
        r = g.get_repo(repo)
        tree = r.get_git_tree(ref, recursive=True)
        
        files = []
        for element in tree.tree:
            if element.type == "blob":
                if extensions:
                    if any(element.path.endswith(ext) for ext in extensions):
                        files.append(element.path)
                else:
                    files.append(element.path)
        return files
    except Exception as e:
        raise ValueError(f"Failed to list repo files: {e}")
