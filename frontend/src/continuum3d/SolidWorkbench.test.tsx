// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import App from '../App'
import { studioTheme } from '../theme'
import { exampleSolid } from './model'
import response from '../../../tests/fixtures/continuum3d/hex8-response.json'

const key='nonlinear-studio.continuum3d.model.v1'
vi.setConfig({ testTimeout: 20_000 })
let values:Map<string,string>
beforeEach(()=>{
  values=new Map([['nonlinear-studio-guide-hidden-v2','true'],[key,JSON.stringify(exampleSolid())]])
  Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:(k:string)=>values.get(k)??null,setItem:(k:string,v:string)=>values.set(k,v)}})
  vi.stubGlobal('ResizeObserver',class{observe(){} disconnect(){} unobserve(){}})
  vi.spyOn(globalThis,'fetch').mockImplementation(async input=>{
    if(String(input).includes('/auth/session'))return Response.json({authenticated:false,user:null})
    if(String(input).includes('/continuum3d/solve'))return Response.json(response)
    throw new Error(`Unexpected request: ${input}`)
  })
})
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals()})
function open(){
  render(<ThemeProvider theme={studioTheme}><App/></ThemeProvider>)
  fireEvent.click(screen.getByRole('button',{name:'3D'}))
  fireEvent.click(screen.getByRole('tab',{name:'Continuum 3D workspace'}))
}
it('places dimension before Frame; gates unsupported modules and preserves each draft',()=>{
  open()
  expect(screen.getByRole('tab',{name:'Plate 3D workspace'})).toBeEnabled()
  expect(screen.getByRole('tab',{name:'Shell 3D workspace'})).toBeEnabled()
  fireEvent.click(screen.getByRole('button',{name:/^Materials/}))
  fireEvent.change(screen.getByLabelText('Young’s modulus'),{target:{value:'2e-'}})
  expect(screen.getByRole('button',{name:'Run analysis'})).toBeDisabled()
  fireEvent.click(screen.getByRole('tab',{name:'Frame 3D workspace'}))
  expect(document.title).toBe('Frame 3D workspace — Nonlinear Studio')
  fireEvent.click(screen.getByRole('tab',{name:'Continuum 3D workspace'}))
  expect(screen.getByLabelText('Young’s modulus')).toHaveValue('2e-')
  fireEvent.click(screen.getByRole('button',{name:'2D'}))
  expect(screen.getByRole('tab',{name:'Plate workspace'})).not.toBeDisabled()
  fireEvent.click(screen.getByRole('button',{name:'3D'}))
  fireEvent.click(screen.getByRole('tab',{name:'Continuum 3D workspace'}))
  expect(screen.getByLabelText('Young’s modulus')).toHaveValue('2e-')
  fireEvent.click(screen.getByRole('button',{name:'Cancel changes'}))
  expect(screen.getByLabelText('Young’s modulus')).toHaveValue('200000000000')
})
it('runs a true solid payload, shows raw point results and invalidates edits with undo',async()=>{
  open();fireEvent.click(screen.getByRole('button',{name:'Run analysis'}))
  await screen.findByText('Checks passed')
  const call=vi.mocked(fetch).mock.calls.find(([url])=>String(url).includes('/continuum3d/solve'))!
  expect(JSON.parse(String(call[1]?.body))).toEqual(exampleSolid())
  fireEvent.click(screen.getByRole('tab',{name:'Integration-point stress'}))
  expect(screen.getByRole('table',{name:'Integration point stress'})).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'Model'}))
  fireEvent.click(screen.getByRole('button',{name:/^Materials/}))
  fireEvent.change(screen.getByLabelText('Young’s modulus'),{target:{value:'100e9'}})
  fireEvent.click(screen.getByRole('button',{name:'Apply material'}))
  expect(JSON.parse(values.get(key)!).materials[0].E).toBe(100e9)
  expect(screen.getByRole('button',{name:'Results'})).toBeDisabled()
  fireEvent.click(screen.getByRole('button',{name:'Undo'}))
  expect(JSON.parse(values.get(key)!).materials[0].E).toBe(200e9)
})
it('reports failed solves, retries and discards a late cancelled response',async()=>{
  open()
  vi.mocked(fetch).mockResolvedValueOnce(Response.json({error:{message:'Missing solid supports'}},{status:422}))
  fireEvent.click(screen.getByRole('button',{name:'Run analysis'}));await screen.findByText('Missing solid supports')
  let finish!:(response:Response)=>void
  vi.mocked(fetch).mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve}))
  fireEvent.click(screen.getByRole('button',{name:'Run analysis'}))
  expect(screen.getByText('Solving…')).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'Cancel'}))
  await act(async()=>finish(Response.json(response)))
  await waitFor(()=>expect(screen.queryByText('Checks passed')).toBeNull())
  expect(screen.getByText(/server may still be finishing/)).toBeTruthy()
})
it('clears boundary data when remeshing and restores the complete model with undo',()=>{
  open();fireEvent.click(screen.getByRole('button',{name:'Geometry & mesh'}))
  fireEvent.change(screen.getByLabelText('X divisions'),{target:{value:'2'}})
  fireEvent.click(screen.getByRole('button',{name:'Generate mesh'}))
  const changed=JSON.parse(values.get(key)!)
  expect(changed.elements).toHaveLength(8);expect(changed.constraints).toEqual([]);expect(changed.tractions).toEqual([])
  fireEvent.click(screen.getByRole('button',{name:'Undo'}))
  expect(JSON.parse(values.get(key)!)).toEqual(exampleSolid())
})
