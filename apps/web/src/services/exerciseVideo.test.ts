import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from './api'
import { describeVideoUploadError, uploadExerciseVideo, videoFileError } from './exerciseVideo'

type Reply = { status: number; body?: unknown; network?: boolean }
const replies: Reply[] = []
const requests: FakeXHR[] = []
const OriginalXHR = globalThis.XMLHttpRequest

class FakeXHR {
  status = 0
  responseText = ''
  timeout = 0
  withCredentials = false
  headers: Record<string, string> = {}
  body: FormData | null = null
  upload = { onprogress: null as ((event: { lengthComputable: boolean; loaded: number; total: number }) => void) | null, onload: null as (() => void) | null }
  onload: (() => void) | null = null
  onerror: (() => void) | null = null
  ontimeout: (() => void) | null = null
  onabort: (() => void) | null = null
  open(method: string, url: string) { expect(method).toBe('POST'); expect(url).toContain('/exercises/exercise-1/video') }
  setRequestHeader(key: string, value: string) { this.headers[key] = value }
  getResponseHeader() { return null }
  abort() { this.onabort?.() }
  send(body: FormData) {
    this.body = body
    requests.push(this)
    const reply = replies.shift() ?? { status: 200, body: { id: 'exercise-1' } }
    queueMicrotask(() => {
      if (reply.network) { this.onerror?.(); return }
      this.upload.onprogress?.({ lengthComputable: true, loaded: 5, total: 10 })
      this.upload.onload?.()
      this.status = reply.status
      this.responseText = JSON.stringify(reply.body ?? {})
      this.onload?.()
    })
  }
}

describe('exercise video transport', () => {
  afterEach(() => {
    globalThis.XMLHttpRequest = OriginalXHR
    replies.length = 0
    requests.length = 0
    vi.useRealTimers()
  })

  it('sends multipart with auth, progress, and a stable idempotency key', async () => {
    globalThis.XMLHttpRequest = FakeXHR as unknown as typeof XMLHttpRequest
    const file = new File(['video bytes'], 'demo.mp4', { type: 'video/mp4' })
    const progress: number[] = []
    const stages: string[] = []
    const result = await uploadExerciseVideo<{ id: string }>('exercise-1', file, 'upload-key-123', new AbortController().signal, {
      onProgress: value => progress.push(value), onStage: stage => stages.push(stage),
    })
    expect(result.id).toBe('exercise-1')
    expect(requests).toHaveLength(1)
    expect(requests[0].body?.get('file')).toBe(file)
    expect(requests[0].headers['Idempotency-Key']).toBe('upload-key-123')
    expect(requests[0].headers).not.toHaveProperty('Content-Type')
    expect(requests[0].withCredentials).toBe(true)
    expect(progress).toEqual([50, 100])
    expect(stages).toEqual(['preparing', 'uploading', 'processing', 'complete'])
  })

  it('retries a temporary network failure with the same key', async () => {
    globalThis.XMLHttpRequest = FakeXHR as unknown as typeof XMLHttpRequest
    replies.push({ status: 0, network: true }, { status: 200, body: { id: 'exercise-1' } })
    const upload = uploadExerciseVideo('exercise-1', new File(['x'], 'demo.mp4', { type: 'video/mp4' }), 'upload-key-123', new AbortController().signal)
    await expect(upload).resolves.toEqual({ id: 'exercise-1' })
    expect(requests).toHaveLength(2)
    expect(requests.map(item => item.headers['Idempotency-Key'])).toEqual(['upload-key-123', 'upload-key-123'])
  })

  it('does not retry permanent validation errors', async () => {
    globalThis.XMLHttpRequest = FakeXHR as unknown as typeof XMLHttpRequest
    replies.push({ status: 413, body: { error: { code: 'UPLOAD_TOO_LARGE', message: 'Too large.' } } })
    await expect(uploadExerciseVideo('exercise-1', new File(['x'], 'demo.mp4', { type: 'video/mp4' }), 'upload-key-123', new AbortController().signal)).rejects.toMatchObject({ status: 413, code: 'UPLOAD_TOO_LARGE' })
    expect(requests).toHaveLength(1)
  })

  it('uses the configured policy in file and server-error messages', () => {
    const policy = { max_bytes: 3, accepted_types: ['video/mp4'] }
    expect(videoFileError(new File(['large'], 'demo.mp4', { type: 'video/mp4' }), policy)).toMatch(/upload limit/)
    expect(videoFileError(new File(['x'], 'demo.txt', { type: 'text/plain' }), policy)).toMatch(/MP4/)
    expect(describeVideoUploadError(new ApiError('Storage failed', 503, 'STORAGE_UNAVAILABLE'), policy)).toMatch(/storage is unavailable/i)
  })
})
