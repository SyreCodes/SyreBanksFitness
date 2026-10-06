/** Resolve API media paths against the configured API origin for split deployments. */
export function mediaPlaybackUrl(url: string | null | undefined): string | undefined {
  if (!url) return undefined
  try {
    const apiOrigin = new URL(import.meta.env.VITE_API_URL || window.location.origin, window.location.origin).origin
    const parsed = new URL(url, apiOrigin)
    return ['https:', 'http:'].includes(parsed.protocol) ? parsed.href : undefined
  } catch { return undefined }
}
