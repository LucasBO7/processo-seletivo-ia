import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { SearchResponse } from '../api/analysis-types'
import { StartupDetails } from './StartupDetails'

const baseResponse: SearchResponse = {
  outcome: 'success', query_plan: null,
  candidate_startups: [{ startup_id: 'one', name: 'Alpha / Brasil', score: 0.9 }],
  selected_sources: [
    { startup_id: 'one', source_id: 'safe', source_url: 'https://example.com/fonte', title: 'Fonte segura', excerpt: 'Trecho <script>não executável</script>' },
    { startup_id: 'one', source_id: 'unsafe', source_url: 'javascript:alert(1)', title: 'Fonte maliciosa', excerpt: null },
  ],
  structured_profiles: [], validated_profiles: [], classifications: [], validated_classifications: [],
  claim_validations: [], classification_validations: [], validated_claims: [], rejected_claims: [], conflicting_claims: [], evidence_gaps: [],
  nvidia_contexts: [], recommendations: [], warnings: [], errors: [], metrics: {},
  briefings: [{
    startup_id: 'one', startup_name: 'Alpha / Brasil', business_facts: [], technical_gaps: [],
    executive_summary: [{ kind: 'confirmed_fact', text: 'Resumo seguro', citation_ids: ['S1'] }],
    inception_opportunities: [], uncertainties_and_gaps: [], missing_sections: [], markdown: '# Alpha\n\nConteúdo original',
  }],
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('StartupDetails', () => {
  it('cria apenas links com protocolos permitidos e trata conteúdo como texto', () => {
    render(<StartupDetails response={baseResponse} startupId="one" />)
    expect(screen.getByRole('link', { name: /fonte segura/i })).toHaveAttribute('href', 'https://example.com/fonte')
    expect(screen.queryByRole('link', { name: /fonte maliciosa/i })).not.toBeInTheDocument()
    expect(screen.getByText(/<script>não executável<\/script>/i)).toBeInTheDocument()
  })

  it('exporta o Markdown em um arquivo de texto', () => {
    const createObjectURL = vi.fn<(blob: Blob) => string>(() => 'blob:briefing')
    const revokeObjectURL = vi.fn<(url: string) => void>()
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: createObjectURL })
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revokeObjectURL })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    render(<StartupDetails response={baseResponse} startupId="one" />)
    fireEvent.click(screen.getByRole('button', { name: /exportar briefing/i }))
    const blob = createObjectURL.mock.calls[0][0] as Blob
    expect(blob.type).toBe('text/markdown;charset=utf-8')
    expect(click).toHaveBeenCalledOnce()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:briefing')
  })

  it('explica quando o validador bloqueia recomendação e briefing', () => {
    render(<StartupDetails response={{
      ...baseResponse,
      briefings: [],
      errors: [{ code: 'evidence_validator_unavailable', message: 'Falha segura.', node: 'evidence_validator' }],
    }} startupId="one" />)

    expect(screen.getByText(/validação de evidências ficou indisponível/i)).toBeInTheDocument()
    expect(screen.getByText(/briefing depende de pelo menos uma recomendação/i)).toBeInTheDocument()
  })

  it('distingue ausência de necessidade de contexto NVIDIA insuficiente', () => {
    const response = {
      ...baseResponse,
      briefings: [],
      warnings: ['recommendation_no_identified_need'],
      nvidia_contexts: [{
        startup_id: 'one',
        startup_name: 'Alpha / Brasil',
        chunks: [],
        gaps: [],
        sufficiency: { status: 'sufficient' as const, reasons: [] },
      }],
    }

    render(<StartupDetails response={response} startupId="one" />)

    expect(screen.getByText(/nenhuma necessidade técnica validada/i)).toBeInTheDocument()
  })
})
