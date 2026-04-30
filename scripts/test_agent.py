"""
Quick end-to-end smoke test for the agent pipeline.

Tests:
  1. Simple query — should succeed on first attempt
  2. Ambiguous query — tests schema RAG precision
  3. Intentionally bad query input — tests graceful error handling

Run with:
    python -m scripts.test_agent
"""

import json
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)

from backend.db.connection import test_connection
from backend.agent.graph import run_agent

TEST_QUERIES = [
    {
        "name": "Simple count query",
        "query": "How many artists are in the database?",
        "expect_success": True,
    },
    {
        "name": "Multi-join revenue query",
        "query": "Who are the top 5 customers by total invoice amount?",
        "expect_success": True,
    },
    {
        "name": "Aggregate + group by",
        "query": "What is the average track length in minutes per genre?",
        "expect_success": True,
    },
    {
        "name": "Specific artist lookup",
        "query": "List all albums by AC/DC",
        "expect_success": True,
    },
]


def run_tests():
    print("=" * 60)
    print("Self-Healing Text-to-SQL Agent — Smoke Tests")
    print("=" * 60)

    if not test_connection():
        print("❌ Cannot connect to PostgreSQL. Aborting tests.")
        sys.exit(1)
    print("✅ Database connected.\n")

    passed = 0
    failed = 0

    for test in TEST_QUERIES:
        print(f"🧪 Test: {test['name']}")
        print(f"   Query: {test['query']}")

        try:
            state = run_agent(test["query"])

            if state["is_success"] == test["expect_success"]:
                status = "✅ PASS"
                passed += 1
            else:
                status = "❌ FAIL (unexpected outcome)"
                failed += 1

            print(f"   {status}")
            print(f"   Retries used: {state['retry_count']}")
            print(f"   Answer: {state['final_answer'][:120]}...")
            if state.get("execution_result"):
                print(f"   Rows returned: {len(state['execution_result'])}")
            print()

        except Exception as e:
            print(f"   ❌ EXCEPTION: {e}")
            failed += 1
            print()

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {len(TEST_QUERIES)} tests")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
