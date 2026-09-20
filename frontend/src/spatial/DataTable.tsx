import { useState } from 'react'
import { Checkbox, Table, TableBody, TableCell, TableContainer, TableHead, TablePagination, TableRow } from '@mui/material'
export type Column = { key: string; label: string; numeric?: boolean }
export function DataTable({ columns, rows, selected, onSelect, label }: { columns: Column[]; rows: Record<string, string | number>[]; selected?: number[]; onSelect?: (id: number, extend: boolean) => void; label: string }) {
  const [page, setPage] = useState(0); const safePage = Math.min(page, Math.max(0, Math.ceil(rows.length / 20) - 1))
  return <div className="spatial-data-table">
    <TableContainer sx={{ flex: 1, minHeight: 0 }}><Table stickyHeader size="small" aria-label={label}><TableHead><TableRow>
      {onSelect && <TableCell padding="checkbox"><span className="sr-only">Select</span></TableCell>}
      {columns.map(c => <TableCell key={c.key} align={c.numeric ? 'right' : 'left'}>{c.label}</TableCell>)}
    </TableRow></TableHead><TableBody>
      {rows.slice(safePage * 20, safePage * 20 + 20).map((row, i) => <TableRow key={`${row.id}-${i}`} hover selected={selected?.includes(Number(row.id))}>
        {onSelect && <TableCell padding="checkbox"><Checkbox size="small" checked={selected?.includes(Number(row.id)) ?? false} onChange={() => onSelect(Number(row.id), true)} slotProps={{ input: { 'aria-label': `Select ${label} ${row.id}` } }} /></TableCell>}
        {columns.map(c => <TableCell key={c.key} align={c.numeric ? 'right' : 'left'} sx={{ fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>{row[c.key]}</TableCell>)}
      </TableRow>)}
      {!rows.length && <TableRow><TableCell colSpan={columns.length + (onSelect ? 1 : 0)} sx={{ py: 3, textAlign: 'center', color: 'text.secondary' }}>No {label.toLowerCase()} yet.</TableCell></TableRow>}
    </TableBody></Table></TableContainer>
    <TablePagination component="div" count={rows.length} page={safePage} onPageChange={(_, value) => setPage(value)} rowsPerPage={20} rowsPerPageOptions={[20]} sx={{ flexShrink: 0, '.MuiTablePagination-toolbar': { minHeight: 40, pl: 1 }, '.MuiTablePagination-selectLabel,.MuiTablePagination-displayedRows': { my: 0 } }} />
  </div>
}
