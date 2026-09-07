# Frame interaction and result diagrams — 2026-09-06

## Delivered behavior

1. **Moment / shear / axial diagrams.** Frame Results offers Moment M, Shear V, and
   Axial N as filled, consistently scaled section-force diagrams. Selecting a member shows
   its end values and absolute peak; all-member paragraphs no longer overlap the drawing.
   Result tables provides x, N, V, and M stations. Diagram and table share member selection.
2. **Click-to-create geometry.** Node / New nodes enters point placement. Member / New
   elements accepts two empty points, existing nodes, or both, creates missing endpoints,
   and previews the pending member. A 10 px snap tolerance reuses existing nodes. Duplicate
   and zero-length members are rejected. All Geometry/explorer/command-band entry points
   follow the same canvas workflow. Escape exits the tool; Cancel restores the committed model.
3. **Scientific load input.** Nodal, member, edge and surface component fields accept
   decimal or e/E notation. `-2.5e` remains visible as an invalid draft; `-2.5e4` commits
   -25000. Empty, overflow and non-finite inputs block Apply and Apply-and-continue.
   Nodal moments carry N·m units. Invalid intermediate input never silently becomes zero.
4. **Separate analysis setup.** Properties belongs to the selected model entity.
   Analysis settings opens a bounded dialog from the command band. Loading strategy is
   visible first; Newton and step options use collapsed disclosures. Closing the dialog
   preserves staged options, and global Apply/Cancel commits or restores them.
5. **One primary action position.** The fixed-width header action is Apply changes for a
   draft, Run analysis for a committed model, and Cancel while running. The footer owns
   draft status and Cancel only. Ctrl/Command+Enter follows the same state outside forms
   and overlays. Apply commits first; running is a separate subsequent action.

## Recovery conventions and boundaries

`frameDiagrams.ts` consumes backend `element_response.local_end_forces` from the last accepted
state. x follows member i to j, N is positive in tension, V = dM/dx, and section end moments
are M(0) = -Mi and M(L) = Mj after member-load correction. Uniform and linearly varying
member loads are integrated along the member, including exact interior bending extrema.
Nodal loads are not subtracted as member-load vectors. All load patterns follow the backend
load-factor multiplier, including their individual scale.

Nodal-only diagrams use the recovered current member length. Distributed-load correction
uses reference local axes and reference length; it is approximate for large rotations.
That limitation is displayed beside both the diagram and station table. Earlier result steps
show a notice and a return-to-last-accepted-step action instead of displaying final-state
forces as earlier-step evidence. Missing recovery produces an explicit empty state.

The section-force station approach was checked against the official
[CALFEM beam2s reference](https://calfem-for-python.readthedocs.io/en/latest/calfem_reference/),
which documents N/V/M station recovery and local distributed loading. The nonlinear
corotational/reference-load boundary remains specific to this solver and is not an assertion
that the linear CALFEM recovery is exact under arbitrary finite rotation.

Project archives and their OpenAPI schema accept moment, shear and axial views. The legacy
Frame internal view maps to Moment. No solver-core constitutive or equilibrium algorithm changed.

## Verification

- Frontend: **97 tests passed**, TypeScript and production build passed.
- Backend: **212 tests passed**, including project archive view validation and persisted
  model/result round trips. Ruff passed after formatting the expanded result-view enum.
- Strict UI audit: **0 findings**. DESIGN.md lint: **0 errors**, 9 existing token-reference
  warnings; runtime token ownership remains documented in DESIGN.md.
- Release schema/evidence check and whitespace check passed.
- Numerical regressions: cantilever tip-force signs and constant shear; simply supported
  uniform-load parabola; triangular-load exact extremum; unavailable recovery.
- Live API check: 2 m simply supported beam under q = -3 N/m solved successfully. Corrected
  end moments were 0, midspan M = 1.5 N·m, end shears +3 / -3 N, agreeing with equilibrium.
- Browser: actual backend solve succeeded; Moment/Shear views and earlier-step guard checked;
  table-member selection and canvas selection synchronized; numerical cells keep exponents
  on one line. Scientific incomplete/complete input and button transition checked.
- Browser creation: two empty clicks changed 3 nodes / 2 members to 5 nodes / 3 members;
  one node click created a fourth node; Cancel restored both test drafts.
- Analysis dialog checked at 1120×800 and 900×740. At 900 px the 1120 px desktop workspace
  remains horizontally accessible; the 600 px dialog fits within the viewport.
- Local API restarted with the current schema. API and frontend-proxy health both returned
  ok; live OpenAPI matches the checked-in schema. Frontend: http://127.0.0.1:5173/.

This follow-up remains in the local working tree with the preceding workbench redesign;
no new GitHub push or public-site deployment was performed for this follow-up.
