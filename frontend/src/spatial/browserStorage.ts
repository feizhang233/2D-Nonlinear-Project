export function readBrowserStorage(key: string): string | null {
  try { return window.localStorage.getItem(key) } catch { return null }
}
export function writeBrowserStorage(key: string, value: string): boolean {
  try { window.localStorage.setItem(key, value); return true } catch { return false }
}
