"""Target-code regressions for the index's V00–V18 and integration boundaries.

Oracles are beam closed solutions, independent B/energy/virtual-work integrals,
rigid-body transformations and the existing 2D implementation, not the source
package's precomputed pass flags or its reference kernel.
"""

from dataclasses import replace

import numpy as np
import pytest
from numpy.testing import assert_allclose as close

import reused_cores.frame3d_linear as f

E, G, A, IY, IZ, J, L = 200e9, 80e9, 0.01, 8e-6, 5e-6, 1e-5, 2.0
ELEMENT = f.FrameElement(1, 1, 2, E, G, A, IY, IZ, J, (0, 1, 0))
NODES = [f.Node(1, 0, 0, 0), f.Node(2, L, 0, 0)]
FIXED = f.Support(1, True, True, True, True, True, True)


def cantilever(*, element=ELEMENT, nodes=NODES, nodal=(), line=(), **kwargs):
    result = f.solve_frame(nodes, [element], [FIXED], nodal, line, **kwargs)
    assert result.validation.passed, result.validation
    assert all(e.validation.passed for e in result.elements)
    return result


def rotation():
    axis = np.array([1.0, 2.0, 3.0]) / np.sqrt(14)
    x, y, z = axis
    skew = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    return np.eye(3) + np.sin(0.73) * skew + (1 - np.cos(0.73)) * (skew @ skew)


def test_v00_basis():
    e = replace(ELEMENT, reference_vector=(0, 0, 1))
    geom = f.calculate_geometry(e, NODES[0], f.Node(2, 1, 2, 2))
    assert geom.L == 3
    close(geom.Q[0], [1 / 3, 2 / 3, 2 / 3])
    close(geom.Q[1], [-2 / (3 * np.sqrt(5)), -4 / (3 * np.sqrt(5)), np.sqrt(5) / 3])
    close(geom.Q @ geom.Q.T, np.eye(3), atol=1e-15)
    assert np.linalg.det(geom.Q) == pytest.approx(1)
    for magnitude in (1e-200, 1e200):
        scaled = replace(e, reference_vector=(0, 0, magnitude))
        close(f.calculate_geometry(scaled, NODES[0], f.Node(2, 1, 2, 2)).Q, geom.Q)


@pytest.mark.parametrize(
    "end,reference", [((0, 0, 0), (0, 1, 0)), ((2, 0, 0), (1, 0, 0)), ((2, 0, 0), (1, 1e-12, 0))]
)
def test_v00_degenerate_geometry(end, reference):
    with pytest.raises(ValueError):
        f.calculate_geometry(
            replace(ELEMENT, reference_vector=reference), NODES[0], f.Node(2, *end)
        )


def test_v01_independent_strain_displacement_integral():
    integrated = np.zeros((12, 12))
    points, weights = np.polynomial.legendre.leggauss(2)
    for point, weight in zip(points, weights, strict=True):
        t = (point + 1) / 2
        b = np.zeros((4, 12))
        b[0, [0, 6]] = [-1 / L, 1 / L]
        b[1, [3, 9]] = [-1 / L, 1 / L]
        h2 = np.array(
            [(-6 + 12 * t) / L**2, (-4 + 6 * t) / L, (6 - 12 * t) / L**2, (-2 + 6 * t) / L]
        )
        b[2, [1, 5, 7, 11]] = h2
        b[3, [2, 4, 8, 10]] = h2 * [1, -1, 1, -1]
        integrated += b.T @ np.diag([E * A, G * J, E * IZ, E * IY]) @ b * weight * L / 2
    actual = f.calculate_local_stiffness(ELEMENT, L)
    close(actual, integrated, rtol=1e-12, atol=1e-6)
    assert actual[1, 5] == pytest.approx(1.5e6)
    assert actual[2, 4] == pytest.approx(-2.4e6)


