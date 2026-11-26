"""Verify Redis-backed conversation state through the Nginx load balancer.

Run `python test_stateless.py --failover` to also stop one agent container and
continue the same conversation through a surviving instance.
"""
import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path

BASE_URL = "http://localhost:8080"


def post(path: str, data: dict) -> dict:
    req = urllib.request.Request(
        f"{BASE_URL}{path}", data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read())


def get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=10) as response:
        return json.loads(response.read())


def main() -> None:
    parser = argparse.ArgumentParser(description="Test stateless conversations across agent replicas")
    parser.add_argument("--failover", action="store_true",
                        help="stop one agent container and continue the conversation")
    args = parser.parse_args()

    print("=" * 60)
    print("Stateless Scaling Demo")
    print("=" * 60)
    questions = [
        "What is Docker?", "Why do we need containers?", "What is Kubernetes?",
        "How does load balancing work?", "What is Redis used for?",
    ]
    session_id = None
    instances_seen = set()
    for index, question in enumerate(questions, 1):
        result = post("/chat", {"question": question, "session_id": session_id})
        session_id = result["session_id"]
        instances_seen.add(result["served_by"])
        print(f"Request {index}: [{result['served_by']}] {question}")

    history = get(f"/chat/{session_id}/history")
    if history["count"] != 10:
        raise SystemExit(f"FAIL: expected 10 messages, got {history['count']}")
    print(f"PASS: session history intact across {len(instances_seen)} instance(s): {history['count']} messages")

    if args.failover:
        compose_dir = Path(__file__).resolve().parent
        containers = subprocess.check_output(
            ["docker", "compose", "ps", "-q", "agent"], cwd=compose_dir, text=True
        ).splitlines()
        if len(containers) < 2:
            raise SystemExit("Failover needs at least two agents; start with docker compose up --scale agent=3")
        stopped = containers[0]
        subprocess.run(["docker", "stop", stopped], check=True)
        time.sleep(3)  # let Nginx's Docker DNS resolver refresh the replica pool
        result = post("/chat", {
            "question": "Does this conversation survive an agent failure?",
            "session_id": session_id,
        })
        history = get(f"/chat/{session_id}/history")
        if result["session_id"] != session_id or history["count"] != 12:
            raise SystemExit("FAIL: conversation did not survive agent loss")
        print(f"PASS: {result['served_by']} continued the session after stopping {stopped[:12]}")


if __name__ == "__main__":
    main()
