import axios from 'axios'

import type {
  ExtractionPayload,
  ExtractionResponse,
  JobStatusResponse,
} from './types'

export const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  'http://127.0.0.1:8000'

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

export async function createExtractionJob(
  payload: ExtractionPayload,
): Promise<ExtractionResponse> {
  const { data } = await client.post<ExtractionResponse>('/extract', payload)
  return data
}

export async function fetchJobStatus(jobId: string): Promise<JobStatusResponse> {
  const { data } = await client.get<JobStatusResponse>(`/status/${jobId}`)
  return data
}

export async function fetchHealth(): Promise<{ status: string }> {
  const { data } = await client.get<{ status: string }>('/health')
  return data
}
