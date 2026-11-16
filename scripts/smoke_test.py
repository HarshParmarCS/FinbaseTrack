#!/usr/bin/env python3
"""End-to-end smoke test for a running stack (`docker compose up --build`).

It talks to the FRONTEND origin, exactly like a browser: every request goes to
`<frontend>/api/v1/...` and the Next.js server forwards it to the backend container. It uses
three real users and checks authentication, CSRF, and all seven PBAC rules from the assignment.

Usage (standard library only, no dependencies):
    python3 scripts/smoke_test.py                          # http://localhost:3000
    python3 scripts/smoke_test.py --base http://localhost:3001

It creates three throwaway users (smoke-<time>-*@example.com) and one project. The project is
deleted at the end; the users and their audit rows stay. Exit code 0 means every check passed.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from typing import Any

PASSWORD = "smoke-test-password-1"
results: list[tuple[bool, str]] = []


class Client:
    """One browser: its own cookie jar, the frontend Origin, and the CSRF double-submit header."""

    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def cookie(self, name: str) -> str | None:
        return next((c.value for c in self.jar if c.name == name), None)

    def call(
        self,
        method: str,
        path: str,
        body: Any = None,
        *,
        csrf: bool = True,
        origin: str | None = None,
    ) -> tuple[int, Any, list[str]]:
        headers = {"Accept": "application/json", "Origin": origin or self.base}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        token = self.cookie("csrf_token")
        if csrf and method != "GET" and token:
            headers["X-CSRF-Token"] = token
        request = urllib.request.Request(
            f"{self.base}/api/v1{path}", data=data, method=method, headers=headers
        )
        try:
            with self.opener.open(request, timeout=15) as response:
                raw = response.read()
                status = response.status
                set_cookies = response.headers.get_all("Set-Cookie") or []
        except urllib.error.HTTPError as error:
            raw = error.read()
            status = error.code
            set_cookies = error.headers.get_all("Set-Cookie") or []
        payload = json.loads(raw) if raw else None
        return status, payload, set_cookies


def check(condition: bool, label: str) -> None:
    results.append((condition, label))
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")


def expect(actual: int, wanted: int, label: str, payload: Any = None) -> None:
    detail = ""
    if actual != wanted and isinstance(payload, dict) and "error" in payload:
        detail = f" ({payload['error'].get('code')}: {payload['error'].get('message')})"
    check(actual == wanted, f"{label}: HTTP {actual}, expected {wanted}{detail}")


def policy_of(payload: Any) -> str | None:
    try:
        policy = payload["error"]["details"][0]["policy_id"]
    except (KeyError, IndexError, TypeError):
        return None
    return policy if isinstance(policy, str) else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:3000", help="frontend URL")
    base = parser.parse_args().base
    stamp = int(time.time())
    ana, ben, cy = Client(base), Client(base), Client(base)
    email = {name: f"smoke-{stamp}-{name}@example.com" for name in ("ana", "ben", "cy")}

    print(f"Smoke test against {base} (through the frontend proxy)")

    print("Health and authentication")
    status, payload, _ = Client(base).call("GET", "/health")
    check(
        status == 200 and payload == {"data": {"status": "ok"}}, "health through the frontend proxy"
    )
    users: dict[str, str] = {}
    for name, client in (("ana", ana), ("ben", ben), ("cy", cy)):
        status, payload, cookies = client.call(
            "POST",
            "/auth/register",
            {"name": name.title(), "email": email[name], "password": PASSWORD},
        )
        expect(status, 201, f"register {name}", payload)
        users[name] = payload["data"]["id"] if status == 201 else ""
    names = sorted(c.split("=", 1)[0] for c in cookies)
    check(names == ["access_token", "csrf_token", "refresh_token"], "register sets three cookies")
    flags = {c.split("=", 1)[0]: c.lower() for c in cookies}
    check(
        "httponly" in flags.get("access_token", "")
        and "httponly" in flags.get("refresh_token", ""),
        "access and refresh cookies are HttpOnly",
    )
    check("httponly" not in flags.get("csrf_token", "x; httponly"), "csrf cookie is readable")
    status, payload, _ = ana.call(
        "POST", "/auth/login", {"email": email["ana"], "password": PASSWORD}
    )
    expect(status, 200, "login", payload)
    status, payload, _ = ana.call(
        "POST", "/auth/login", {"email": email["ana"], "password": "wrong-password"}
    )
    expect(status, 401, "login with a wrong password", payload)
    status, payload, _ = ana.call("GET", "/auth/me")
    check(status == 200 and payload["data"]["email"] == email["ana"], "authenticated GET /auth/me")
    status, payload, _ = Client(base).call("GET", "/projects")
    expect(status, 401, "protected API without a session", payload)

    print("Projects and membership")
    status, payload, _ = ana.call(
        "POST", "/projects", {"name": f"Smoke {stamp}", "description": "x"}
    )
    expect(status, 201, "owner creates a project", payload)
    project = payload["data"]["id"]
    status, payload, _ = ana.call("POST", "/projects", {"name": "No CSRF"}, csrf=False)
    expect(status, 403, "a change without the CSRF header is refused", payload)
    status, payload, _ = ana.call(
        "POST", "/projects", {"name": "Foreign"}, origin="http://evil.example"
    )
    expect(status, 403, "a change from a foreign origin is refused", payload)
    status, payload, _ = ana.call("POST", f"/projects/{project}/members", {"email": email["ben"]})
    expect(status, 201, "owner adds Ben as a member", payload)

    print("PBAC rule 1: project visibility")
    expect(ben.call("GET", f"/projects/{project}")[0], 200, "member sees the project")
    status, payload, _ = cy.call("GET", f"/projects/{project}")
    expect(status, 404, "outsider gets 404 (existence not revealed)", payload)
    status, payload, _ = cy.call("GET", "/projects")
    check(status == 200 and payload["meta"]["total"] == 0, "outsider's project list is empty")

    print("PBAC rules 2 and 3: project update and delete (owner only)")
    status, payload, _ = ben.call("PATCH", f"/projects/{project}", {"name": "Hijacked"})
    check(
        status == 403 and policy_of(payload) == "project-update",
        "member cannot update the project (403 project-update)",
    )
    status, payload, _ = ben.call("DELETE", f"/projects/{project}")
    check(
        status == 403 and policy_of(payload) == "project-delete",
        "member cannot delete the project (403 project-delete)",
    )
    expect(
        ana.call("PATCH", f"/projects/{project}", {"description": "Updated"})[0],
        200,
        "owner updates the project",
    )

    print("PBAC rule 4: task creation (members only)")
    status, payload, _ = cy.call("POST", f"/projects/{project}/tasks", {"title": "Sneaky"})
    expect(status, 404, "outsider cannot create a task", payload)
    status, payload, _ = ben.call(
        "POST", f"/projects/{project}/tasks", {"title": "Ben's task", "priority": "high"}
    )
    expect(status, 201, "member creates a task", payload)
    task = payload["data"]["id"]

    print("PBAC rule 5: task update (creator or assignee)")
    status, payload, _ = ana.call("PATCH", f"/tasks/{task}", {"title": "Owner override"})
    check(
        status == 403 and policy_of(payload) == "task-update",
        "owner who is neither creator nor assignee cannot update (403 task-update)",
    )
    expect(
        ben.call("PATCH", f"/tasks/{task}", {"title": "Ben's task, edited"})[0],
        200,
        "creator updates the task",
    )

    print("PBAC rule 7: task completion (assignee and required fields)")
    expect(
        ben.call("PATCH", f"/tasks/{task}/status", {"status": "in_progress"})[0],
        200,
        "move to In progress",
    )
    status, payload, _ = ben.call("PATCH", f"/tasks/{task}/status", {"status": "completed"})
    check(
        status == 403 and policy_of(payload) == "task-complete",
        "incomplete task cannot be completed (403 task-complete)",
    )
    status, payload, _ = ben.call(
        "PATCH",
        f"/tasks/{task}",
        {"description": "Done properly", "due_date": "2099-12-31", "assignee_id": users["ben"]},
    )
    expect(status, 200, "fill in description, due date and assignee", payload)
    expect(
        ben.call("PATCH", f"/tasks/{task}/status", {"status": "completed"})[0],
        200,
        "complete task can be completed",
    )

    print("PBAC rule 6: task delete (project owner, only while Todo)")
    status, payload, _ = ana.call("DELETE", f"/tasks/{task}")
    check(
        status == 403 and policy_of(payload) == "task-delete",
        "owner cannot delete a completed task (403 task-delete)",
    )
    status, payload, _ = ben.call("POST", f"/projects/{project}/tasks", {"title": "Throwaway"})
    todo = payload["data"]["id"]
    status, payload, _ = ben.call("DELETE", f"/tasks/{todo}")
    check(
        status == 403 and policy_of(payload) == "task-delete",
        "creator who is not the owner cannot delete a Todo task",
    )
    expect(ana.call("DELETE", f"/tasks/{todo}")[0], 204, "owner deletes a Todo task")

    print("Search, filter and pagination")
    status, payload, _ = ana.call(
        "GET", f"/projects/{project}/tasks?q=edited&status=completed&priority=high&page_size=1"
    )
    check(
        status == 200 and payload["meta"]["total"] == 1 and payload["data"][0]["id"] == task,
        "search + status + priority filter + page size",
    )

    print("Dashboard and session end")
    status, payload, _ = ben.call("GET", "/dashboard/stats")
    check(status == 200 and payload["data"]["completed_tasks"] >= 1, "dashboard statistics")
    expect(ana.call("DELETE", f"/projects/{project}")[0], 204, "owner deletes the project")
    expect(ben.call("GET", f"/tasks/{task}")[0], 404, "its tasks are gone")
    expect(ana.call("POST", "/auth/logout")[0], 204, "logout")
    expect(ana.call("GET", "/auth/me")[0], 401, "no access after logout")

    failed = [label for ok, label in results if not ok]
    print(f"\n{len(results) - len(failed)} of {len(results)} checks passed.")
    print(f"Users created: {', '.join(email.values())}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
