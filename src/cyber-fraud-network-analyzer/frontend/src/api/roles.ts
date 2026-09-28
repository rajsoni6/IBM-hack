/**
 * api/roles.ts
 * Re-exports role types and functions from patterns.ts for cleaner imports.
 */
export type { RoleEntry, RolesResponse } from './patterns'
export { getRoles, runRoleAnalysis } from './patterns'
