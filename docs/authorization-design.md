# FinTasks: Authorization Design (PBAC)

RBAC is prohibited. There are no roles, no role columns and no role checks. "Owner" and "member" are relationships between a user and a project that conditions read from the database. They are never stored on the user and never grant anything by themselves: only a policy can allow an action.

## 1. Principles

1. **Centralized.** Every access decision is made by the policy engine in `backend/app/authorization/`. Nowhere else.
2. **Default deny / fail closed.** No matching allow policy means deny. Unknown action, missing policy, unknown condition, missing data or an error during evaluation all mean deny.
3. **Decide in one place, enforce in the service layer.** Services call `AuthorizationService.require(...)` before every mutation. That single call is the only authorization code a service contains. Services never inspect ownership, membership or status to decide access. Routers and repositories contain no authorization at all.
4. **Framework independent.** The engine and everything it uses never import FastAPI or raise HTTP exceptions. The engine returns a `Decision`. The enforcement point raises domain errors, which the central exception handlers turn into 403 or 404.
5. **Trusted identity only.** The subject is the user from the verified JWT. Project, creator and assignee identities are always read from the database, never from the request.
6. **Current state.** Membership, ownership and task attributes are read from the database for each decision. Nothing is cached across requests, so a removed member loses access on their next request.
7. **Configurable and safe.** Policies are JSON. Condition names map to predefined Python functions. JSON is never evaluated as code (no `eval`, `exec`, dynamic imports).
8. **Explainable.** Each decision carries the policy ID, a reason code and the failed conditions. Denials are logged.

## 2. PEP, PDP, PAP, PIP

| Role | Responsibility | Implementation |
|---|---|---|
| **PEP** (Policy Enforcement Point) | Asks for a decision before an action and enforces it | `AuthorizationService.require*` in `service.py`, called by the service layer; raises `PermissionDeniedError` (403) or `NotFoundError` (404) |
| **PDP** (Policy Decision Point) | Evaluates policies against a context and returns a `Decision` | `PolicyEngine` in `engine.py`, with `registry.py`, `policies.py`, `conditions.py` |
| **PAP** (Policy Administration Point) | Where policies are defined, validated and loaded | `policies.json` (version controlled, changed by code review) and `policy_loader.py`, which validates it at startup |
| **PIP** (Policy Information Point) | Supplies the current facts the policies need | `PolicyInformationPoint` in `information.py`: reads membership, project and task state from PostgreSQL |

## 3. Module layout

```
app/authorization/
├── __init__.py       public API
├── decision.py       Decision (frozen dataclass) and ReasonCode
├── context.py        AuthorizationContext, Subject, ProjectFacts, TaskFacts, TaskChanges
├── conditions.py     condition functions and the safe condition registry
├── policies.py       Action, Effect, Policy, condition tree evaluation, PolicyConfigError
├── registry.py       PolicyRegistry: action identifier to policies
├── policy_loader.py  loads and validates policies.json
├── engine.py         PolicyEngine (the PDP)
├── information.py    PolicyInformationPoint (the PIP)
├── service.py        AuthorizationService (the PEP)
├── dependencies.py   FastAPI providers for the engine and the service
└── policies.json     the seven policies
```

Only `dependencies.py` imports FastAPI. A test enforces that no other file in the package does.

## 4. Actions and policies

Action identifiers use dots. Nine policies exist, the seven mandatory ones plus two supporting ones added with the project endpoints (M5). Any other action is denied.

| Action | Policy ID | Conditions (all must hold) |
|---|---|---|
| `project.view` | `project-view` | `is_project_member` |
| `project.update` | `project-update` | `is_project_owner` |
| `project.delete` | `project-delete` | `is_project_owner` |
| `task.create` | `task-create` | `is_project_member` |
| `task.update` | `task-update` | `is_project_member` AND (`is_task_creator` OR `is_task_assignee`) |
| `task.delete` | `task-delete` | `is_project_owner` AND `task_status_is(todo)` |
| `project.create` | `project-create` | `is_authenticated` |
| `project.member.manage` | `project-member-manage` | `is_project_owner` |
| `task.complete` | `task-complete` | `is_project_member` AND `task_has_assignee` AND `task_required_fields_complete(title, description, priority, due_date, assignee)` |

