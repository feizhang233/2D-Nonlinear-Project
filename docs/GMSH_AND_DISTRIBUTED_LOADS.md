# Gmsh and distributed-load contract

## Mesh generation

`POST /api/v1/meshes` accepts the current versioned `ModelInput` and a positive target mesh size.
It is available for Continuum, Plate, and Shell models. The service:

1. extracts the single exterior loop from the current Q4 element topology;
2. collapses collinear nodes left by an earlier structured mesh;
3. generates a first-order surface mesh with Gmsh recombination enabled;
4. rejects any result containing non-Q4 surface cells; and
5. returns ordered boundary segments with owning element IDs and zero-based local-edge indices.

Four-corner domains use transfinite curves and a transfinite surface, which gives a structured Q4
mesh. More general polygons are accepted only if Gmsh recombination still produces an all-Q4
result. The interactive service limit is 10,000 nodes. The current bridge does not support holes,
multiple exterior loops, branched boundaries, or a non-XY flat Shell.

The mesh endpoint does not solve a model. The frontend applies the returned nodes/elements,
geometrically rebinds supported constraints and loads, increments the model revision, invalidates
old results, and stores the Gmsh boundary metadata with the model.

The frontend owns mesh as a first-class left-navigator item. Its target-size input accepts any
finite value greater than zero; values such as `0.5 m` are example defaults, not lower bounds.

## Consistent distributed loads

All distributed loads are proportional reference loads. Their assembled vector is multiplied by
the nonlinear load factor. They are not pressure follower loads and do not contribute an external
tangent.

- Frame member load: linearly varying `qx_i`, `qy_i`, `qx_j`, `qy_j` in N/m, integrated with the
  two-node Euler-Bernoulli consistent load vector in the reference member's local axes and then
  transformed to global DOFs. A uniform UI edit writes equal end values.
- Continuum edge load: fixed-global `UX`/`UY` line load in N/m. Each straight Q4 edge contributes
  `q L / 2` to each endpoint.
- Plate surface load: fixed-global `UZ` pressure in N/m2, integrated by the existing Q4 surface
  load routine. Plate edge load uses fixed-global `UZ` in N/m.
- Shell surface/edge load: fixed-global `UX`/`UY`/`UZ` traction in N/m2 or N/m, integrated by the
  Shell core's Q4 surface/edge routines.

A Gmsh boundary load stores `extensions.boundary_id` plus `extensions.edge_segments`. Each segment
contains `element_id`, zero-based `local_edge`, and its two node IDs. This avoids treating a long
geometric boundary as one element edge and keeps total load proportional to the generated boundary
length.