@pytest.mark.parametrize("theory", ["euler_bernoulli", "timoshenko"])
def test_v02_six_rigid_modes_and_scaled_rank(theory):
    e = replace(ELEMENT, theory=theory, Asy=0.008, Asz=0.008)
    k = f.calculate_local_stiffness(e, L)
    close(k, k.T)
    for axis in np.eye(3):
        translation = np.r_[axis, [0, 0, 0], axis, [0, 0, 0]]
        rigid_rotation = np.r_[[0, 0, 0], axis, np.cross(axis, [L, 0, 0]), axis]
        close(k @ translation, 0, atol=1e-6)
        close(k @ rigid_rotation, 0, atol=1e-6)
    scale = np.tile([L, L, L, 1, 1, 1], 2)
    eig = np.linalg.eigvalsh(k * np.outer(scale, scale))
    assert np.count_nonzero(abs(eig) < eig[-1] * 1e-9) == 6
    assert np.count_nonzero(eig > eig[-1] * 1e-9) == 6


@pytest.mark.parametrize(
    "force,dofs,expected,energy",
    [
        ({"fx": 10000}, [0], [1e-5], 0.05),
        ({"mx": 2000}, [3], [0.005], 5),
        ({"fy": 1000}, [1, 5], [1000 * L**3 / (3 * E * IZ), 1000 * L**2 / (2 * E * IZ)], 4 / 3),
        ({"fz": 1000}, [2, 4], [1000 * L**3 / (3 * E * IY), -1000 * L**2 / (2 * E * IY)], 5 / 6),
    ],
)
def test_v03_to_v06_cantilever(force, dofs, expected, energy):
    load = f.NodalLoad(2, **force)
    r = cantilever(nodal=[load])
    close(r.nodal_displacements[1, dofs], expected, rtol=1e-12)
    close(r.reactions[:3], -load.vector[:3], atol=1e-8)
    close(r.reactions[3:6], -load.vector[3:] - np.cross([L, 0, 0], load.vector[:3]), atol=1e-8)
    assert r.validation.strain_energy == pytest.approx(energy)


def test_v07_pure_bending_and_normal_stress():
    r = cantilever(nodal=[f.NodalLoad(2, mz=1000)], section_points=[f.SectionPoint(0.05, 0)])
    fields = r.elements[0].fields
    close(fields.transverse_displacement_y, 0.001 * fields.x_local**2 / 2, atol=1e-15)
    close(fields.rotation_z, 0.001 * fields.x_local, atol=1e-15)
    close(fields.normal_stress, -1e7)
    assert r.validation.strain_energy == pytest.approx(1)
    assert f.calculate_normal_stress(ELEMENT, 10000, 2000, 3000, 0.04, -0.02) == pytest.approx(
        10000 / A + 2000 * (-0.02) / IY - 3000 * 0.04 / IZ
    )


def test_v08_uniform_load_and_particular_solution():
    load = f.DistributedLoad(1, qy_i=1000, qy_j=1000)
    eq = f.calculate_local_equivalent_nodal_load(ELEMENT, load, L)
    close(eq[[1, 5, 7, 11]], [1000, 1000 / 3, 1000, -1000 / 3])
    r = cantilever(line=[load], number_of_points=3)
    close(r.nodal_displacements[1, [1, 5]], [0.002, 0.004 / 3])
    close(r.elements[0].local_end_forces[6:], 0, atol=1e-8)
    assert r.elements[0].fields.bending_moment_z[1] == pytest.approx(500)
    assert r.elements[0].fields.transverse_displacement_y[1] == pytest.approx(
        17 * 1000 * L**4 / (384 * E * IZ)
    )
    # Exact integrated energy includes the load bubble, not merely 1/2 d.T K d.
    assert r.validation.strain_energy == pytest.approx(1000**2 * L**5 / (40 * E * IZ))


@pytest.mark.parametrize("component", ["qx", "qy", "qz", "mx"])
def test_uniform_and_triangular_fields_against_virtual_work(component):
    for qi, qj in [(1000, 1000), (0, 1000), (700, -300)]:
        load = f.DistributedLoad(1, **{component + "_i": qi, component + "_j": qj})
        r = cantilever(line=[load], number_of_points=9)
        fields = r.elements[0].fields
        name, rigidity = {
            "qx": ("axial_displacement", E * A),
            "qy": ("transverse_displacement_y", E * IZ),
            "qz": ("transverse_displacement_z", E * IY),
            "mx": ("rotation_x", G * J),
        }[component]
        gp, gw = np.polynomial.legendre.leggauss(4)
        expected = []
        for x in fields.x_local:
            total = 0
            for lo, hi in [(0, x), (x, L)]:
                a = lo + (gp + 1) * (hi - lo) / 2
                mn, mx = np.minimum(a, x), np.maximum(a, x)
                green = mn if component in ("qx", "mx") else mn**2 * (3 * mx - mn) / 6
                total += np.dot(gw, (qi + (qj - qi) * a / L) * green) * (hi - lo) / (2 * rigidity)
            expected.append(total)
        close(getattr(fields, name), expected, rtol=1e-10, atol=1e-13)