Notes:
- **Membership is part of every project and task policy.** `is_project_owner` itself requires current membership. A removed member (or a stale creator or assignee) is therefore denied immediately.
- **Reading a task** uses `project.view` evaluated against the task's project. There is no separate task-view policy.
- **`project.create`** allows any authenticated, active user. **`project.member.manage`** (add and remove members) is owner-only. Both were added in M5; before that they were denied.
- **Completion is checked on the resulting state.** Any write whose resulting status is `completed` (create or update) must satisfy both the base action and `task.complete`, evaluated against the task as it would be after the write. This makes "clear the due date of a completed task" a denied update.
- **"Has an assignee"** means the resulting assignee is set AND is currently a member of the task's project.
- **Required completion fields:** `title`, `description`, `priority`, `due_date`, `assignee`. A text field counts as complete only if it is not blank. They are configured in `policies.json`.
- **Data scoping, not policy:** list and aggregate endpoints (project list, dashboard) filter by membership in the query. A non-member's data never appears.

## 5. Policy file format (`policies.json`)

```json
{
  "version": 1,
  "default_effect": "deny",
  "policies": [
    {
      "id": "task-delete",
      "action": "task.delete",
      "effect": "allow",
      "operator": "all",
      "conditions": ["is_project_owner", {"name": "task_status_is", "value": "todo"}],
      "description": "Only the project owner can delete a task, and only while it is todo."
    }
  ]
}
```

Policy fields: `id` (unique, lowercase with hyphens), `action` (must be a known action), `effect` (`allow` or `deny`), `conditions` (non-empty list), `operator` (`all` or `any`, default `all`), `description` (optional, used in the 403 message). No other keys are accepted.

A condition entry is one of:
- `"name"`: a registered condition without parameters;
- `{"name": "...", <parameters>}`: a registered condition with parameters (every parameter is required and validated);
- `{"operator": "all" | "any", "conditions": [...]}`: a nested group (maximum depth 4).

The loader rejects, at startup, with a `PolicyConfigError` that aborts the application:
unreadable or invalid JSON, a document that is not an object, unknown keys, a wrong `version`, `default_effect` other than `deny`, an unknown action, a missing policy for a required action, duplicate policy IDs, an unknown condition, an unsupported operator, an empty condition list, wrong parameter names or values, an invalid effect, and malformed entries.

### Safe condition registry
`conditions.py` holds a fixed dictionary from condition name to a `ConditionSpec` (the Python function and its parameter validators). The JSON can only select entries of this dictionary. It cannot supply code, module names or expressions.

| Condition | Parameters | True when |
|---|---|---|
| `is_authenticated` | none | the subject is an authenticated, active user (the subject comes only from the verified token) |
| `is_project_member` | none | a project is in the context and the subject is currently a member |
| `is_project_owner` | none | the subject is currently a member AND `project.owner_id` equals the subject's ID |
| `is_task_creator` | none | the stored task's `creator_id` equals the subject's ID |
| `is_task_assignee` | none | the stored task's `assignee_id` equals the subject's ID |
| `task_status_is` | `value` (`todo`, `in_progress`, `completed`) | the stored task has that status |
| `task_has_assignee` | none | the resulting task has an assignee who is currently a project member |
| `task_required_fields_complete` | `fields` (subset of `title`, `description`, `priority`, `due_date`, `assignee`) | every listed field of the resulting task is filled in |

A condition returns `True` only for an explicit `True`. Missing data (no project, no task) is `False`.

## 6. Context and decision

```
AuthorizationContext (frozen)
  subject        Subject(id, is_active)           the authenticated user
  action         str                              e.g. "task.update"
  project        ProjectFacts(id, owner_id)|None  current state from the database
  is_project_member  bool                         current membership of the subject
  task           TaskFacts | None                 current stored state
  proposed_task  TaskFacts | None                 state after the requested change (create or update)
  assignee_is_project_member  bool                is the resulting assignee a current member

Decision (frozen)
  allowed, action, policy_id, reason_code, failed_conditions
ReasonCode: ALLOWED, EXPLICIT_DENY, CONDITIONS_NOT_MET, NO_POLICY, UNKNOWN_ACTION,
            SUBJECT_INACTIVE, RESOURCE_NOT_FOUND, EVALUATION_ERROR
```

## 7. Evaluation algorithm (PDP)

`PolicyEngine.evaluate(context) -> Decision`. It never raises: any exception during evaluation produces `Decision(allowed=False, reason_code=EVALUATION_ERROR)`.

1. Subject not active: deny (`SUBJECT_INACTIVE`).
2. Action not one of the known actions: deny (`UNKNOWN_ACTION`).
3. No policy registered for the action: deny (`NO_POLICY`).
4. Any matching `deny` policy: deny (`EXPLICIT_DENY`). Explicit deny wins.
5. Any matching `allow` policy: allow (`ALLOWED`, returns the policy ID).
6. Otherwise deny (`CONDITIONS_NOT_MET`, with the policy ID and the failed condition names).

