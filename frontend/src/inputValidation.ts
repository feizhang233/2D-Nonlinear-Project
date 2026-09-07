/** Form drafts may contain unfinished scientific notation; never serialize it as null. */
export function hasNonFiniteNumber(value: unknown): boolean {
  if (typeof value === 'number') return !Number.isFinite(value)
  if (!value || typeof value !== 'object') return false
  return Object.values(value).some(hasNonFiniteNumber)
}
