# Nonlinear Studio UX Contract

## Product context

Nonlinear Studio is a desktop-first structural analysis workbench for engineers who define a finite-element model, run a bounded nonlinear solve, and review numerical evidence. The current owned interface is English-only and supports four independent model families: Frame, Continuum, Plate, and Shell.

The repository's model schemas, solver contracts, existing sample models, and P1-P16 verification evidence are the product's authoritative business sources. `Step 2 Math Core/INTERFACE.md` is the authoritative contract for Math Core identifiers, operations, signs, state boundaries, and error envelopes. The interface must expose solver state precisely and must not imply that an uncommitted edit or stale result is current.

## Visual contract

- Use the MUI theme with a compact white header, muted green actions, and a quiet drawing surface.
- Preserve desktop model/result workflows and the 1120 px minimum application width.
- Use color only with a textual, numeric, icon, line-style, or table equivalent.
- Keep modeling and result evidence literal; avoid decorative dashboard cards or marketing visual language.

## Canonical application map

```text
Application shell
├── Project menu / Save / Analysis / Account / Apply–Run
├── Math Core reference-tool dialog
├── Mode: Model | Results
├── Workspace bar: Frame | Continuum | Plate | Shell
├── Model mode
│   ├── Canvas-local Draw / Support / Load toolbar
│   ├── Expandable model list → central canvas → on-demand Properties
│   ├── Model editing canvas
│   ├── Analysis settings dialog
│   └── Draft status / Cancel strip (Apply shares the header Run slot)
└── Results mode
    ├── Read-only result canvas
    └── Expandable Results & tables evidence panel
```

## Workspace and navigation contract

- Frame, Continuum, Plate, and Shell are independent workspaces. Each preserves its own committed model, staged model, selection, form state, analysis options, result, and result view.
- The workspace bar is the only model-family navigation owner.
- Model and Results are separate top-level modes. A successful solve enters Results mode for the active workspace. Results mode never exposes model mutation controls.
- Results is unavailable until the active workspace has result evidence. Returning to Model does not delete the result.
- Switching workspaces with staged changes must open the app-owned unsaved-changes dialog. The user may keep editing, discard and continue, or apply and continue.

## Edit transaction contract

- Model and analysis-option edits are staged immediately in the visible controls but do not mutate the committed model.
- A persistent strip states that changes are unapplied and owns `Cancel`. The header action stays in one position and switches between `Apply changes`, `Run analysis`, and running `Cancel`.
- `Apply changes` commits the staged model as one revision and invalidates older result evidence.
- `Cancel` restores the committed model and committed analysis options.
- Run, Save, Export, and Results navigation are unavailable while staged changes exist.
- Closing or reloading the browser with staged changes invokes the platform's leave-page warning.
- Import, example reset, history open, and workspace changes use the same unsaved-changes guard.

## Math Core utility contract

- Math Core is a Project-menu utility and does not add a model family, workflow step, or result mode.
- The server-owned catalog is the canonical source for core names, operations, parameter requirements, executable examples, residual convention, state protocol, evidence meaning, and limitations.
- Selecting a core or operation resets only the dialog's transient request/result state. It never changes the active workspace or staged model.
- Execution is pessimistic and duplicate submission is blocked. Closing the dialog aborts the browser request and discards only transient Math Core input/output.
- Interface-level operation failures keep the `MathCoreResponse` envelope and appear inline. Catalog/transport failures stay persistent in the dialog with an explicit retry path.
- Math Core is unavailable while the active nonlinear analysis is running so reference work cannot contend with the canonical solve.

## Model tree, forms, and canvas

- The model tree and right form inspector are the primary entry points for selecting and editing model entities. Selecting an entity or workflow step restores a collapsed inspector.
- The canvas supports graphical model editing such as adding or moving editable Frame geometry, placing supports and loads, and sketching surface-family geometry.
- For Continuum, Plate, and Shell, generated mesh nodes and elements are visible and selectable for inspection by default, but cannot be directly added, moved, renamed, rewired, or deleted.
- Surface topology changes originate from Geometry and Mesh and return a newly generated staged mesh.
- Frame nodes and elements remain directly editable because their topology is the authored structural model.

