/**
 * Thin compatibility wrapper — re-exports the reducer for tests
 * and provides useHydraSocket as an alias for useHydra.
 *
 * All state management has moved to HydraContext.
 */
export { reducer } from '../context/HydraContext'
export { useHydra as useHydraSocket } from '../context/HydraContext'
