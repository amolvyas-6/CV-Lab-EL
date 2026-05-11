import type {
  ExtractResponse,
  BatchExtractionPayload,
  ExtractionPayload,
  HealthResponse,
  JobsResponse,
  MetadataResponse,
  SummaryResponse,
  BackendJobRecord,
} from './types'

const API_BASE = '/api'

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  })

  if (!response.ok) {
    let errorMessage = `Request failed with status ${response.status}`

    try {
      const payload = (await response.json()) as { detail?: string }
      if (payload.detail) {
        errorMessage = payload.detail
      }
    } catch {
      // Ignore parse errors and keep default status-based message.
    }

    throw new Error(errorMessage)
  }

  return (await response.json()) as T
}

export function fetchHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>('/health')
}

export function startExtraction(payload: ExtractionPayload): Promise<ExtractResponse> {
  return requestJson<ExtractResponse>('/extract', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function startBatchExtraction(payload: BatchExtractionPayload): Promise<ExtractResponse> {
  return requestJson<ExtractResponse>('/batch-extract', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getJobStatus(jobId: string): Promise<BackendJobRecord> {
  return requestJson<BackendJobRecord>(`/status/${jobId}`)
}

export function listJobs(): Promise<JobsResponse> {
  return requestJson<JobsResponse>('/jobs')
}

export function fetchMetadata(): Promise<MetadataResponse> {
  return requestJson<MetadataResponse>('/metadata')
}

export function fetchSummary(): Promise<SummaryResponse> {
  return requestJson<SummaryResponse>('/summary')
}