def test_fixed_fixed_load_has_nonzero_internal_displacement_and_energy():
    r = f.solve_frame(
        NODES,
        [ELEMENT],
        [FIXED, replace(FIXED, node_id=2)],
        distributed_loads=[f.DistributedLoad(1, qy_i=1000, qy_j=1000)],
        number_of_points=3,
    )
    close(r.displacements, 0)
    assert r.elements[0].fields.transverse_displacement_y[1] == pytest.approx(
        1000 * L**4 / (384 * E * IZ)
    )
    assert r.validation.strain_energy > 0
    assert r.validation.passed


def test_v09_support_settlement_and_duplicate_records():
    nodes = [f.Node(i + 1, i, 0, 0) for i in range(3)]
    elements = [ELEMENT, replace(ELEMENT, id=2, node_i=2, node_j=3)]
    supports = [
        FIXED,
        f.Support(2, v=True, w=True, rx=True, ry=True, rz=True),
        replace(FIXED, node_id=3, u_value=0.002),
        f.Support(1, u=True),
    ]
    r = f.solve_frame(nodes, elements, supports)
    close(r.nodal_displacements[:, 0], [0, 0.001, 0.002])
    close(r.reactions[[0, 12]], [-2e6, 2e6])
    assert r.validation.passed
    with pytest.raises(ValueError, match="conflicting"):
        f.solve_frame(nodes, elements, supports + [f.Support(1, u=True, u_value=0.001)])


def test_v10_rotation_covariance_with_mixed_loading():
    h = rotation()
    nodes = [NODES[0], f.Node(2, 1, 2, 2)]
    e = replace(ELEMENT, reference_vector=(0, 0, 1))
    q = f.calculate_geometry(e, *nodes).Q
    force = q.T @ np.array([200, 1000, 300])
    moment = q.T @ np.array([400, 300, -200])
    line = [f.DistributedLoad(1, qx_i=20, qy_i=30, qz_i=40, qy_j=-20, mx_i=10, mx_j=20)]
    nodal = f.NodalLoad(2, *force, *moment)
    r = cantilever(element=e, nodes=nodes, nodal=[nodal], line=line)
    rotated = cantilever(
        element=replace(e, reference_vector=tuple(h @ e.reference_vector)),
        nodes=[f.Node(n.id, *(h @ n.coordinates)) for n in nodes],
        nodal=[f.NodalLoad(2, *(h @ force), *(h @ moment))],
        line=line,
    )
    close(rotated.displacements.reshape(-1, 3), r.displacements.reshape(-1, 3) @ h.T, atol=1e-13)
    close(rotated.reactions.reshape(-1, 3), r.reactions.reshape(-1, 3) @ h.T, atol=1e-7)
    close(rotated.elements[0].local_end_forces, r.elements[0].local_end_forces, atol=1e-7)
    assert rotated.validation.strain_energy == pytest.approx(r.validation.strain_energy)


def test_global_distributed_forces_transform_before_integration():
    e = replace(ELEMENT, reference_vector=(0, 0, 1))
    nodes = [NODES[0], f.Node(2, 1, 2, 2)]
    q = f.calculate_geometry(e, *nodes).Q
    gi, gj = np.array([20, 30, -40]), np.array([50, -60, 70])
    li, lj = q @ gi, q @ gj
    global_load = f.DistributedLoad(1, *gi, 9, *gj, 11, coordinate_system="global")
    local_load = f.DistributedLoad(1, *li, 9, *lj, 11)
    a = cantilever(element=e, nodes=nodes, line=[global_load])
    b = cantilever(element=e, nodes=nodes, line=[local_load])
    close(a.displacements, b.displacements, atol=1e-14)


