# FinTasks: Authorization Design (PBAC)

RBAC is prohibited. There are no roles, no role columns and no role checks. "Owner" and "member" are relationships between a user and a project that conditions can read. They are not roles and are never stored on the user.

## 1. Principles

1. **Centralized.** All access decisions are made in `backend/app/authorization/`. Nowhere else.
2. **Default deny.** If no policy explicitly allows an action, it is denied.
3. **Separated from business logic.** Routers declare the action. Services and repositories contain no authorization decisions.
4. **Trusted identity only.** The subject is the user from the verified JWT. No client-supplied user ID is used.
5. **Current state.** Conditions read membership and resource state from the database for the current request.
6. **Configurable.** Policies are JSON, validated at startup. Conditions are reusable Python functions registered by name.
7. **Explainable.** Every decision returns the policy ID and a reason, and denials are logged.

## 2. Components

```
authorization/
├── engine.py        PolicyEngine: authorize(), is_allowed(), evaluation algorithm
├── registry.py      PolicyRegistry: loads and validates policies.json, maps condition names to functions
├── context.py       AuthorizationContext, Decision, ResourceState dataclasses
├── conditions/      reusable condition functions (pure)
│   ├── common.py    is_authenticated
│   ├── project.py   is_project_member, is_project_owner
│   └── task.py      is_task_creator, is_task_assignee, task_status_is, task_has_assignee,
│                    task_required_fields_present
├── dependencies.py  authorize(...) FastAPI dependency factory, resource loaders, action resolver
└── policies.json    policy definitions
```

### AuthorizationContext
```
user:      the authenticated User (from the verified JWT)
action:    string such as "task:update"
project:   Project | None             (loaded resource)
task:      Task | None                (loaded resource, current state)
proposed:  TaskState | None           (resulting state if the write succeeds: current task merged with the payload; for create, built from the payload)
is_member: bool                       (current membership of user in project, queried once per request)
```
Conditions receive the context and optional parameters from the policy. They never touch HTTP objects and never write.

### Decision
```
Decision { allowed: bool, policy_id: str | None, reason: str }
```

## 3. Policy file format (`policies.json`)

```json
{
  "version": 1,
  "default_effect": "deny",
  "policies": [
    {
      "id": "task-delete",
      "description": "Only the project owner may delete a task, and only while it is todo.",
      "action": "task:delete",
      "effect": "allow",
      "conditions": { "all": ["is_project_owner", { "fn": "task_status_is", "value": "todo" }] },
      "deny_reason": "Only the project owner can delete a task whose status is todo."
    }
  ]
}
```

Fields: `id` (unique), `description`, `action`, `effect` (`allow` or `deny`), `conditions`, `deny_reason` (optional, shown when the policy is the one that failed).

Condition grammar:
- `"name"`: a registered condition with no parameters.
- `{ "fn": "name", ...params }`: a registered condition with parameters.
- `{ "all": [node, ...] }`: true if every node is true.
- `{ "any": [node, ...] }`: true if at least one node is true.
- `{ "not": node }`: negation.

Validation at startup (failure aborts the app): valid JSON structure, unique IDs, `default_effect` is `deny`, every condition name exists in the registry, parameters are valid for the condition, `all`/`any` are non-empty.

## 4. Evaluation algorithm

`PolicyEngine.authorize(user, action, resource, payload)` (the context is built from these):

1. Collect policies whose `action` equals the requested action. If none exist: deny, `policy_id = null`, reason "No policy allows this action" (default deny).
2. Evaluate each collected policy's conditions.
3. If any matching `deny` policy's conditions are true: deny (explicit deny wins).
4. Else if any matching `allow` policy's conditions are true: allow, return its ID.
5. Else deny, return the ID of the first allow policy considered and its `deny_reason`.

Composite checks: when one request involves several actions (see 6), ALL must be allowed. The first denial is returned.

`PolicyEngine.is_allowed(...)` runs the same algorithm without logging or raising. It is used to build `allowed_actions`.

## 5. Action and policy catalog

| Action | Policy ID | Conditions |
|---|---|---|
| `project:create` | `project-create` | `is_authenticated` |
| `project:view` | `project-view` | `is_project_member` |
| `project:update` | `project-update` | `is_project_owner` |
| `project:delete` | `project-delete` | `is_project_owner` |
| `project:member:manage` | `project-member-manage` | `is_project_owner` |
| `task:create` | `task-create` | `is_project_member` |
| `task:view` | `task-view` | `is_project_member` |
| `task:update` | `task-update` | `is_project_member` AND (`is_task_creator` OR `is_task_assignee`) |
| `task:delete` | `task-delete` | `is_project_owner` AND `task_status_is(todo)` |
| `task:complete` | `task-complete` | `is_project_member` AND `task_has_assignee` AND `task_required_fields_present(title, description, assignee_id, due_date)` |

Mapping to the seven mandatory assignment policies:
- Project visibility: `project-view`. Project update: `project-update`. Project delete: `project-delete`.
- Task creation: `task-create`. Task update: `task-update`. Task delete: `task-delete`. Task completion: `task-complete`.
- Additional policies (assumptions): `project-create`, `project-member-manage`, `task-view`.

### Condition catalog
| Condition | Parameters | True when |
|---|---|---|
| `is_authenticated` | none | context user is an active, verified user |
| `is_project_member` | none | user is currently a member of `context.project` (owner counts because the owner is a member) |
| `is_project_owner` | none | `context.project.owner_id == user.id` AND user is a current member |
| `is_task_creator` | none | `context.task.creator_id == user.id` |
| `is_task_assignee` | none | `context.task.assignee_id == user.id` |
| `task_status_is` | `value` | `context.task.status == value` (current state) |
| `task_has_assignee` | none | `context.proposed.assignee_id` is not null (resulting state) |
| `task_required_fields_present` | `fields` (list) | every listed field of `context.proposed` is non-null and, for strings, non-blank (resulting state) |

