import { ApiError, apiUrl, csrfToken, getAccessToken } from './api'

export type VideoUploadPolicy = { max_bytes: number; accepted_types: string[] }
export type VideoUploadStage = 'preparing' | 'uploading' | 'processing' | 'retrying' | 'complete' | 'failed'
export type UploadCallbacks = {
  onProgress?: (percent: number) => void
  onStage?: (stage: VideoUploadStage, attempt: number) => void
}

export class UploadCancelledError extends Error {
  constructor() { super('Video upload cancelled.'); this.name = 'UploadCancelledError' }
}

function responseError(xhr: XMLHttpRequest): ApiError {
  type ErrorBody = { error?: { code?: string; message?: string; request_id?: string }; detail?: string }
  let body: ErrorBody | null = null
  try { body = JSON.parse(xhr.responseText) as ErrorBody } catch { /* A proxy may return an empty or non-JSON error page. */ }
  const code = body?.error?.code
  const message = body?.error?.message ?? body?.detail ?? (xhr.status === 413 ? 'Video exceeds the upload limit.' : 'Video upload failed. Please try again.')
  return new ApiError(message, xhr.status, code, body?.error?.request_id ?? xhr.getResponseHeader('X-Request-ID') ?? undefined)
}

export function describeVideoUploadError(error: unknown, policy: VideoUploadPolicy): string {
  if (error instanceof UploadCancelledError) return 'Upload cancelled. Your existing demonstration is still available.'
  if (!(error instanceof ApiError)) return 'Video upload failed. Your exercise details were saved; try the upload again.'
  const limit = Math.round(policy.max_bytes / (1024 * 1024))
  switch (error.code) {
    case 'UPLOAD_TOO_LARGE': return `Video exceeds the ${limit} MB upload limit. Choose a smaller file.`
    case 'UNSUPPORTED_VIDEO_TYPE': return 'This video format is not supported. Choose an MP4, WebM, or MOV file.'
    case 'STORAGE_UNAVAILABLE': return 'Video storage is unavailable right now. Your exercise details are safe; try the upload again later.'
    case 'IDEMPOTENCY_CONFLICT': return 'This upload changed during retry. Select the video again and retry.'
    case 'AUTH_EXPIRED': return 'Your session has expired. Sign in again before uploading.'
  }
  if (error.status === 413) return `Video exceeds the ${limit} MB upload limit. Choose a smaller file.`
  if (error.status === 401 || error.status === 403) return 'Your session cannot upload this video. Sign in with an authorized account.'
  if (error.code === 'UPLOAD_TIMEOUT') return 'The video upload timed out. Retry the upload; your exercise details are safe.'
  if (error.code === 'NETWORK_ERROR') return 'The connection dropped while uploading. Retry the upload; your exercise details are safe.'
  return error.message || 'Video upload failed. Your exercise details were saved; try the upload again.'
}

export function videoFileError(file: File | null, policy: VideoUploadPolicy): string {
  if (!file) return ''
  if (!policy.accepted_types.includes(file.type)) return 'Choose an MP4, WebM, or MOV video file.'
  if (file.size === 0) return 'Choose a nonempty video file.'
  if (file.size > policy.max_bytes) return `Video exceeds the ${Math.round(policy.max_bytes / (1024 * 1024))} MB upload limit.`
  return ''
}

function uploadOnce<T>(exerciseId: string, file: File, key: string, signal: AbortSignal, callbacks: UploadCallbacks, attempt: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    if (signal.aborted) { reject(new UploadCancelledError()); return }
    const xhr = new XMLHttpRequest()
    let settled = false
    const finish = (result: { value: T } | { error: Error }) => {
      if (settled) return
      settled = true
      signal.removeEventListener('abort', abort)
      if ('error' in result) reject(result.error)
      else resolve(result.value)
    }
    const abort = () => xhr.abort()
    xhr.open('POST', apiUrl(`/exercises/${exerciseId}/video`))
    xhr.withCredentials = true
    xhr.timeout = 5 * 60 * 1000
    const token = getAccessToken()
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    xhr.setRequestHeader('X-CSRF-Token', csrfToken())
    xhr.setRequestHeader('Idempotency-Key', key)
    xhr.upload.onprogress = event => {
      if (event.lengthComputable && event.total > 0) callbacks.onProgress?.(Math.min(100, Math.round(event.loaded / event.total * 100)))
    }
    xhr.upload.onload = () => { callbacks.onProgress?.(100); callbacks.onStage?.('processing', attempt) }
    xhr.onload = () => {
      if (xhr.status < 200 || xhr.status >= 300) { finish({ error: responseError(xhr) }); return }
      try { finish({ value: JSON.parse(xhr.responseText) as T }) }
      catch { finish({ error: new ApiError('The server returned an invalid upload response.', 502, 'INVALID_RESPONSE') }) }
    }
    xhr.onerror = () => finish({ error: new ApiError('The connection dropped while uploading.', 0, 'NETWORK_ERROR') })
    xhr.ontimeout = () => finish({ error: new ApiError('The video upload timed out.', 0, 'UPLOAD_TIMEOUT') })
    xhr.onabort = () => finish({ error: new UploadCancelledError() })
    signal.addEventListener('abort', abort, { once: true })
    const body = new FormData()
    body.set('file', file)
    callbacks.onStage?.('uploading', attempt)
    xhr.send(body)
  })
}

function mayRetry(error: unknown): boolean {
  if (!(error instanceof ApiError)) return false
  return error.status === 0 || [408, 429, 502, 503, 504].includes(error.status)
}

function retryDelay(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) { reject(new UploadCancelledError()); return }
    const timer = window.setTimeout(() => { signal.removeEventListener('abort', abort); resolve() }, ms)
    const abort = () => { window.clearTimeout(timer); reject(new UploadCancelledError()) }
    signal.addEventListener('abort', abort, { once: true })
  })
}

export async function uploadExerciseVideo<T>(exerciseId: string, file: File, key: string, signal: AbortSignal, callbacks: UploadCallbacks = {}): Promise<T> {
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    callbacks.onStage?.(attempt === 1 ? 'preparing' : 'retrying', attempt)
    try {
      const saved = await uploadOnce<T>(exerciseId, file, key, signal, callbacks, attempt)
      callbacks.onStage?.('complete', attempt)
      return saved
    } catch (error) {
      if (attempt === 3 || !mayRetry(error)) { callbacks.onStage?.('failed', attempt); throw error }
      await retryDelay(500 * 2 ** (attempt - 1), signal)
    }
  }
  throw new Error('Video upload failed.')
}