def test_v11_section_roll_changes_directional_compliance():
    old = cantilever(nodal=[f.NodalLoad(2, fy=1000)])
    new = cantilever(element=replace(ELEMENT, roll_angle=90), nodal=[f.NodalLoad(2, fy=1000)])
    assert new.nodal_displacements[1, 1] / old.nodal_displacements[1, 1] == pytest.approx(IZ / IY)


def test_v12_release_condenses_load_and_recovers_member_rotation():
    e = replace(ELEMENT, releases=(11,))
    load = f.DistributedLoad(1, qy_i=1000, qy_j=1000)
    c = f.condense_releases(
        f.calculate_local_stiffness(e, L),
        f.calculate_local_equivalent_nodal_load(e, load, L),
        e.releases,
    )
    close(c.load[[1, 5, 7]], [1250, 500, 750])
    r = f.solve_frame(
        NODES,
        [e],
        [FIXED, f.Support(2, u=True, v=True, w=True, rx=True, ry=True)],
        distributed_loads=[load],
    )
    close(r.reactions[[1, 5, 7]], [-1250, -500, -750])
    assert r.elements[0].local_displacements[11] == pytest.approx(-1 / 6000)
    assert abs(r.elements[0].local_end_forces[11]) < 1e-8
    assert r.displacements[11] == 0  # joint gauge differs from member rotation
    assert r.inactive_dof_vectors.shape == (1, 12)
    assert r.validation.passed


def test_rotated_released_joint_null_direction_and_loaded_inactive_error():
    h = rotation()
    e = replace(ELEMENT, releases=(11,), reference_vector=tuple(h @ np.array([0, 1, 0])))
    nodes = [f.Node(n.id, *(h @ n.coordinates)) for n in NODES]
    supports = [FIXED, f.Support(2, u=True, v=True, w=True)]
    r = f.solve_frame(
        nodes, [e], supports, distributed_loads=[f.DistributedLoad(1, qy_i=1000, qy_j=1000)]
    )
    assert r.validation.passed
    assert r.inactive_dof_vectors.shape == (1, 12)
    close(abs(r.inactive_dof_vectors[0, 9:] @ (h @ np.array([0, 0, 1]))), 1)
    with pytest.raises(ValueError, match="inactive"):
        f.solve_frame(nodes, [e], supports, [f.NodalLoad(2, mx=h[0, 2], my=h[1, 2], mz=h[2, 2])])


def test_both_end_bending_releases_simply_supported_beam():
    e = replace(ELEMENT, releases=(5, 11))
    r = f.solve_frame(
        NODES,
        [e],
        [replace(FIXED, rz=False), f.Support(2, v=True)],
        distributed_loads=[f.DistributedLoad(1, qy_i=1000, qy_j=1000)],
        number_of_points=3,
    )
    close(r.reactions[[1, 7]], [-1000, -1000])
    close(r.elements[0].local_end_forces[[5, 11]], 0, atol=1e-8)
    assert r.elements[0].fields.transverse_displacement_y[1] == pytest.approx(
        5 * 1000 * L**4 / (384 * E * IZ)
    )
    assert r.validation.passed


def test_singular_release_block_is_rejected():
    with pytest.raises(ValueError, match="release block"):
        cantilever(element=replace(ELEMENT, releases=(3, 9)))


@pytest.mark.parametrize("axis,inertia,rotation_dof,sign", [(1, IZ, 5, 1), (2, IY, 4, -1)])
def test_v13_timoshenko_both_planes_and_eb_limit(axis, inertia, rotation_dof, sign):
    e = replace(ELEMENT, theory="timoshenko", Asy=0.008, Asz=0.008)
    force = np.zeros(3)
    force[axis] = 1000
    r = cantilever(element=e, nodal=[f.NodalLoad(2, *force)])
    assert r.nodal_displacements[1, axis] == pytest.approx(
        1000 * L**3 / (3 * E * inertia) + 1000 * L / (G * 0.008)
    )
    assert r.nodal_displacements[1, rotation_dof] == pytest.approx(
        sign * 1000 * L**2 / (2 * E * inertia)
    )
    close(
        f.calculate_local_stiffness(replace(e, Asy=1e12, Asz=1e12), L),
        f.calculate_local_stiffness(ELEMENT, L),
        rtol=1e-12,
    )


