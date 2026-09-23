export function csvCell(value: unknown): string {
  let text = value === null || value === undefined ? '' : String(value)
  if (/^[\s]*[=+\-@\t\r]/.test(text)) text = `'${text}`
  return `"${text.replace(/"/g, '""')}"`
}
export function makeCsv(rows: unknown[][]) { return '\uFEFF' + rows.map(row => row.map(csvCell).join(';')).join('\r\n') }
export function downloadCsv(filename: string, rows: unknown[][]) {
  downloadBlob(filename, new Blob([makeCsv(rows)], { type: 'text/csv;charset=utf-8' }))
}
export function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url; link.download = filename; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
