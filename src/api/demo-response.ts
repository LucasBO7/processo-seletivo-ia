import type { SearchResponse, SourceLink } from './analysis-types'

const startupId = '11111111-1111-4111-8111-111111111111'
const sourceId = '22222222-2222-4222-8222-222222222222'
const chunkId = '33333333-3333-4333-8333-333333333333'
const source: SourceLink = {
  startup_id: startupId,
  source_id: sourceId,
  source_url: 'https://www.neurotech.com.br/',
}
const product = {
  value: 'Plataforma de inteligência artificial para decisões de crédito e risco.',
  sources: [source],
}
const technicalNeed = {
  value: 'Escalar inferência de modelos com baixa latência e operação previsível.',
  sources: [source],
}

export function demoSearchResponse(query: string): SearchResponse {
  return {
    outcome: 'success',
    query_plan: {
      status: 'ready',
      normalized_query: query.trim(),
      filters: {
        sectors: ['financial_services'],
        company_sizes: [],
        stages: [],
        locations: ['Brasil'],
        keywords: ['Neurotech'],
        ai_usage_signals: ['IA no produto principal'],
      },
      analysis_strategy: {
        mode: 'targeted',
        objectives: ['Avaliar maturidade de IA', 'Identificar oportunidades NVIDIA'],
        rationale: 'Análise direcionada à startup selecionada.',
      },
      ambiguities: [],
      clarification_questions: [],
      unresolved_filters: [],
      filter_suggestions: [],
    },
    candidate_startups: [{ startup_id: startupId, name: 'Neurotech', score: 0.94 }],
    selected_sources: [{
      ...source,
      title: 'Neurotech — soluções de IA',
      excerpt: 'Conteúdo ilustrativo usado exclusivamente no modo de demonstração.',
    }],
    structured_profiles: [],
    validated_profiles: [{
      startup_id: startupId,
      name: 'Neurotech',
      product,
      business_model: {
        value: 'Soluções B2B para instituições financeiras e empresas.',
        sources: [source],
      },
      sector: { value: 'Serviços financeiros e análise de risco.', sources: [source] },
      target_audience: {
        value: 'Instituições que automatizam decisões de crédito e risco.',
        sources: [source],
      },
      ai_use_cases: [{
        value: 'Modelos preditivos aplicados à análise de risco.',
        sources: [source],
      }],
      technologies: [{ value: 'Machine learning e processamento de dados.', sources: [source] }],
      infrastructure: [],
      external_dependencies: [],
      technical_needs: [technicalNeed],
      claims: [],
      unknown_fields: ['infrastructure', 'external_dependencies'],
    }],
    classifications: [],
    validated_classifications: [{
      startup_id: startupId,
      name: 'Neurotech',
      status: 'classified',
      category: 'ai-native',
      justification: 'A inteligência artificial participa diretamente da proposta de valor.',
      confidence: 'high',
      signals: [{
        type: 'core_ai_dependency',
        description: 'O produto depende de modelos preditivos para gerar suas decisões.',
        sources: [source],
      }],
      evidence_references: [source],
    }],
    claim_validations: [{
      startup_id: startupId,
      claim_key: 'technical_needs:1',
      field: 'technical_needs',
      value: technicalNeed.value,
      status: 'supported',
      justification: 'A necessidade está sustentada pela evidência selecionada.',
      analyzed_sources: [{ ...source, verdict: 'supports' }],
      original_sources: [source],
    }],
    classification_validations: [],
    validated_claims: [],
    rejected_claims: [],
    conflicting_claims: [],
    evidence_gaps: [],
    nvidia_contexts: [{
      startup_id: startupId,
      startup_name: 'Neurotech',
      chunks: [{
        chunk_id: chunkId,
        document_id: '44444444-4444-4444-8444-444444444444',
        content: 'NVIDIA NIM oferece microsserviços otimizados para inferência de IA.',
        title: 'NVIDIA NIM Documentation',
        technology: 'nvidia_nim',
        source_url: 'https://docs.nvidia.com/nim/',
        source_section: 'Overview',
        scores: { hybrid_score: 0.91, reranker_score: 0.96 },
      }],
      sufficiency: { status: 'sufficient', reasons: [] },
      gaps: [],
    }],
    recommendations: [{
      startup_id: startupId,
      startup_name: 'Neurotech',
      technology: 'NVIDIA NIM',
      technical_justification: 'NVIDIA NIM pode apoiar inferência escalável e de baixa latência.',
      business_justification: 'A oportunidade sustenta a evolução de um produto baseado em IA.',
      priority: 'high',
      implementation_complexity: 'medium',
      next_action: 'Realizar um workshop técnico com a NVIDIA e validar um proof of concept.',
      startup_evidence: [{ ...source, field: 'technical_needs', value: technicalNeed.value }],
      nvidia_evidence: [{
        chunk_id: chunkId,
        title: 'NVIDIA NIM Documentation',
        technology: 'nvidia_nim',
        source_url: 'https://docs.nvidia.com/nim/',
        source_section: 'Overview',
      }],
    }],
    briefings: [{
      startup_id: startupId,
      startup_name: 'Neurotech',
      executive_summary: [{
        kind: 'confirmed_fact',
        text: 'A startup aplica IA em decisões de crédito e risco.',
        citation_ids: [sourceId],
      }],
      inception_opportunities: [{
        kind: 'supported_inference',
        text: 'NVIDIA NIM é uma oportunidade para validar inferência escalável.',
        citation_ids: [sourceId, chunkId],
      }],
      uncertainties_and_gaps: [{
        kind: 'uncertainty',
        text: 'A arquitetura atual deve ser confirmada em uma descoberta técnica.',
        citation_ids: [sourceId],
      }],
      business_facts: [{ field: 'product', value: product.value, citation_ids: [sourceId] }],
      technical_gaps: [{
        name: 'Escalabilidade de inferência',
        description: technicalNeed.value,
        citation_ids: [sourceId],
      }],
      missing_sections: [],
      markdown: `# Briefing executivo — Neurotech

> Conteúdo simulado para demonstração.

## Síntese

A startup aplica inteligência artificial em decisões de crédito e risco.

## Oportunidade NVIDIA

Avaliar NVIDIA NIM em um workshop técnico e validar um proof of concept para inferência escalável.`,
    }],
    warnings: ['demo_mode_enabled'],
    errors: [],
    metrics: {
      query_planner_duration_ms: 182,
      retriever_duration_ms: 96,
      extractor_duration_ms: 1240,
      classifier_duration_ms: 880,
      evidence_validator_duration_ms: 710,
      nvidia_rag_duration_ms: 420,
      recommendation_duration_ms: 1360,
      briefing_duration_ms: 940,
    },
  }
}