@pytest.mark.parametrize("count", [1, 2, 4, 8])
def test_v14_inclined_member_assembly(count):
    end = np.array([1, 2, 2])
    nodes = [f.Node(i + 1, *(end * i / count)) for i in range(count + 1)]
    elements = [
        replace(ELEMENT, id=i + 1, node_i=i + 1, node_j=i + 2, reference_vector=(0, 0, 1))
        for i in range(count)
    ]
    q = f.calculate_geometry(elements[0], *nodes[:2]).Q
    r = f.solve_frame(
        nodes, elements, [FIXED], [f.NodalLoad(count + 1, *(q.T @ np.array([0, 1000, 0])))]
    )
    for i, d in enumerate(r.nodal_displacements):
        x = 3 * i / count
        close((q @ d[:3])[1], 1000 * x * x * (9 - x) / (6 * E * IZ), atol=1e-12)
    assert r.validation.passed
    close(r.reactions[6:], 0, atol=1e-6)


def test_v15_bent_space_frame_against_castigliano_energy():
    nodes = [NODES[0], NODES[1], f.Node(3, 2, 3, 0)]
    elements = [ELEMENT, replace(ELEMENT, id=2, node_i=2, node_j=3, reference_vector=(0, 0, 1))]
    r = f.solve_frame(nodes, elements, [FIXED], [f.NodalLoad(3, fz=1000)])
    # Independent member force distributions, integrated rather than element matrices.
    gp, gw = np.polynomial.legendre.leggauss(3)
    x, a = (gp + 1), (gp + 1) * 1.5
    energy = np.dot(gw, (1000 * (2 - x)) ** 2 / (2 * E * IY) + (3000) ** 2 / (2 * G * J))
    energy += np.dot(gw, (1000 * (3 - a)) ** 2 / (2 * E * IZ)) * 1.5
    assert r.nodal_displacements[2, 2] == pytest.approx(2 * energy / 1000)
    assert r.validation.strain_energy == pytest.approx(energy)
    close(r.reactions[:6], [0, 0, -1000, -3000, 2000, 0], atol=1e-7)
    assert r.validation.passed


@pytest.mark.parametrize("supports", [[], [f.Support(1, u=True, v=True, w=True)]])
@pytest.mark.parametrize("loaded", [False, True])
def test_v16_mechanisms_are_rejected_even_without_load(supports, loaded):
    with pytest.raises(ValueError, match="singular"):
        f.solve_frame(NODES, [ELEMENT], supports, [f.NodalLoad(2, fy=1000)] if loaded else [])


def test_v17_triangular_consistent_load_and_tip_response():
    load = f.DistributedLoad(1, qy_j=1000)
    eq = f.calculate_local_equivalent_nodal_load(ELEMENT, load, L)
    close(eq[[1, 5, 7, 11]], [300, 400 / 3, 700, -200])
    assert eq[1] + eq[7] == pytest.approx(1000)
    assert eq[5] + eq[11] + L * eq[7] == pytest.approx(4000 / 3)
    r = cantilever(line=[load])
    close(
        r.nodal_displacements[1, [1, 5]],
        [11 * 1000 * L**4 / (120 * E * IZ), 1000 * L**3 / (8 * E * IZ)],
    )


def test_v18_locking_diagnostic_and_closed_element_pure_bending_energy():
    curvature, shear_area = 0.001, 0.008
    gp, gw = np.polynomial.legendre.leggauss(3)
    x = (gp + 1) * L / 2
    bad_shear = 0.5 * G * shear_area * np.dot(gw, (curvature * (L / 2 - x)) ** 2) * L / 2
    good_bending = 0.5 * E * IZ * curvature**2 * L
    assert bad_shear == pytest.approx(213.3333333333333)
    assert good_bending == pytest.approx(1)
    d = np.zeros(12)
    d[[7, 11]] = [curvature * L**2 / 2, curvature * L]
    for area in (0.008, 8e3):
        k = f.calculate_local_stiffness(
            replace(ELEMENT, theory="timoshenko", Asy=area, Asz=area), L
        )
        assert 0.5 * d @ k @ d == pytest.approx(good_bending)