Conditions are pure functions of the context. New conditions are added in `conditions/` and registered by name.

## 6. Request flow

### Dependency
Each protected route declares its action through one dependency:

```python
@router.patch("/tasks/{task_id}", response_model=...)
def update_task(
    task_id: UUID,
    payload: TaskUpdate,
    ctx: AuthzResult = Depends(authorize("task:update", load=load_task_for_update)),
    service: TaskService = Depends(...),
):
    return ok(service.update_task(ctx.task, payload, actor=ctx.user))
```

The dependency:
1. Gets the current user from `get_current_user` (verified JWT).
2. Loads the resource using the loader (task, then its project). Missing resource gives 404.
3. Computes membership. For project-scoped resources a non-member gets 404 (hides existence) instead of evaluating policies.
4. Builds `proposed` from the payload where the action writes a task.
5. Resolves the list of actions to check (see below), calls the engine, and returns the loaded objects so the service does not re-fetch.
6. On denial: log (user ID, action, policy ID, reason) and raise `PermissionDeniedError`, which becomes 403 with `details[0] = {policy_id, reason}`.

### Action resolver
| Request | Actions evaluated |
|---|---|
| `PATCH /projects/{id}` | `project:update` |
| `POST .../members`, `DELETE .../members/{user_id}` | `project:member:manage` |
| `POST /projects/{id}/tasks` | `task:create`; plus `task:complete` if the requested status is `completed` |
| `PATCH /tasks/{id}` | `task:update`; plus `task:complete` if the resulting status is `completed` |
| `DELETE /tasks/{id}` | `task:delete` |
| `GET` project, members, activity | `project:view` |
| `GET` task | `task:view` |

Completion is evaluated against the resulting state: if a task is already `completed` and a PATCH clears its due date, the resulting state is incomplete and the update is denied.

### 404 versus 403
The non-member check happens first (it is the `project:view` / `task:view` policy, evaluated implicitly by the dependency before the route's own action). A non-member never receives 403 for project or task resources. A member denied by a policy receives 403. This is why the contract lists `project:view` + the route action for write endpoints.

### List and aggregate endpoints (data scoping)
`GET /projects`, `GET /dashboard/stats` and `GET /dashboard/activity` have no single resource to authorize. They return only data from projects where the user is a member. The service passes the verified user ID into a repository membership filter. This is the data-scoping form of the `project:view` policy, and it is tested explicitly (a non-member's data never appears). `GET /projects/{id}/tasks` first passes `project:view`.

### allowed_actions
When building `ProjectOut` and `TaskOut`, the service asks the engine (`is_allowed`) for the actions listed in the contract and returns the allowed ones. The mapping is:
- Project: `update` is `project:update`, `delete` is `project:delete`, `manage_members` is `project:member:manage`, `create_task` is `task:create`.
- Task: `update` is `task:update`, `delete` is `task:delete`, `complete` is `task:complete` evaluated against the current task state (as if status were completed).

This keeps one source of truth. The UI never replicates policy logic.

## 7. Membership changes

Membership is read from the database in every request (no caching across requests). Removing a member deletes their `project_members` row and unassigns their tasks in one transaction. From the next request they receive 404 for the project and its tasks. Their JWT remains valid, but it carries identity only and no permissions.

## 8. Logging and audit

- Denials: INFO log with request ID, user ID, action, policy ID and reason.
- Allowed mutations are written to `activity_logs` by services (not by the authorization module).
- Startup logs the number of policies loaded and the policy file version.

## 9. Testing matrix (`backend/tests/authorization/`)

Unit tests run on constructed contexts with no database. API tests (`tests/api/`) confirm the end-to-end status codes.

| Policy | Allow case | Deny case | Default-deny / edge |
|---|---|---|---|
| `project-create` | any authenticated user | n/a | unauthenticated gets 401 |
| `project-view` | member | non-member gives 404 | unknown action is denied |
| `project-update` | owner | member non-owner gives 403 | non-member 404 |
| `project-delete` | owner | member non-owner gives 403 | non-member 404 |
| `project-member-manage` | owner | member non-owner gives 403 | removing the owner gives 422 |
| `task-create` | member | non-member gives 404 | member removed then create gives 404 |
| `task-view` | member | non-member gives 404 | |
| `task-update` | creator member, assignee member | member who is neither gives 403, owner who is neither gives 403 | removed creator or assignee gives 404 |
| `task-delete` | owner and `todo` | owner and `in_progress` gives 403, creator non-owner gives 403 | completed task gives 403 |
| `task-complete` | assignee set and all required fields present | no assignee gives 403, missing due date or description gives 403 | completing at create time is checked too; clearing a field on a completed task is denied |

Engine tests: default deny with no policy, explicit deny beats allow, `all`/`any`/`not` composition, unknown condition fails at startup, duplicate policy ID fails at startup, invalid parameters fail at startup, and `is_allowed` equals `authorize` outcomes.

## 10. Extending

1. Add or update the policy in this document.
2. Add the condition function (if new) in `conditions/` and register it.
3. Add the policy to `policies.json`.
4. Add allow, deny and default-deny tests.
5. Reference the action from the route through `authorize(...)`.

## 11. Non-goals

Roles, role hierarchies, groups, permissions tied to roles, per-user permission tables, runtime policy editing through the API, caching of decisions across requests.