## Flow ledger

| Trigger | Entry point | Staged state | Commit | Success | Failure or recovery |
| --- | --- | --- | --- | --- | --- |
| Edit entity | Tree/form/canvas | Draft model | Apply changes | Revision increments; result becomes invalidated | Cancel restores committed values |
| Change analysis option | Independent Analysis settings dialog | Draft run options | Apply changes | Options become solver input | Cancel restores committed options |
| Switch workspace | Workspace bar | Unsaved dialog when needed | Apply or discard | Target workspace restores its local state | Keep editing leaves current workspace unchanged |
| Generate surface mesh | Mesh form | Busy, then staged model | Apply changes | New Q4 mesh is committed | Error remains in current form; old committed mesh survives |
| Run analysis | Top app bar | Queued/running progress | Server-committed accepted states | Enters Results mode with current evidence | Cancel/failure preserves committed model and reports evidence |
| Run Math Core operation | Project menu → Math Core dialog | Transient JSON request | None | Stable response envelope remains in the dialog | Field error, operation error envelope, or transport retry stays in the dialog |
| Open result | Results mode | Read-only | None | Result canvas and tables stay synchronized | Empty/invalidated result explains required next action |

## Overlay contract

- Dialogs own focus, trap keyboard navigation, restore focus on close, and close by explicit actions or supported dismissal.
- The unsaved-changes dialog names the pending destination and gives three explicit outcomes.
- Authentication and history dialogs do not replace or silently discard the current workspace.
- Snackbars acknowledge low-risk completed actions only. Validation, stale results, and solver failures remain persistent in their owning panel.

## Async, validation, permissions, and state

- Analysis and mesh actions expose busy state and cancellation where supported.
- Late analysis responses are ignored unless the request is current, the revision matches, and the job is still running. Completion in an inactive family cannot switch the visible mode.
- Cancellation during validation prevents submission. Cancellation during submission retains the POST acknowledgement and cancels the resulting job. Once an ID exists, failed cancellation stays actionable and polling continues until the server confirms termination. A terminal cancelled record retains accepted evidence.
- Completed poll delays remove their abort listener. Requests time out after 30 seconds (mesh generation: 120 seconds), report uncertain completion explicitly, and are never automatically resubmitted.
- Imports pass the backend model schema before replacing the workspace. Schema paths, execution-limit errors, malformed response bodies, and transport failures appear as meaningful errors. Mesh errors remain in the inspector.
- Ctrl/Command + Enter is ignored in inputs, IME composition, menus, and dialogs; mesh busy state also blocks shortcut submission.
- Backend SPA fallback contains static paths within the frontend build and returns 404 for unknown API routes or missing assets.
- Solver validation runs against the committed model only.
- Guest users can model, open/download model and result project files, mesh, and solve. Saving snapshots to an account and private history require authentication.
- Empty, loading, success, cancelled, failed, and result-invalidated states must preserve shell geometry.
- Every form control has a visible label, inline validation where applicable, and keyboard access. Icon-only actions have accessible names and tooltips.

## Verification contract

- Typecheck, unit/component tests, production build, strict frontend audit, and `git diff --check` must pass before handoff.
- Browser verification covers the 1120 px desktop floor, workspace persistence, Apply/Cancel, surface mesh read-only behavior, successful transition into Results mode, and guarded navigation with staged changes.

## Canonical UI ownership