def test_inclined_support_with_prescribed_displacement():
    h = rotation()
    nodes = [f.Node(n.id, *(h @ n.coordinates)) for n in NODES]
    e = replace(ELEMENT, reference_vector=tuple(h @ np.array([0, 1, 0])))
    support = replace(FIXED, axes=tuple(map(tuple, h.T)), u_value=0.001)
    tip = f.Support(2, v=True, axes=tuple(map(tuple, h.T)))
    force = h @ np.array([1000, 0, 0])
    r = f.solve_frame(nodes, [e], [support, tip], [f.NodalLoad(2, *force)])
    close(h.T @ r.nodal_displacements[1, :3], [0.001 + 1000 * L / (E * A), 0, 0], atol=1e-13)
    assert r.validation.passed


def test_planar_frame_matches_existing_2d_solver():
    import frame2d as planar

    nodes2 = [planar.Node(1, 0, 0), planar.Node(2, 0, 3), planar.Node(3, 4, 3)]
    elements2 = [planar.FrameElement(1, 1, 2, E, A, IZ), planar.FrameElement(2, 2, 3, E, A, IZ)]
    supports2 = [planar.Support(1, True, True, True, u_value=0.0001, angle=20)]
    nodal2 = [planar.NodalLoad(3, fx=1200, fy=-1500, mz=500)]
    line2 = [planar.DistributedLoad(2, qx_i=50, qy_i=-500, qx_j=-70, qy_j=-1000)]
    a = planar.solve_frame(nodes2, elements2, supports2, nodal2, line2)
    nodes3 = [f.Node(n.id, n.x, n.y, 0) for n in nodes2]
    elements3 = [
        replace(ELEMENT, reference_vector=(-1, 0, 0)),
        replace(ELEMENT, id=2, node_i=2, node_j=3),
    ]
    angle = np.deg2rad(20)
    axes = ((np.cos(angle), np.sin(angle), 0), (-np.sin(angle), np.cos(angle), 0), (0, 0, 1))
    supports3 = [
        replace(FIXED, u_value=0.0001, axes=axes),
        f.Support(2, w=True, rx=True, ry=True),
        f.Support(3, w=True, rx=True, ry=True),
    ]
    b = f.solve_frame(
        nodes3,
        elements3,
        supports3,
        [f.NodalLoad(3, fx=1200, fy=-1500, mz=500)],
        [f.DistributedLoad(2, qx_i=50, qy_i=-500, qx_j=-70, qy_j=-1000)],
    )
    close(b.nodal_displacements[:, [0, 1, 5]], a.nodal_displacements, rtol=1e-10, atol=1e-12)
    close(b.reactions.reshape(-1, 6)[:, [0, 1, 5]], a.reactions.reshape(-1, 3), atol=1e-6)
    for x, y in zip(a.elements, b.elements, strict=True):
        close(y.local_end_forces[[0, 1, 5, 6, 7, 11]], x.local_end_forces, atol=1e-6)
        close(y.fields.bending_moment_z, x.fields.bending_moment, atol=1e-6)
        close(y.fields.shear_force_y, -x.fields.shear_force, atol=1e-6)
    assert b.validation.passed


@pytest.mark.parametrize(
    "changes",
    [
        dict(J=-1),
        dict(G=0),
        dict(E=float("nan")),
        dict(node_j=1),
        dict(releases=(11, 11)),
        dict(releases=(1,)),
        dict(releases=(True,)),
        dict(reference_vector=(0, 0, 0)),
        dict(theory="unknown"),
        dict(theory="timoshenko"),
        dict(Asy=-1),
        dict(roll_angle=float("inf")),
    ],
)
def test_invalid_element_inputs(changes):
    with pytest.raises((ValueError, TypeError)):
        replace(ELEMENT, **changes)


