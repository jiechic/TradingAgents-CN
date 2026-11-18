// Vite injects the repository VERSION for both development and production.
const appVersion = (import.meta.env.VITE_APP_VERSION || '').trim() || 'unknown'

export const APP_CONFIG = {
  version: appVersion,
  fullVersion: appVersion,
} as const
