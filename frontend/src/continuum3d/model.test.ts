import { describe, expect, it } from 'vitest'
import { blockModel, boundaryFaces, exampleSolid, parseSolid } from './model'
import hex from '../../../tests/fixtures/continuum3d/hex8.json'
import tet from '../../../tests/fixtures/continuum3d/tet4.json'

describe('solid topology and portable host contract',()=>{
  it('matches the actual frontend payloads solved by host integration tests',()=>{
    expect(exampleSolid('hex8')).toEqual(hex)
    expect(exampleSolid('tet4')).toEqual(tet)
    expect(parseSolid(JSON.parse(JSON.stringify(hex)))).toEqual(hex)
  })
  it('generates conforming tetrahedra with only the true outer boundary exposed',()=>{
    const m=blockModel([2,1,1],[2,1,1],'tet4')
    expect(m.elements).toHaveLength(12)
    expect(boundaryFaces(m)).toHaveLength(20)
    expect(new Set(m.elements.flatMap(e=>e.nodes)).size).toBe(m.nodes.length)
  })
  it('bounds mesh generation before allocation and rejects invalid imported shapes',()=>{
    expect(()=>blockModel([1,1,1],[1000,1000,1000])).toThrow('200 nodes')
    expect(()=>blockModel([1,0,1],[1,1,1])).toThrow('positive')
    expect(()=>blockModel([1,1,1],[1,1.5,1])).toThrow('whole-number')
    expect(()=>parseSolid({...hex,body_force:[0,NaN,0]})).toThrow('finite')
    expect(()=>parseSolid({...hex,elements:[{...hex.elements[0],nodes:[999,2,3,4,5,6,7,8]}]})).toThrow('connectivity')
    expect(()=>parseSolid({...hex,materials:[{id:1,E:1,nu:.5}]})).toThrow('isotropic')
  })
})