@pytest.mark.parametrize(
    "case",
    [
        "missing_node",
        "duplicate_node",
        "duplicate_element",
        "isolated_node",
        "unknown_nodal_load",
        "unknown_line_load",
        "unknown_support",
        "timoshenko_line_load",
        "invalid_sampling",
    ],
)
def test_model_errors(case):
    nodes, elements, supports, nodal, line = list(NODES), [ELEMENT], [FIXED], [], []
    kwargs = {}
    if case == "missing_node":
        elements = [replace(ELEMENT, node_j=3)]
    if case == "duplicate_node":
        nodes.append(NODES[1])
    if case == "duplicate_element":
        elements.append(ELEMENT)
    if case == "isolated_node":
        nodes.append(f.Node(3, 3, 3, 3))
    if case == "unknown_nodal_load":
        nodal.append(f.NodalLoad(3))
    if case == "unknown_line_load":
        line.append(f.DistributedLoad(3))
    if case == "unknown_support":
        supports.append(replace(FIXED, node_id=3))
    if case == "timoshenko_line_load":
        elements = [replace(ELEMENT, theory="timoshenko", Asy=0.008, Asz=0.008)]
        line = [f.DistributedLoad(1, qy_i=1)]
    if case == "invalid_sampling":
        kwargs["number_of_points"] = True
    with pytest.raises((ValueError, TypeError)):
        f.solve_frame(nodes, elements, supports, nodal, line, **kwargs)


def test_load_superposition_and_unsorted_input_ids():
    a = cantilever(nodal=[f.NodalLoad(2, fy=1000)], line=[f.DistributedLoad(1, qz_j=100)])
    b = cantilever(
        nodes=NODES[::-1],
        nodal=[f.NodalLoad(2, fy=400), f.NodalLoad(2, fy=600)],
        line=[f.DistributedLoad(1, qz_j=40), f.DistributedLoad(1, qz_j=60)],
    )
    close(a.displacements, b.displacements, atol=1e-14)


def test_invalid_support_bases_and_values():
    for kwargs in [
        dict(u=False, u_value=1),
        dict(u="yes"),
        dict(axes=((1, 0, 0), (0, 1, 0), (0, 0, -1))),
    ]:
        with pytest.raises((ValueError, TypeError)):
            replace(FIXED, **kwargs)
    with pytest.raises(ValueError, match="same axes"):
        f.solve_frame(
            NODES, [ELEMENT], [FIXED, f.Support(1, u=True, axes=tuple(map(tuple, rotation())))]
        )


def test_prescribed_rigid_motion_does_not_fail_energy_due_to_roundoff():
    rng = np.random.default_rng(73)
    for _ in range(5):
        h, _ = np.linalg.qr(rng.normal(size=(3, 3)))
        nodes = [f.Node(n.id, *(h @ n.coordinates)) for n in NODES]
        e = replace(ELEMENT, reference_vector=tuple(h @ np.array([0, 1, 0])))
        translation, omega = rng.normal(size=3) * 0.003, rng.normal(size=3) * 0.002
        supports = [
            f.Support(
                n.id,
                True,
                True,
                True,
                True,
                True,
                True,
                *(translation + np.cross(omega, n.coordinates)),
                *omega,
            )
            for n in nodes
        ]
        r = f.solve_frame(nodes, [e], supports)
        assert r.validation.passed
        assert r.validation.strain_energy < 1e-20
        assert r.validation.energy_absolute_error <= r.validation.energy_roundoff_bound
        close(r.reactions, 0, atol=1e-7)


def test_energy_diagnostic_still_rejects_material_work_mismatch():
    from reused_cores.frame3d_linear.validation import energy_check

    ratio, error, bound = energy_check(1.0, 3.0, np.ones(12) * 0.001, np.eye(12) * 1e6, 3.0)
    assert ratio > 0.3
    assert error == 1
    assert bound < 1e-10


def test_nearly_parallel_connections_are_not_misclassified_as_inactive():
    from reused_cores.frame3d_linear.solution import solve_system

    stiffness = np.diag([1.0, 1.0, 1.0, 1.0, 1e-14, 1.0])
    directions = [[(1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 1e-7, 1.0)]]
    force = np.array([0.0, 0.0, 0.0, 0.0, 1.0, 0.0])
    r = solve_system(
        stiffness, force, [f.Support(1, u=True, v=True, w=True)], rotational_connectivity=directions
    )
    assert r.inactive_dof_vectors.shape == (0, 6)
    assert r.active_dof_count == 3
    assert r.displacements[4] == pytest.approx(1e14)
