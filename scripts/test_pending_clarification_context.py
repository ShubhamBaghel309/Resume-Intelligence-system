# -*- coding: utf-8 -*-
import json
import os
import sqlite3
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.workflows.intelligent_agent import ResumeIntelligenceAgent


def pick_candidate_with_wrong_company(db_path: str) -> tuple[str, str, list[str]]:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT candidate_name, work_experience
        FROM parsed_resumes
        WHERE candidate_name IS NOT NULL
          AND work_experience IS NOT NULL
          AND TRIM(work_experience) <> ''
        """
    )
    wrong_company_pool = ["Google", "Microsoft", "Amazon", "TCS", "Infosys", "Flipkart"]

    for candidate_name, work_experience in cur.fetchall():
        try:
            parsed = json.loads(work_experience)
        except Exception:
            continue

        companies = []
        for item in parsed:
            if isinstance(item, dict) and item.get("company"):
                companies.append(str(item["company"]).strip())

        if not companies:
            continue

        companies_lower = {company.lower() for company in companies}
        for wrong_company in wrong_company_pool:
            if wrong_company.lower() not in companies_lower:
                conn.close()
                return candidate_name, wrong_company, companies

    conn.close()
    raise RuntimeError("Could not find a candidate fixture for pending clarification test.")


def assert_contains(text: str, expected: str, label: str) -> None:
    if expected.lower() not in text.lower():
        raise AssertionError(f"{label}: expected to find {expected!r} in {text!r}")


def assert_not_contains(text: str, forbidden: str, label: str) -> None:
    if forbidden.lower() in text.lower():
        raise AssertionError(f"{label}: found forbidden phrase {forbidden!r} in {text!r}")


def main() -> None:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(repo_root, "resumes.db")
    candidate_name, wrong_company, actual_companies = pick_candidate_with_wrong_company(db_path)

    print("=" * 80)
    print("Pending Clarification Context Regression")
    print("=" * 80)
    print(f"Candidate fixture: {candidate_name}")
    print(f"Wrong company: {wrong_company}")
    print(f"Actual companies: {', '.join(actual_companies[:4])}")

    agent = ResumeIntelligenceAgent()
    initial_query = f"Tell me about {candidate_name}'s work experience at {wrong_company}"

    print("\n[Case 1] Bare 'yes' follow-up with session-only context")
    first = agent.query(initial_query, verbose=False)
    print("Initial answer:", first["answer"])
    assert_contains(first["answer"], "Would you like", "initial clarification")

    second = agent.query("yes", session_id=first["session_id"], verbose=False)
    print("Follow-up answer:", second["answer"])
    assert_contains(second["answer"], candidate_name, "bare yes follow-up")
    assert_not_contains(
        second["answer"],
        "I couldn't find any candidates matching your criteria",
        "bare yes follow-up",
    )

    print("\n[Case 2] Natural-language affirmative follow-up with session-only context")
    third = agent.query(initial_query, verbose=False)
    print("Initial answer:", third["answer"])
    assert_contains(third["answer"], "Would you like", "initial clarification 2")

    fourth = agent.query(
        "yes tell me summary of their actual work experience",
        session_id=third["session_id"],
        verbose=False,
    )
    print("Follow-up answer:", fourth["answer"])
    assert_contains(fourth["answer"], candidate_name, "natural affirmative follow-up")
    assert_not_contains(
        fourth["answer"],
        "I couldn't find any candidates matching your criteria",
        "natural affirmative follow-up",
    )

    print("\nPASS: pending clarification context is restored correctly across session-only follow-ups.")


if __name__ == "__main__":
    main()
