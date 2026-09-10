import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { AnalysisOutcome, SearchResponse } from '../api/analysis-types'
import { HomePage } from './HomePage'

function response(outcome: AnalysisOutcome, overrides: Partial<SearchResponse> = {}): SearchResponse {
  return {
    outcome, query_plan: null, candidate_startups: [], selected_sources: [],
    structured_profiles: [], classifications: [], validated_profiles: [],
    validated_classifications: [], claim_validations: [], classification_validations: [],
    validated_claims: [], rejected_claims: [], conflicting_claims: [], evidence_gaps: [],
    nvidia_contexts: [], recommendations: [], briefings: [], warnings: [], errors: [], metrics: {},
    ...overrides,
  }
}

function mockApi(payload: SearchResponse) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify(payload), { status: 200, headers: { 'Content-Type': 'application/json' } }),
  )
}

function submitQuery(query = 'startups de saúde com IA') {
  fireEvent.change(screen.getByLabelText(/consulta em linguagem natural/i), { target: { value: query } })
  fireEvent.click(screen.getByRole('button', { name: /analisar startups/i }))
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllEnvs()
})

describe('HomePage', () => {
  it('executa a demonstração completa sem chamar serviços externos', async () => {
    vi.stubEnv('VITE_DEMO_MODE', 'true')
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    render(<HomePage />)

    submitQuery('Analise a Neurotech')

    expect(screen.getByText(/pipeline em execução/i)).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Neurotech' })).toBeInTheDocument()
    expect(screen.getByText(/modo demonstração/i)).toBeInTheDocument()
    expect(screen.getByText(/NVIDIA NIM é uma oportunidade/i)).toBeInTheDocument()
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('valida a consulta antes de chamar a API', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    render(<HomePage />)
    fireEvent.click(screen.getByRole('button', { name: /analisar startups/i }))
    expect(screen.getByText(/descreva quais startups/i)).toBeInTheDocument()
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('envia linguagem natural e filtros canônicos ao endpoint completo', async () => {
    const fetchSpy = mockApi(response('no_results'))
    render(<HomePage />)
    fireEvent.change(screen.getByLabelText('Setor'), { target: { value: 'data_and_ai' } })
    fireEvent.change(screen.getByLabelText('Estágio'), { target: { value: 'seed' } })
    submitQuery()

    await screen.findByText(/nenhuma startup encontrada/i)
    const [, request] = fetchSpy.mock.calls[0]
    expect(String(fetchSpy.mock.calls[0][0])).toContain('/api/v1/search')
    expect(request?.body).toBe(JSON.stringify({
      query: 'startups de saúde com IA\n\nFiltros explícitos: setor=data_and_ai; estágio=seed.',
    }))
  })

  it('anuncia carregamento enquanto a pipeline está em execução', async () => {
    let resolveRequest: ((value: Response) => void) | undefined
    vi.spyOn(globalThis, 'fetch').mockReturnValue(new Promise((resolve) => { resolveRequest = resolve }))
    render(<HomePage />)
    submitQuery()
    expect(screen.getByText(/pipeline em execução/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /analisando/i })).toBeDisabled()
    resolveRequest?.(new Response(JSON.stringify(response('no_results'))))
    await screen.findByText(/nenhuma startup encontrada/i)
  })

  it('exibe perguntas de esclarecimento e permite levá-las ao campo', async () => {
    mockApi(response('needs_clarification', {
      query_plan: {
        status: 'needs_clarification', normalized_query: 'startups de IA',
        filters: { sectors: [], company_sizes: [], stages: [], locations: [], keywords: [], ai_usage_signals: [] },
        analysis_strategy: { mode: 'exploratory', objectives: [], rationale: 'Consulta ampla.' },
        ambiguities: ['O setor não está definido.'],
        clarification_questions: ['Qual setor você deseja analisar?'],
        unresolved_filters: [], filter_suggestions: [],
      },
    }))
    render(<HomePage />)
    submitQuery('startups de IA')
    const question = await screen.findByRole('button', { name: 'Qual setor você deseja analisar?' })
    fireEvent.click(question)
    expect(screen.getByLabelText(/consulta em linguagem natural/i)).toHaveValue('startups de IA\nQual setor você deseja analisar?')
  })

  it.each([
    ['invalid_query', 'Revise a consulta'],
    ['no_results', 'Nenhuma startup encontrada'],
    ['temporarily_unavailable', 'Serviço temporariamente indisponível'],
    ['internal_failure', 'A análise não pôde ser concluída'],
  ] as const)('apresenta o estado %s', async (outcome, title) => {
    mockApi(response(outcome))
    render(<HomePage />)
    submitQuery()
    expect(await screen.findByRole('heading', { name: title })).toBeInTheDocument()
  })

  it('permite selecionar uma startup sem misturar seus perfis', async () => {
    mockApi(response('success', {
      candidate_startups: [
        { startup_id: 'one', name: 'Alpha', score: 0.9 },
        { startup_id: 'two', name: 'Beta', score: 0.8 },
      ],
      validated_profiles: [
        { startup_id: 'one', name: 'Alpha', product: { value: 'Produto Alpha', sources: [] }, business_model: null, sector: null, target_audience: null, ai_use_cases: [], technologies: [], infrastructure: [], external_dependencies: [], technical_needs: [], claims: [], unknown_fields: [] },
        { startup_id: 'two', name: 'Beta', product: { value: 'Produto Beta', sources: [] }, business_model: null, sector: null, target_audience: null, ai_use_cases: [], technologies: [], infrastructure: [], external_dependencies: [], technical_needs: [], claims: [], unknown_fields: [] },
      ],
    }))
    render(<HomePage />)
    submitQuery()
    expect(await screen.findByText('Produto Alpha')).toBeInTheDocument()
    expect(screen.queryByText('Produto Beta')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Beta/i }))
    expect(await screen.findByText('Produto Beta')).toBeInTheDocument()
    expect(screen.queryByText('Produto Alpha')).not.toBeInTheDocument()
  })

  it('sanitiza respostas incompatíveis', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('<html>erro</html>', { status: 503 }))
    render(<HomePage />)
    submitQuery()
    expect(await screen.findByRole('alert')).toHaveTextContent(/formato que a interface não reconhece/i)
  })
})
