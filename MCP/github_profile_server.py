# MCP/github_profile_server.py
"""
GitHub Profile Checker — REMOTE API MCP Server.

Fetches a candidate's public GitHub profile via the GitHub REST API.
Returns: repos, top languages, contribution stats, bio.

Useful for the Resume Intelligence System to evaluate developer candidates.
No auth needed for public profiles (rate limit: 60 req/hr unauthenticated).
Set GITHUB_TOKEN env var for higher rate limits (5000 req/hr).
"""

from fastmcp import FastMCP
from typing import Annotated
from pydantic import Field
import os
import json

mcp = FastMCP("GitHubProfileChecker")


@mcp.tool()
def check_github_profile(
    github_username: Annotated[str | None, Field(description="GitHub username (e.g., 'torvalds', 'guido')")] = None,
) -> dict:
    """
    Fetch a candidate's public GitHub profile: bio, repos, top languages, stats.

    This calls the real GitHub REST API — a remote server example.
    """
    import urllib.request
    import urllib.error

    if not github_username:
        return {
            "status": "missing_fields",
            "missing_fields": ["github_username"],
            "message": "Missing: github_username",
        }

    username = github_username.strip().lstrip("@").split("/")[-1]  # handle URLs, @mentions

    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "ResumeMCP/1.0"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"

    # ── Fetch user profile ──────────────────────────────────────
    try:
        req = urllib.request.Request(f"https://api.github.com/users/{username}", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            user = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"status": "error", "message": f"GitHub user '{username}' not found."}
        return {"status": "error", "message": f"GitHub API error: {e.code} {e.reason}"}
    except Exception as e:
        return {"status": "error", "message": f"Network error: {str(e)}"}

    # ── Fetch top repos (sorted by stars) ───────────────────────
    try:
        req = urllib.request.Request(
            f"https://api.github.com/users/{username}/repos?sort=stars&per_page=10&type=owner",
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            repos = json.loads(resp.read().decode())
    except Exception:
        repos = []

    # ── Aggregate languages across repos ────────────────────────
    language_counts = {}
    top_repos = []
    for repo in repos[:10]:
        lang = repo.get("language")
        if lang:
            language_counts[lang] = language_counts.get(lang, 0) + 1
        top_repos.append({
            "name": repo.get("name", ""),
            "description": (repo.get("description") or "")[:80],
            "stars": repo.get("stargazers_count", 0),
            "language": lang or "N/A",
            "url": repo.get("html_url", ""),
        })

    # Sort languages by frequency
    top_languages = sorted(language_counts.items(), key=lambda x: -x[1])
    top_languages = [lang for lang, _ in top_languages[:5]]

    # ── Build response ──────────────────────────────────────────
    profile = {
        "username": user.get("login", username),
        "name": user.get("name") or "N/A",
        "bio": (user.get("bio") or "N/A")[:200],
        "location": user.get("location") or "N/A",
        "company": user.get("company") or "N/A",
        "public_repos": user.get("public_repos", 0),
        "followers": user.get("followers", 0),
        "following": user.get("following", 0),
        "profile_url": user.get("html_url", ""),
        "created_at": user.get("created_at", "N/A"),
    }

    return {
        "status": "success",
        "message": f"GitHub profile for {profile['name']} (@{username})",
        "profile": profile,
        "top_languages": top_languages,
        "top_repos": top_repos,
    }


if __name__ == "__main__":
    mcp.run()
