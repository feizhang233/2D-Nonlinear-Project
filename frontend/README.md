# Nonlinear Studio frontend

P11 is a React + TypeScript + Material UI workbench for the existing P10 FastAPI service.

The model-family selector loads complete verified examples for Frame, Continuum, Plate, and Shell.
The navigator and property inspector use each family's node count, formulation, material/property
shape, and DOF order. The canvas renders Frame line elements or Q4 surface projections; recovered
tables show Frame end forces, Continuum Cauchy stress, or Plate/Shell `N/M/Q` resultants.
The left model navigator exposes mesh as a first-class item. Its inspector lets Continuum, Plate,
and flat Shell regenerate an all-Q4 mesh with Gmsh, while Frame reports its explicit line topology. The
load inspector supports Frame member, Continuum edge, and Plate/Shell surface or edge distributed
loads with repeated canvas arrows and explicit units/direction limits.

```bash
npm install
npm run dev
```

Start the API from the repository root in another terminal:

```bash
.venv/bin/python -m nonlinear_api.main
```

Vite proxies `/api` and `/health` to `http://127.0.0.1:8000`. For a separate deployed API, set
`VITE_API_BASE_URL` and allow the frontend origin with `NONLINEAR_CORS_ORIGINS`.

The workspace runs analyses in the local asynchronous API mode, polls live step/iteration progress,
and exposes cooperative cancellation. It clears current results and restart state whenever the
model changes. Versioned restart bundles can be exported from terminal results and imported for a
continued calculation. Arc-length convergence is labelled only as augmented-equilibrium
convergence; the UI does not present it as a stability or branch-uniqueness result.