| Capability | Canonical owner | Source of truth | Variants | Verification |
| --- | --- | --- | --- | --- |
| Select/Listbox | MUI TextField select / Menu | DESIGN.md | Authored | Browser popup + keyboard |
| Form | PropertyPanel, GeometryPanel, AnalysisSettingsDialog/AnalysisPanel, ScientificField | Backend schemas; state reducer | Staged model/options | App and API tests |
| Scrollbar | theme.ts CssBaseline | DESIGN.md | Internal vertical; document horizontal | Browser 1120 px and narrow viewport |
| Toast | App Snackbar / Alert | UX contract | success, info, warning, error | Component tests |
| CRUD | useModelHistory / api.ts | IAM schemas | Private snapshots | Component and backend tests |
| Direct manipulation | ModelCanvas + canvasViewport | Geometry contract | Frame, sketch, read-only results | Canvas regression + browser drag |

Canvas state is transient, not encoded in the URL. Workspace model/result state remains in the
reducer. Zoom and pan never create drafts; model dragging commits once on pointer release.
Cancelled drags do not mutate the model. Document horizontal scrolling preserves the established
desktop support floor on smaller screens.

## September 6 operation redesign

The user explicitly authorized replacing the previous functional-area design. ModelTools owns
drawing/placement actions; the header owns Analysis; ModelNavigator owns category selection, New, local search,
Show more, and Delete selected. It does not collapse the inspector on double-click. Search is
transient per category and resets on category/document changes; clearing it is immediate.

`sections.ts` owns section definitions/defaults/assignment and materializes A/I or thickness into
element properties. `nonlinear_core/sections.py` validates the same reserved extension at the
model boundary. Shape changes preserve section ID and update all assigned members. Unassigned
legacy properties remain authoritative until explicitly assigned. Surface remeshing assigns the
chosen default to all newly generated elements; this replaces previous per-element assignments.

`modelOperations.ts` owns removal and splitting. Delete/Backspace is ignored in fields, IME,
menus, dialogs, Results and busy operations. Cancel restores every staged deletion. Connected
nodes and referenced materials/sections cannot be removed until their references are resolved.
Deleting a Frame member also removes its attached member loads. Frame splitting accepts unique
internal positions, inherits material/section, interpolates endpoint load intensities and retains
load pattern/scale. It never silently splits a Q4 or accepts endpoint/duplicate cuts.

Invalid Section or non-finite numeric drafts block Apply and Apply-and-continue, while Cancel/Discard remain enabled.
Selecting or inspecting does not create a draft. MUI fields, dialogs, Snackbar/Alert and the
existing draft reducer remain canonical owners for their behavior.

`projectFiles.ts`, `SaveProjectDialog`, the archive reducer action and the API archive schemas own
portable persistence. Project JSON includes the committed model, sections, run options, optional
completed analysis, selected step and result presentation. Results must match the exact model
fingerprint. Queued/running jobs cannot be restored as finished results. Server-side snapshots
store the archive in an additive SQLite column and retain existing user isolation and 24-snapshot
retention. Model-only snapshots and legacy model/restart files remain compatible. Archive requests
are bounded to 20 MB; solve/model-validation byte limits remain unchanged. Failed saves preserve
current model/results and expose persistent dialog feedback. Imports cannot overwrite newer edits.

| Capability | Owner | Verification |
| --- | --- | --- |
| Section CRUD and assignment | SectionPanel + sections.ts + core sections validator | section unit tests; API consistency tests; browser assignment |
| Delete / split | ModelTools / ModelNavigator / modelOperations.ts | keyboard component tests, resultant-preserving split test, browser |
| Project persistence | projectFiles + archive schemas + IdentityStore | mismatch rejection, database restart test, browser file round trip |

## Frame workflow follow-up

- New nodes/elements in every entry point select a canvas tool. Empty clicks create nodes; two
  endpoint clicks create a member with a live preview and 10 px snapping. Existing nodes may be
  reused. Missing materials, zero-length and duplicate members cannot create invalid topology.
- Analysis settings edits the current workspace run options in a separate dialog. Returning to
  the model preserves those drafts; Apply and Cancel use the same transaction as property edits.
- Load component fields preserve raw e/E exponent input. Incomplete/overflowing numbers show an
  inline error and block all Apply paths; they never silently become zero or JSON null.
