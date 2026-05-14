"""Index GitHub repo files into ChromaDB for RAG."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import chromadb

from mcp_server.tools.github_tools import (
    get_github_client,
    list_repo_files,
    list_workflow_runs,
    read_repo_file,
)


def _safe_repo_id(repo: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", repo.replace("/", "__"))


def index_repository(
    github_pat: str,
    repo: str,
    *,
    auto_index: bool = True,
    max_files: int = 250,
    max_chars: int = 12000,
) -> dict[str, Any]:
    """
    Validate repo, gather stats, optionally index into local ChromaDB.

    Returns:
        ok, error (optional), file_count, workflow_count, last_failed_run, indexed
    """
    out_base = {
        "ok": False,
        "error": None,
        "file_count": 0,
        "workflow_count": 0,
        "last_failed_run": None,
        "indexed": False,
    }

    if not github_pat or not repo:
        out_base["error"] = "Missing GitHub PAT or repository."
        return out_base
    if "/" not in repo or repo.count("/") != 1:
        out_base["error"] = "Repository must be in owner/repo format."
        return out_base

    try:
        g = get_github_client(github_pat)
        r = g.get_repo(repo)
        ref = r.default_branch
    except Exception as e:
        out_base["error"] = str(e)
        return out_base

    extensions = [
        ".py",
        ".yml",
        ".yaml",
        ".toml",
        ".txt",
        ".json",
        ".cfg",
        ".ini",
        ".md",
    ]
    try:
        files = list_repo_files(github_pat, repo, ref=ref, extensions=extensions)
    except Exception as e:
        out_base["error"] = str(e)
        return out_base

    file_count = len(files)
    workflow_count = sum(
        1
        for f in files
        if f.startswith(".github/workflows/")
        and (f.endswith(".yml") or f.endswith(".yaml"))
    )

    last_failed_run = None
    try:
        fails = list_workflow_runs(github_pat, repo, status="failure", limit=1)
        if fails:
            fr = fails[0]
            last_failed_run = {
                "id": fr.get("id"),
                "name": fr.get("name"),
                "created_at": fr.get("created_at"),
                "html_url": fr.get("html_url"),
                "head_commit_message": (fr.get("head_commit_message") or "")[:160],
            }
    except Exception:
        pass

    if not auto_index:
        out_base.update(
            {
                "ok": True,
                "file_count": file_count,
                "workflow_count": workflow_count,
                "last_failed_run": last_failed_run,
                "indexed": False,
            }
        )
        return out_base

    if not files:
        out_base.update(
            {
                "ok": True,
                "file_count": file_count,
                "workflow_count": workflow_count,
                "last_failed_run": last_failed_run,
                "indexed": False,
            }
        )
        return out_base

    try:
        root = Path.cwd() / ".pipelinepilot" / "chroma" / _safe_repo_id(repo)
        root.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(root))
        coll_name = "repo_files"
        try:
            client.delete_collection(coll_name)
        except Exception:
            pass
        collection = client.get_or_create_collection(name=coll_name)

        ids: list[str] = []
        docs: list[str] = []
        for fp in files:
            if len(ids) >= max_files:
                break
            try:
                content = read_repo_file(github_pat, repo, file_path=fp, ref=ref)
            except Exception:
                continue
            text = content.strip()
            if not text:
                continue
            if len(text) > max_chars:
                text = text[:max_chars] + "\n\n[... truncated ...]"
            ids.append(fp)
            docs.append(f"FILE: {fp}\n{text}")

        if ids:
            collection.add(ids=ids, documents=docs)

        out_base.update(
            {
                "ok": True,
                "file_count": file_count,
                "workflow_count": workflow_count,
                "last_failed_run": last_failed_run,
                "indexed": bool(ids),
            }
        )
        return out_base

    except Exception as e:
        out_base["error"] = f"Indexing failed: {e}"
        out_base["file_count"] = file_count
        out_base["workflow_count"] = workflow_count
        out_base["last_failed_run"] = last_failed_run
        return out_base
