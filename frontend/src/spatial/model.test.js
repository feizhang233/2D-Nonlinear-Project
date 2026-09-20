import { test } from 'vitest'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { applyMaterial, applySection, autoReference, blankModel, defaultSection, deleteSelected, example3D, insertMember, insertNode, modelIssues, parseModel3D, planeCoords, planePoint, toSpatialPayload, xyz } from './model'
import { basis, project, unproject } from './projection'

test('all work planes preserve global coordinates and orthographic inverse projection', () => {
  for (const plane of ['XY', 'XZ', 'YZ']) {
    const p = planePoint(plane, 1.25, -2.375, 6)
    assert.deepEqual(planeCoords(plane, p), [1.25, -2.375, 6])
    for (const axes of [basis({ azimuth: -.63, elevation: .55 }), basis({ azimuth: 0, elevation: 0 }, plane)]) {
      const q = project(p, axes); const recovered = unproject(q[0], q[1], axes, plane, 6)
      p.forEach((v, i) => assert.ok(Math.abs(v - recovered[i]) < 1e-10))
    }
  }
  assert.equal(unproject(0, 0, basis({ azimuth: 0, elevation: 0 }, 'XZ'), 'XY', 0), null)
})
test('exact coordinates reuse joints; zero-length and duplicate members are rejected atomically', () => {
  const source = blankModel(); const created = insertMember(source, [0, 0, 0], [2.125, 1.375, 0]).model
  assert.equal(source.nodes.length, 0)
  assert.equal(created.nodes[1].x, 2.125)
  assert.equal(insertNode(created, [2.125, 1.375, 0]).model.nodes.length, 2)
  assert.throws(() => insertMember(created, [2.125, 1.375, 0], [0, 0, 0]), /already exists/)
  assert.throws(() => insertMember(created, [0, 0, 0], [0, 0, 0]), /different points/)
  assert.throws(() => insertNode(source, [Infinity, 0, 0]), /finite/)
})
test('intersecting members share a single joint; 3D skew crossings stay unconnected', () => {
  const first = insertMember(blankModel(), [-2, 0, 0], [2, 0, 0]).model
  const connected = insertMember(first, [0, -2, 0], [0, 2, 0]).model
  assert.equal(connected.nodes.length, 5); assert.equal(connected.elements.length, 4)
  const joint = connected.nodes.find(n => n.x === 0 && n.y === 0 && n.z === 0)
  assert.equal(connected.elements.filter(e => e.node_i === joint.id || e.node_j === joint.id).length, 4)
  const skew = insertMember(first, [0, -2, .1], [0, 2, .1]).model
  assert.equal(skew.nodes.length, 4); assert.equal(skew.elements.length, 2)
})
test('partial collinear overlap is split without duplicate segments', () => {
  const first = insertMember(blankModel(), [0, 0, 0], [4, 0, 0]).model
  const extended = insertMember(first, [2, 0, 0], [6, 0, 0]).model
  assert.equal(extended.nodes.length, 4); assert.equal(extended.elements.length, 3)
  const lengths = extended.elements.map(e => Math.abs(extended.nodes[e.node_j - 1].x - extended.nodes[e.node_i - 1].x))
  assert.deepEqual(lengths, [2, 2, 2])
})
test('split members preserve line-load resultant, interpolation, orientation, and original end releases', () => {
  const original = insertMember(blankModel(), [0, 0, 0], [10, 0, 0], { ...defaultSection(), releases: [4, 11], roll_angle: 30 }).model
  original.distributed_loads = [{ element_id: 1, coordinate_system: 'global', qx_i: 2, qy_i: 10, qz_i: -5, mx_i: 0, qx_j: 12, qy_j: 30, qz_j: -25, mx_j: 8 }]
  const split = insertNode(original, [4, 0, 0]).model
  assert.equal(split.elements.length, 2)
  assert.deepEqual(split.elements.map(e => e.releases), [[4], [11]])
  assert.ok(split.elements.every(e => e.roll_angle === 30))
  assert.equal(split.distributed_loads[0].qy_j, 18); assert.equal(split.distributed_loads[1].qy_i, 18)
  const resultant = split.distributed_loads.reduce((sum, l) => { const e = split.elements.find(e => e.id === l.element_id); const length = Math.abs(split.nodes[e.node_j - 1].x - split.nodes[e.node_i - 1].x); return sum + (l.qy_i + l.qy_j) * length / 2 }, 0)
  assert.equal(resultant, 200)
})
test('deletion remaps nodes, supports and loads together and removes dependent member loads', () => {
  const source = example3D(); source.distributed_loads = [{ element_id: 1, coordinate_system: 'local', qx_i: 1, qx_j: 1, qy_i: 0, qy_j: 0, qz_i: 0, qz_j: 0, mx_i: 0, mx_j: 0 }]
  const changed = deleteSelected(source, { nodes: [1], elements: [5] })
  assert.deepEqual(changed.nodes.map(n => n.id), [1, 2, 3, 4, 5, 6, 7])
  assert.equal(changed.nodes[3].z, 3); assert.equal(changed.nodal_loads[0].node_id, 4)
  assert.deepEqual(changed.supports.map(s => s.node_id), [1, 2, 3]); assert.equal(changed.distributed_loads.length, 0)
  assert.ok(changed.elements.every(e => e.id !== 1 && e.id !== 5)); assert.equal(source.nodes.length, 8)
  assert.doesNotThrow(() => parseModel3D(changed))
})
test('auto orientation avoids vertical and reference-parallel members', () => {
  assert.deepEqual(autoReference([0, 0, 0], [0, 3, 0]), [0, 0, 1])
  const model = insertMember(blankModel(), [0, 0, 0], [0, 3, 0]).model
  model.supports = [{ node_id: 1, u: true, v: true, w: true, rx: true, ry: true, rz: true }]
  assert.deepEqual(modelIssues(model), [])
  model.elements[0].reference_vector = [0, 1, 0]
  assert.match(modelIssues(model).join(), /parallel/)
})
test('parser rejects malformed input and unsupported assignments without losing numerical values', () => {
  const model = example3D()
  assert.deepEqual(parseModel3D(toSpatialPayload(model)).elements, model.elements)
  for (const mutate of [m => { m.nodes[0].z = undefined }, m => { m.nodes[0].id = 8 }, m => { m.elements[0].node_j = 999 }, m => { m.elements[0].E = -1 }, m => { m.elements[0].theory = 'nonlinear' }, m => { m.supports[0].u = 'true' }, m => { m.supports[0].axes = [[1, 0, 0], [0, 1, 0], [0, 0, -1]] }]) {
    const bad = structuredClone(model); mutate(bad); assert.throws(() => parseModel3D(bad))
  }
  assert.ok(!Object.hasOwn(toSpatialPayload(model), 'name'))
})
test('repository examples import through the same frontend parser', () => {
  for (const name of ['cantilever_3d', 'space_frame_3d']) {
    const model = parseModel3D(JSON.parse(readFileSync(new URL(`../../../tests/fixtures/frame3d/${name}.json`, import.meta.url), 'utf8')))
    assert.ok(model.nodes.length > 1); assert.deepEqual(modelIssues(model), [])
  }
})
test('material and section assignments change only their own properties on the requested elements', () => {
  const model = example3D(); model.elements[0].roll_angle = 15; model.elements[0].releases = [4, 11]
  const before = structuredClone(model)
  const material = applyMaterial(model, [1, 3], { E: 195e9, G: 75e9 })
  assert.deepEqual(model, before)
  assert.deepEqual(material.elements[0], { ...before.elements[0], E: 195e9, G: 75e9 })
  assert.deepEqual(material.elements[1], before.elements[1])
  const section = { A: .0125, Iy: 1e-4, Iz: 2e-4, J: 1.5e-4, Asy: .009, Asz: .01 }
  const changed = applySection(material, [1, 2], section)
  assert.deepEqual(changed.elements[0], { ...material.elements[0], ...section })
  assert.deepEqual(changed.elements[1], { ...material.elements[1], ...section })
  assert.deepEqual(changed.elements[2], material.elements[2])
  assert.equal(material.elements[0].A, .01)
  const all = applyMaterial(changed, changed.elements.map(e => e.id), { E: 200e9, G: 77e9 })
  all.elements.forEach((e, i) => assert.deepEqual(e, { ...changed.elements[i], E: 200e9, G: 77e9 }))
  assert.deepEqual(parseModel3D(toSpatialPayload(all)).elements, all.elements)
})
test('assignment rejects invalid values and targets atomically, including missing Timoshenko shear areas', () => {
  const model = example3D(); const original = structuredClone(model)
  for (const E of [0, -1, Infinity, NaN]) assert.throws(() => applyMaterial(model, [1], { E, G: 80e9 }), /positive finite/)
  for (const ids of [[], [999], [1, 999]]) {
    assert.throws(() => applyMaterial(model, ids, { E: 210e9, G: 80e9 }), /existing element/)
    assert.throws(() => applySection(model, ids, defaultSection()), /existing element/)
  }
  for (const key of ['A', 'Iy', 'Iz', 'J', 'Asy', 'Asz']) assert.throws(() => applySection(model, [1], { ...defaultSection(), [key]: -1 }), /positive finite/)
  assert.deepEqual(model, original)
  model.elements[0].theory = 'timoshenko'
  assert.throws(() => applySection(model, [1], { ...defaultSection(), Asy: undefined }), /both shear areas/)
})
test('frontend payload solves through the strict backend API schema, including a connected subdivided beam', () => {
  const model = example3D(); const split = insertNode(model, [3, 0, 3]).model
  const localPython = fileURLToPath(new URL(process.platform === 'win32'
    ? '../../../.venv/Scripts/python.exe' : '../../../.venv/bin/python', import.meta.url))
  const executable = process.env.NONLINEAR_TEST_PYTHON ?? (existsSync(localPython) ? localPython : 'python')
  const python = spawnSync(executable, ['-c', `import json,sys
from fastapi.testclient import TestClient
from nonlinear_api.app import create_app
from nonlinear_api.iam_store import IdentityStore
app = create_app(identity_store=IdentityStore(":memory:"))
with TestClient(app) as client:
    response = client.post('/api/v1/3d/solve', json=json.load(sys.stdin))
    assert response.status_code == 200, response.text
    result=response.json()
    assert result['validation']['passed'], result['validation']
    assert len(result['nodal_displacements']) == 9
    print(result['nodal_displacements'][4]['u'])
`], { input: JSON.stringify(toSpatialPayload(split)), encoding: 'utf8', env: { ...process.env, MPLCONFIGDIR: '/tmp/nonlinear-mpl', XDG_CACHE_HOME: '/tmp/nonlinear-cache' } })
  assert.equal(python.status, 0, python.error?.message || python.stderr || python.stdout)
  assert.ok(Math.abs(Number(python.stdout.trim()) - 0.000901163) < 1e-9)
}, 30000)