- Moment/Shear/Axial diagrams and the station table share recovered end actions and member
  selection. All-member text is suppressed; only selected ends/peak are annotated. Earlier steps
  cannot display final-state diagrams. Missing recovery is explicit. Distributed-load correction
  uses reference axes, and large-rotation approximation is disclosed beside the evidence.
- New result views are accepted by the backend project archive schema and survive save/reopen.

| Capability | Owner | Verification |
| --- | --- | --- |
| Primary action | App header + draft reducer | Same DOM button through Apply/Run; invalid-number gate |
| Analysis settings | AnalysisSettingsDialog + AnalysisPanel | Dialog return preserves draft options; browser 1120 px |
| Scientific load input | ScientificField + inputValidation | Partial exponent, finite completion, overflow; live browser |
| Canvas creation | ModelNavigator / ModelTools / GeometryPanel → ModelCanvas | Two-point/snap regression and browser clicks; Cancel |
| Frame diagrams | frameDiagrams + FrameDiagramLayer + FrameSectionTable | Cantilever, uniform and triangular load recovery; selected-step guard; browser table selection |

## Simplified UI — latest user direction

The user explicitly requested a simpler redesign after finding the previous interface cluttered.
The revised DESIGN.md and theme replace the old command-band/category-card layout. ModelNavigator
owns single-column expandable categories; at most one category is expanded. Closing a category
closes its Properties view; model settings remains an explicit separate action. Small lists expose
records directly; lists above eight records offer search with immediate clear and retained paging.
New record selection opens its editor. Canvas point creation preserves the open/closed inspector
state to keep its viewport stable between clicks. Selection and all data still live in StudioState.

Properties is initially hidden and can occupy zero width; its mounted editor preserves intermediate
numeric text during hide/show. Explicit selection reopens it. Clicking blank canvas closes it without
committing/discarding a draft. The fixed primary Apply/Run/Cancel button and existing navigation
transaction guards are unchanged. Generated topology remains inspectable and read-only.

Results & tables is a reversible evidence-panel disclosure. Running/failed states open it; successful
completion closes it to foreground the result canvas. Opening/hiding the panel preserves the chosen
result view, step, member and tab. Data is never discarded by a layout action. Hidden panels are not
keyboard-focusable. Analysis from Results returns to Model and opens the existing settings dialog.

Project consolidates low-frequency file/history/reference/help actions in a MUI menu. Existing auth,
unsaved-edit guards, import validation and async state ownership remain authoritative. Units,
formulation and member splitting remain accessible through contextual disclosures rather than
repeated permanent toolbars or information cards.

## CAD and first-click loads (2026-09-07)

- All Load creation entry points share placement; no record exists before the first eligible click.
  Auto chooses point vs line by node vs element. Explicit modes reject incompatible targets.
- Point placement accepts every actual mesh node. Boundary line placement uses the clicked cell's
  nearest exposed edge and binds its entire CAD boundary when a generated mesh is available.
  Interior cells cannot silently apply a line load elsewhere. Changing or relocating a load waits
  for a new click and preserves existing intensity when the type is unchanged.
- New outlines have a visible polyline preview, exact X/Y entry, Shift alignment, undo, close and
  cancel. Replacement clears the previous holes and boundary conditions, as stated in the tool.
  Model Cancel restores the complete previous domain. Apply/Run waits for drawing to finish.
- Hole creation first asks for Circle/Rectangle/Square and only the relevant dimensions, then uses
  the next canvas click as its center. Selected holes expose center and dimension editing through
  Update hole / Reset dimensions. Circle metadata survives project serialization and remeshing.
- Reject crossed/zero-area outlines, nonpositive dimensions, and holes outside, touching or
  overlapping the domain or each other. Server validation precedes native meshing too.
- Geometry changes invalidate the mesh. Pending geometry hides old FE topology. Meshing keeps
  material/section definitions, uses true circle arcs, removes construction-only nodes and binds
  boundary segments using CAD curve membership rather than geometric nearest-edge guessing.
- The owned UI remains English; Gmsh boundary labels now use the same language.
