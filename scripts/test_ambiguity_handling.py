# -*- coding: utf-8 -*-
import sys, os
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
"""
test_ambiguity_handling.py
==========================
Regression tests for the "vague question" / Conversational Ambiguity Handling feature.

Tests are built from REAL candidate data in the DB to guarantee meaningful assertions.

Real Candidates Used:
  Somya Singhal      → Companies: AI Blocks, Samsung Research, Navi Technologies, Findem, Facebook, Samsung R&D
  Ratish Nair        → Companies: WHITEHAT JR., SECRET KITCHEN, MAKEBOT ROBOTICS, STAR CLASSES
  Shubham Baghel     → Companies: National Institute of Technology, ISRO Funded Project
  Mani Kandan        → Companies: AMAZON, SUPREME COMPUTERS INDIA PVT LTD
  SANDEEP GILL       → Companies: HDFC Bank LTD, Jana small finance bank
  BINEESHA E         → Companies: Axisbank

Test Categories
---------------
A. Wrong company for a real person    →  agent should ask clarifying question with correct companies
B. Completely unknown name            →  agent should say name not found  
C. Contradictory role/experience      →  agent should flag the contradiction
D. Correct name + correct company     →  agent should answer normally (no clarification)
E. Affirmative reply after clarification → agent should fetch actual work experience
"""

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('PYTHONPATH', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.workflows.intelligent_agent import ResumeIntelligenceAgent

agent = ResumeIntelligenceAgent()

PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️  WARN"

results = []

def run_test(label: str, query: str, session_id: str | None = None,
             conversation_context: dict | None = None,
             expect_clarification: bool = False,
             expect_no_clarification: bool = False,
             forbidden_phrases: list[str] | None = None,
             required_phrases: list[str] | None = None) -> dict:
    """Run a single test turn and evaluate the result."""
    print(f"\n{'─'*70}")
    print(f"🧪 {label}")
    print(f"   Query: {query!r}")
    result = agent.query(query, session_id=session_id, verbose=False,
                         conversation_context=conversation_context or {})
    answer = result["answer"]
    new_ctx = result.get("conversation_context", {})
    new_sid = result["session_id"]

    # Detection: was a clarification question returned?
    clarification_markers = [
        "couldn't find", "could not find", "clarify", "did you mean",
        "would you like", "incorrect", "does not appear", "i don't see",
        "may have worked", "actually", "no record", "check the name"
    ]
    answer_lower = answer.lower()
    got_clarification = any(m in answer_lower for m in clarification_markers)
    has_pending = bool(new_ctx.get("pending_clarification"))

    passed = True
    notes = []

    if expect_clarification and not got_clarification:
        passed = False
        notes.append("Expected clarification question but got normal answer")
    if expect_no_clarification and got_clarification:
        passed = False
        notes.append("Unexpectedly got clarification instead of normal answer")
    if forbidden_phrases:
        for phrase in forbidden_phrases:
            if phrase.lower() in answer_lower:
                passed = False
                notes.append(f"Forbidden phrase found: {phrase!r}")
    if required_phrases:
        for phrase in required_phrases:
            if phrase.lower() not in answer_lower:
                passed = False
                notes.append(f"Required phrase missing: {phrase!r}")

    status = PASS if passed else FAIL
    print(f"   {status}")
    if notes:
        for n in notes:
            print(f"      ↳ {n}")
    print(f"   Answer (first 200 chars): {answer[:200]}")
    if has_pending:
        ids = new_ctx["pending_clarification"].get("candidate_ids", [])
        names = new_ctx["pending_clarification"].get("candidate_names", [])
        print(f"   📌 pending_clarification set → ids={ids}, names={names}")

    results.append({
        "label": label,
        "passed": passed,
        "notes": notes,
        "session_id": new_sid,
        "conversation_context": new_ctx,
    })
    return result


# ===================================================================
# CATEGORY A: Wrong company for a real person
# ===================================================================

print("\n" + "="*70)
print("CATEGORY A: Wrong company assumption for a known candidate")
print("="*70)

# A1: Somya Singhal at Google (she was at Samsung / AI Blocks / Facebook — never Google)
r_a1 = run_test(
    label="A1: Somya Singhal at Google (wrong company)",
    query="Tell me about Somya Singhal's experience at Google",
    expect_clarification=True,
    required_phrases=["somya singhal"],
)

# A2: Ratish Nair at Infosys (he was at WHITEHAT JR, SECRET KITCHEN — never Infosys)
r_a2 = run_test(
    label="A2: Ratish Nair at Infosys (wrong company)",
    query="What did Ratish Nair do at Infosys?",
    expect_clarification=True,
    required_phrases=["ratish nair"],
)

# A3: Mani Kandan at Flipkart (he was at AMAZON and SUPREME COMPUTERS — not Flipkart)
r_a3 = run_test(
    label="A3: Mani Kandan at Flipkart (wrong company)",
    query="Show me Mani Kandan's work at Flipkart",
    expect_clarification=True,
)

# A4: SANDEEP GILL at TCS (he was at HDFC Bank and Jana small finance bank — not TCS)
r_a4 = run_test(
    label="A4: SANDEEP GILL at TCS (wrong company)",
    query="What was Sandeep Gill's role at TCS?",
    expect_clarification=True,
)

# ═══════════════════════════════════════════════════════════════════
# CATEGORY B: Unknown name
# ═══════════════════════════════════════════════════════════════════

print("\n" + "="*70)
print("CATEGORY B: Completely unknown names")
print("="*70)

# B1: Non-existent candidate
run_test(
    label="B1: Completely unknown name — 'Priya Sharma at Microsoft'",
    query="Tell me about Priya Sharma's work at Microsoft",
    expect_clarification=True,
    required_phrases=["priya sharma"],
)

# B2: Unknown candidate, no company
run_test(
    label="B2: Name not in DB — 'John Smith Python developer'",
    query="Show me John Smith's Python projects",
    expect_clarification=True,
)

# ═══════════════════════════════════════════════════════════════════
# CATEGORY C: Contradictory role / experience
# ═══════════════════════════════════════════════════════════════════

print("\n" + "="*70)
print("CATEGORY C: Contradictory role+experience assumptions")
print("="*70)

# C1: Intern with 7 years experience
run_test(
    label="C1: Junior intern with 7+ years experience (contradiction)",
    query="Find me junior interns with 7+ years of experience",
    expect_clarification=True,
    required_phrases=["junior", "experience"],
)

# C2: Fresher with 10+ years
run_test(
    label="C2: Fresher with 10+ years (contradiction)",
    query="Show me freshers who have 10 or more years of experience",
    expect_clarification=True,
)

# ═══════════════════════════════════════════════════════════════════
# CATEGORY D: Correct name + correct company (NO clarification expected)
# ═══════════════════════════════════════════════════════════════════

print("\n" + "="*70)
print("CATEGORY D: Valid queries - no clarification should fire")
print("="*70)

# D1: Somya Singhal at Samsung (she DID work there)
run_test(
    label="D1: Somya Singhal at Samsung (correct — should answer normally)",
    query="Tell me about Somya Singhal's experience at Samsung",
    expect_no_clarification=True,
)

# D2: Ratish Nair at Whitehat Jr (he DID work there)
run_test(
    label="D2: Ratish Nair at WHITEHAT JR (correct — should answer normally)",
    query="What did Ratish Nair do at Whitehat Jr?",
    expect_no_clarification=True,
)

# D3: Normal candidate search (no name, no company contradiction)
run_test(
    label="D3: Generic skill search — no ambiguity expected",
    query="Find Python developers with more than 5 years of experience",
    expect_no_clarification=True,
)

# ═══════════════════════════════════════════════════════════════════
# CATEGORY E: Affirmative follow-up after clarification
# ═══════════════════════════════════════════════════════════════════

print("\n" + "="*70)
print("CATEGORY E: Affirmative reply restores candidate context")
print("="*70)

# E1: Ask wrong company for Somya → get clarification → reply "yes"
r_e1_first = run_test(
    label="E1a: Wrong company → get clarification (sets pending_clarification)",
    query="Tell me about Somya Singhal's work at Google",
    expect_clarification=True,
)

pending_ctx = r_e1_first.get("conversation_context", {})
pending_sid = r_e1_first.get("session_id")

if pending_ctx.get("pending_clarification"):
    run_test(
        label="E1b: 'Yes' reply should fetch Somya's actual work experiences",
        query="yes",
        session_id=pending_sid,
        conversation_context=pending_ctx,
        expect_no_clarification=True,
        required_phrases=["somya singhal"],
    )
else:
    print(f"\n{'─'*70}")
    print(f"🧪 E1b: Skipped — E1a did not set pending_clarification")
    results.append({"label": "E1b (skipped)", "passed": False,
                    "notes": ["E1a didn't set pending_clarification"], "session_id": None, "conversation_context": {}})

# ═══════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════

print("\n" + "="*70)
print("SUMMARY")
print("="*70)
total = len(results)
passed = sum(1 for r in results if r["passed"])
failed = total - passed

for r in results:
    icon = "✅" if r["passed"] else "❌"
    print(f"  {icon}  {r['label']}")
    for n in r.get("notes", []):
        print(f"         ↳ {n}")

print(f"\n  Passed: {passed}/{total}")
print(f"  Failed: {failed}/{total}")

if failed == 0:
    print("\n🎉 ALL TESTS PASSED — Ambiguity Handling feature is working correctly!")
else:
    print(f"\n⚠️  {failed} test(s) failed. Review the output above for details.")
    sys.exit(1)
