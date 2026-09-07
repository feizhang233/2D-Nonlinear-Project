# Simplified UI redesign — 2026-09-06

## Direction

The user found the existing interface cluttered and requested a simpler, easier-to-use redesign.
The implementation replaces the command-heavy layout with a canvas-focused workbench. The
existing theme remains the runtime token owner; DESIGN.md and UX-CONTRACT.md record the new
visual and navigation decisions.

## Delivered

- A compact white header keeps Project, Model/Results, Save, Analysis, account and the primary
  Apply/Run action. A thin family/document row retains four independent workspaces.
- Project groups Open, Export, History, restart export, Math Core, Guide and example reset.
  Existing validation, account and unsaved-edit guards remain attached to those actions.
- The model navigator is a 232 px single-column list with one category expanded at a time.
  New precedes records; search appears for lists above eight records. Search clear is immediate,
  and the existing 60-record pagination and selected-record reachability remain available.
  Unused per-element description lookups were removed from list construction.
- Properties starts hidden and occupies no width while closed. Selected entities open a 320 px
  editor. The form stays mounted during hide/show, preserving incomplete scientific input.
  Model settings opens explicitly from the model-list header; blank-canvas selection closes the
  inspector without committing/discarding a draft.
- The canvas toolbar contains Select, Node/Vertex, Member/Hole, Support and Load. Sections stay
  in the model list; splitting stays with the selected member. Drawing does not open Properties
  between endpoint clicks, so the available drawing area stays stable.
- Fields use white outlined controls. Long descriptions, element details and member splitting
  are disclosed on demand. Quiet green accents, fine dividers, faint major grid lines and a flat
  bottom-right camera toolbar replace the heavy filled controls, card grid and floating banners.
- Successful analyses foreground a full-width result canvas. Results & tables opens a 460 px
  evidence panel. Running/failed solves reveal evidence automatically. Hiding the panel keeps
  the selected result quantity, step, member and tab. Monitor statistics use simple label/value
  rows rather than cards.
- The primary button remains in one fixed position: Apply changes → Run analysis → running
  Cancel. A 34 px footer retains edit status and shows Cancel only when there is a draft.

## Verification

- Frontend: **99/99 tests passed**, including two new regressions for canvas creation with a
  hidden inspector and preservation of unfinished scientific input across hide/show.
- TypeScript and production build passed. Changed standalone UI components were formatted.
- Strict UI audit: **0 findings**. DESIGN.md lint: **0 errors**, 9 token-reference warnings
  associated with the existing declarative component maps; runtime mapping is documented.
- Whitespace/diff check passed. Changed controls reuse MUI buttons, menus, selects, accordions,
  dialogs and the shared draft reducer; no native blocking confirmation was introduced.
- Real browser/API: Frame analysis succeeded, Moment diagram and station table displayed,
  successful completion hid details, and the user could reopen/hide evidence. Opening Analysis
  from Results returned to Model and displayed the existing settings dialog.
- Real browser: two empty canvas clicks created two endpoints and one member (3 nodes / 2
  members → 5 nodes / 3 members), with the inspector remaining hidden. Cancel restored the model.
- Real browser: `-2.5e` stayed intact after closing/reopening Properties; Apply remained disabled.
  Cancel restored committed input. Project menu and Guide remained accessible.
- Real browser: Continuum generated a Gmsh mesh with **15 nodes / 8 Q4 elements**. Its node list
  exposed search, showed a no-match state, cleared immediately, and disabled direct node creation.
  Cancel restored the original topology. Plate and Shell canvases were also checked.
- Layout: 1280 px normal view, 1120×800 desktop floor, and 900×740 narrow view were inspected.
  At 1120 px, the opened node popup measured 142 px against its 141.5 px trigger. At 900 px,
  the workspace retained its 1120 px horizontal scroller and the Analysis dialog fit from x=150
  to x=750. Temporary viewport overrides were reset.
- Existing component tests also cover failed imports, asynchronous cancellation, keyboard/IME
  guards, draft navigation, result invalidation, and generated-mesh read-only behavior.

## Design reconciliation

| Earlier treatment | New user-approved treatment | Owner |
| --- | --- | --- |
| Three broad tool bands and duplicated utilities | Compact action header; canvas-local drawing tools | App / ModelTools |
| Two-column category buttons | Expandable single-column model list | ModelNavigator |
| Always-open inspector plus restore rail | On-demand inspector with no closed width | App |
| Filled blue controls and dot grid | White outlined fields, muted green accents, faint major lines | theme / ModelCanvas |
| Always-visible result evidence | Full result canvas with optional evidence panel | ResultsWorkspace |
| Permanent derived fields and split form | Contextual disclosures | PropertyPanel / SplitElementPanel |

The supported interface remains desktop-first with a 1120 px floor. This UI change retains the
existing Frame recovery boundary: last accepted state, with reference-axis distributed-load
correction approximate at large rotation. No new solver behavior is implied by the visual redesign.

Local preview: http://127.0.0.1:5173/.