## 8. Enforcement and request lifecycle (PEP)

```
HTTP request
 -> middleware (request ID, CSRF)               401 if authentication is missing or invalid
 -> get_current_user                            (identity from the verified JWT)
 -> router: validate input, call ONE service method (no authorization code)
 -> service: authz.require(user, "task.delete", task_id=...)       <- PEP
      -> PIP: reads the task, its project, current membership from PostgreSQL
              (project and creator identities come from the database, never the client)
      -> PDP: PolicyEngine.evaluate(context) -> Decision
      -> allowed: continue            denied: raise a domain error
 -> service: business rules, repository calls, commit
 -> router wraps the result in the envelope
 -> exception handlers: PermissionDeniedError -> 403, NotFoundError -> 404
```

`AuthorizationService` methods:
- `evaluate(user, action, ...) -> Decision`: never raises.
- `allowed_project_actions(user, project_facts, is_member) -> set[Action]`: evaluates the project-level actions for facts the caller has already loaded, with no extra queries. Used to fill `allowed_actions` for a whole project list without N+1 queries.
- `require(user, action, project_id=... | task_id=..., changes=...) -> AuthorizationContext`: raises when denied.
- `require_task_create(user, project_id, changes)` and `require_task_update(user, task_id, changes)`: apply the base policy and, when the resulting status is `completed`, also `task.complete`, on the same facts.

Mapping of denials:

| Situation | Result |
|---|---|
| Project or task does not exist | `NotFoundError`, 404 |
| User is not a member of the project (including a task reached by a guessed UUID) | `NotFoundError`, 404, identical to "does not exist" so nothing is revealed |
| Member denied by a policy | `PermissionDeniedError`, 403, with the policy ID and its description in `details` |
| No or invalid authentication | 401, raised before authorization |

A task is always addressed by its own ID. The service passes only `task_id` and the PIP derives the project from the database. When a project ID is supplied (for example when creating a task) it is only a lookup key: membership in that project is verified, and a client-supplied ID cannot grant access.

## 9. Membership changes

Membership is read from PostgreSQL on every decision using column queries, so no stale ORM object can answer. Removing a member deletes their `project_members` row (after unassigning their tasks). From the very next decision they are a non-member (404) even if the same database session already loaded their old membership.

## 10. Logging

- Denials: INFO, with user ID, action, policy ID, reason code and failed conditions.
- Evaluation errors: ERROR with traceback (the decision is still deny).
- Startup: the number of policies loaded. A policy error stops the application.

## 11. Testing matrix (`backend/tests/authorization/`)

Every policy has a positive, a negative and a boundary test, using in-memory contexts (no database).

| Policy | Positive | Negative | Boundary |
|---|---|---|---|
| `project-view` | member | non-member | owner whose membership row is gone; inactive subject |
| `project-update` | owner | member who is not the owner | owner of another project; owner no longer a member |
| `project-delete` | owner | member who is not the owner | same as update |
| `task-create` | member | non-member | removed member; no project in the context |
| `task-update` | creator; assignee | member who is neither (including the project owner) | removed creator; removed assignee; user who is both |
| `task-delete` | owner and `todo` | non-owner and `todo`; owner and `completed` | owner and `in_progress` |
| `task-complete` | assignee set and all fields filled | no assignee | blank description; each field missing in turn; non-member assignee; resulting state complete while stored state is not, and the reverse |

Engine tests: default deny, unknown action, missing policy, explicit deny wins, `any`/`all`/nested groups, failing condition fails closed, inactive subject. Loader tests: every rejection listed in section 5. Service tests against PostgreSQL: removed member, guessed task UUID, 403 versus 404, the completion double check, stale session. HTTP tests: 401 versus 403 versus 404. Structural tests: no FastAPI imports outside `dependencies.py`, no `eval`/`exec`/`compile`/dynamic imports, and no role-like identifiers or columns anywhere.

## 12. Extending

1. Add or change the policy here.
2. Add a condition (if needed) to `conditions.py` and register it with its parameter validators.
3. Add the action to `Action` in `policies.py` and the policy to `policies.json`.
4. Add positive, negative and boundary tests.
5. Call `authz.require(...)` from the service that performs the action.

## 13. Non-goals

Roles, role hierarchies, groups, permissions attached to users, runtime policy editing through the API, caching decisions across requests.
