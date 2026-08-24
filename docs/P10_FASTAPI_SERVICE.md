# P10 FastAPI Service

## 1. Status and boundary

P10 exposes the validated nonlinear-core workflow as a bounded local HTTP service:

```text
HTTP request
  -> request-byte limit
  -> P1 contract and semantic validation
  -> DOF and control-parameter limits
  -> P2/P9 adapter validation
  -> authenticated optional restart state
  -> adaptive P7 load/displacement or P8 arc-length solver
  -> live progress/cancellation callback
  -> immutable API analysis record
```

The service is intended for small models. A request may run synchronously, or return a queued
record immediately and continue in one daemon thread. The latter is observable local execution,
not a durable or distributed worker queue.

## 2. Endpoints

| Method and path | Purpose | Success response |
|---|---|---|
| `GET /health` | API/core version, execution mode, limits | `200 HealthResponse` |
| `POST /api/v1/models/validate` | Contract/semantic validation without solving | `200 ModelValidationResponse` |
| `POST /api/v1/analyses` | Validate and run or enqueue one analysis | `201 AnalysisRecord` |
| `GET /api/v1/analyses/{id}` | Retrieve the retained analysis record | `200 AnalysisRecord` |
| `DELETE /api/v1/analyses/{id}` | Cooperatively cancel a queued/running analysis | `200 AnalysisRecord` |

`AnalysisRequest` wraps the complete P1 model and accepts `target_load_factor` for load control or
`number_of_steps` for displacement/arc-length control. It may also carry a versioned restart with
an authenticated committed state; arc-length continuation additionally requires the previous
converged augmented increment. Cross-control parameters are rejected instead of being ignored.

Run locally with:

```bash
python -m pip install -e '.[dev]'
nonlinear-api
```

The default address is `http://127.0.0.1:8000`; OpenAPI, Swagger UI, and ReDoc are available at
`/openapi.json`, `/docs`, and `/redoc`.

## 3. Status, progress, and execution

Every record carries:

- `analysis_id`, model ID/hash, control method, DOF count, and execution mode;
- `queued`, `running`, `succeeded`, `failed`, or `cancelled` status;
- creation/start/completion timestamps and live step, iteration, and accepted-step progress;
- the real `SolveResult` or a typed API error.

Synchronous HTTP calls use `asyncio.to_thread()`. Asynchronous calls use a local daemon thread and
return the queued record immediately; clients poll GET. Each Newton loop emits the real step and
iteration to the store and checks a cancellation event. Cancellation raises a dedicated stop
signal outside numerical failure classification, marks the record `cancelled`, and prevents a late
worker return from overwriting it. Uncommitted trial output is discarded.

The store is process-local and is cleared on application shutdown. There is no persistence,
multi-process record sharing, authentication, tenancy, or durable queue in P10.

## 4. Limits

Defaults are:

```text
max_request_bytes = 1,048,576
max_dofs          = 10,000
```

The ASGI middleware checks declared and streamed body bytes before Pydantic/solver allocation.
Oversized requests return `413 REQUEST_TOO_LARGE`. A structurally valid model above the DOF limit
remains `valid=true` at the validation endpoint but has `execution_eligible=false`; analysis
submission returns `413 DOF_LIMIT_EXCEEDED`.

Applications embedding `create_app()` may supply smaller `ApiLimits` and explicit CORS origins.
The command-line app reads comma-separated origins from `NONLINEAR_CORS_ORIGINS`; CORS is opt-in.

## 5. Error contract

All API errors use:

```json
{
  "error": {
    "category": "input | computation | server",
    "code": "STABLE_MACHINE_CODE",
    "message": "human-readable explanation",
    "location": "optional JSON path",
    "details": {}
  }
}
```

- Input/schema/limit errors use stable `4xx` responses and retain JSON locations.
- An unexpected execution exception returns a server-category `500`; the stored record has no
  fabricated solver result.
- Numerical nonconvergence is not a server error. POST returns `201` with `status=failed`, a
  computation-category error, and the original failed `SolveResult`, including rejected steps,
  iteration history, and solver failures. No displacement or post-processing result is invented.

Converged equilibrium, including an arc-length path, remains a numerical result rather than a
stability, uniqueness, or automatic branch-selection claim.

## 6. Acceptance evidence

- `tests/unit/test_p10_api_service.py` covers DOF eligibility, task cancellation, discarded output,
  and unexpected runner failures.
- `tests/integration/test_p10_fastapi.py` covers OpenAPI generation, sync and async execution,
  progress, cancellation, restart continuation, opt-in CORS, retrieval, stable 4xx responses,
  request/DOF limits, and a real numerical-failure record instead of HTTP 500.
