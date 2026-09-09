import type { SearchResponse } from './analysis-types'

const DEFAULT_API_URL = 'http://127.0.0.1:8000'
const REQUEST_TIMEOUT_MS = 180_000

function apiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim()
  return (configured || DEFAULT_API_URL).replace(/\/$/, '')
}

function isSearchResponse(value: unknown): value is SearchResponse {
  if (typeof value !== 'object' || value === null) return false
  const candidate = value as Partial<SearchResponse>
  return (
    typeof candidate.outcome === 'string' &&
    Array.isArray(candidate.candidate_startups) &&
    Array.isArray(candidate.errors)
  )
}

export class AnalysisClientError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'AnalysisClientError'
  }
}

export async function analyzeStartups(query: string): Promise<SearchResponse> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

  try {
    const response = await fetch(`${apiBaseUrl()}/api/v1/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
      signal: controller.signal,
    })
    const payload: unknown = await response.json().catch(() => null)
    if (!isSearchResponse(payload)) {
      throw new AnalysisClientError(
        'A API respondeu em um formato que a interface não reconhece.',
      )
    }
    return payload
  } catch (error) {
    if (error instanceof AnalysisClientError) throw error
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new AnalysisClientError(
        'A análise excedeu o tempo de espera. Tente novamente.',
      )
    }
    throw new AnalysisClientError(
      'Não foi possível conectar à API. Confirme se o backend está em execução.',
    )
  } finally {
    window.clearTimeout(timeout)
  }
}
