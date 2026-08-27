# Nonlinear Studio UX Contract

## Product context

Nonlinear Studio is a desktop-first structural analysis workbench for engineers who define a finite-element model, run a bounded nonlinear solve, and review numerical evidence. The current owned interface is English-only and supports four independent model families: Frame, Continuum, Plate, and Shell.

The repository's model schemas, solver contracts, existing sample models, and P1-P16 verification evidence are the product's authoritative business sources. The interface must expose solver state precisely and must not imply that an uncommitted edit or stale result is current.

## Visual contract

- Use the existing MUI theme and its cool engineering surface palette.
- Preserve dense desktop information architecture and the 1120 px minimum application width.
- Use color only with a textual, numeric, icon, line-style, or table equivalent.
- Keep modeling and result evidence literal; avoid decorative dashboard cards or marketing visual language.

## Canonical application map

```text
Application shell
├── Account and file actions
├── Mode: Model | Results
├── Workspace bar: Frame | Continuum | Plate | Shell
├── Model mode
│   ├── Workflow rail
│   ├── Model tree and forms workspace
│   ├── Model editing canvas
│   └── Apply / Cancel transaction strip
└── Results mode
    ├── Read-only result canvas
    └── Result evidence workspace
```

## Workspace and navigation contract

- Frame, Continuum, Plate, and Shell are independent workspaces. Each preserves its own committed model, staged model, selection, form state, analysis options, result, and result view.
- The workspace bar is the only model-family navigation owner.
- Model and Results are separate top-level modes. A successful solve enters Results mode for the active workspace. Results mode never exposes model mutation controls.
- Results is unavailable until the active workspace has result evidence. Returning to Model does not delete the result.
- Switching workspaces with staged changes must open the app-owned unsaved-changes dialog. The user may keep editing, discard and continue, or apply and continue.

## Edit transaction contract

- Model and analysis-option edits are staged immediately in the visible controls but do not mutate the committed model.
- A persistent strip states that changes are unapplied and owns `Cancel` and `Apply changes`.
- `Apply changes` commits the staged model as one revision and invalidates older result evidence.
- `Cancel` restores the committed model and committed analysis options.
- Run, Save, Export, and Results navigation are unavailable while staged changes exist.
- Closing or reloading the browser with staged changes invokes the platform's leave-page warning.
- Import, example reset, history open, and workspace changes use the same unsaved-changes guard.

## Model tree, forms, and canvas

- The model tree and form inspector are the primary entry points for selecting and editing model entities.
- The canvas supports graphical model editing such as adding or moving editable Frame geometry, placing supports and loads, and sketching surface-family geometry.
- For Continuum, Plate, and Shell, generated mesh nodes and elements are visible and selectable for inspection by default, but cannot be directly added, moved, renamed, rewired, or deleted.
- Surface topology changes originate from Geometry and Mesh and return a newly generated staged mesh.
- Frame nodes and elements remain directly editable because their topology is the authored structural model.

## Flow ledger

| Trigger | Entry point | Staged state | Commit | Success | Failure or recovery |
| --- | --- | --- | --- | --- | --- |
| Edit entity | Tree/form/canvas | Draft model | Apply changes | Revision increments; result becomes invalidated | Cancel restores committed values |
| Change analysis option | Analysis form | Draft run options | Apply changes | Options become solver input | Cancel restores committed options |
| Switch workspace | Workspace bar | Unsaved dialog when needed | Apply or discard | Target workspace restores its local state | Keep editing leaves current workspace unchanged |
| Generate surface mesh | Mesh form | Busy, then staged model | Apply changes | New Q4 mesh is committed | Error remains in current form; old committed mesh survives |
| Run analysis | Top app bar | Queued/running progress | Server-committed accepted states | Enters Results mode with current evidence | Cancel/failure preserves committed model and reports evidence |
| Open result | Results mode | Read-only | None | Result canvas and tables stay synchronized | Empty/invalidated result explains required next action |

## Overlay contract

- Dialogs own focus, trap keyboard navigation, restore focus on close, and close by explicit actions or supported dismissal.
- The unsaved-changes dialog names the pending destination and gives three explicit outcomes.
- Authentication and history dialogs do not replace or silently discard the current workspace.
- Snackbars acknowledge low-risk completed actions only. Validation, stale results, and solver failures remain persistent in their owning panel.

## Async, validation, permissions, and state

- Analysis and mesh actions expose busy state and cancellation where supported.
- Late analysis responses are ignored unless both workspace family and committed revision still match.
- Solver validation runs against the committed model only.
- Guest users can model, import, export, mesh, and solve. Saving and private history require authentication.
- Empty, loading, success, cancelled, failed, and result-invalidated states must preserve shell geometry.
- Every form control has a visible label, inline validation where applicable, and keyboard access. Icon-only actions have accessible names and tooltips.

## Verification contract

- Typecheck, unit/component tests, production build, strict frontend audit, and `git diff --check` must pass before handoff.
- Browser verification covers the 1120 px desktop floor, workspace persistence, Apply/Cancel, surface mesh read-only behavior, successful transition into Results mode, and guarded navigation with staged changes.
