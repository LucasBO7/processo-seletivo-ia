export type AnalysisOutcome =
  | 'success'
  | 'needs_clarification'
  | 'invalid_query'
  | 'no_results'
  | 'temporarily_unavailable'
  | 'internal_failure'

export type ApiError = {
  code: string
  message: string
  node?: string | null
}

export type SourceLink = {
  startup_id: string
  source_id: string
  source_url: string
}

export type Fact = {
  value: string
  sources: SourceLink[]
}

export type StartupProfile = {
  startup_id: string
  name: string
  product?: Fact | null
  business_model?: Fact | null
  sector?: Fact | null
  target_audience?: Fact | null
  ai_use_cases: Fact[]
  technologies: Fact[]
  infrastructure: Fact[]
  external_dependencies: Fact[]
  technical_needs: Fact[]
  claims: Fact[]
  unknown_fields: string[]
}

export type Classification = {
  startup_id: string
  name: string
  status: 'classified' | 'uncertain'
  category: 'non-ai' | 'ai-enabled' | 'ai-native' | null
  justification: string
  confidence: 'low' | 'medium' | 'high'
  signals: Array<{
    type: string
    description: string
    sources: SourceLink[]
  }>
  evidence_references: SourceLink[]
}

export type ClaimValidation = {
  startup_id: string
  claim_key: string
  field?: string
  value?: string
  category?: Classification['category']
  status: 'supported' | 'unsupported' | 'conflicting' | 'insufficient'
  justification: string
  analyzed_sources: Array<SourceLink & { verdict: string }>
  original_sources?: SourceLink[]
}

export type QueryPlan = {
  status: 'ready' | 'needs_clarification' | 'invalid'
  normalized_query: string
  filters: {
    sectors: string[]
    company_sizes: Array<string | { minimum: number; maximum: number | null }>
    stages: string[]
    locations: string[]
    keywords: string[]
    ai_usage_signals: string[]
  }
  analysis_strategy: {
    mode: 'targeted' | 'exploratory' | 'comparative'
    objectives: string[]
    rationale: string
  }
  ambiguities: string[]
  clarification_questions: string[]
  unresolved_filters: Array<{ field: string; requested_value: string }>
  filter_suggestions: Array<{
    field: string
    requested_value: string
    options: string[]
  }>
}

export type CandidateStartup = {
  startup_id: string
  name: string
  score: number | null
}

export type SelectedSource = SourceLink & {
  title: string
  excerpt: string | null
}

export type NvidiaScores = {
  hybrid_score: number
  reranker_score: number | null
}

export type NvidiaChunk = {
  chunk_id: string
  document_id: string
  content: string
  title: string
  technology: string
  source_url: string
  source_section: string | null
  scores: NvidiaScores
}

export type NvidiaContext = {
  startup_id: string
  startup_name: string
  chunks: NvidiaChunk[]
  sufficiency: {
    status: 'sufficient' | 'insufficient'
    reasons: string[]
  }
  gaps: Array<{ code: string; message: string }>
}

export type Recommendation = {
  startup_id: string
  startup_name: string
  technology: string
  technical_justification: string
  business_justification: string
  priority: 'low' | 'medium' | 'high'
  implementation_complexity: 'low' | 'medium' | 'high'
  next_action: string
  startup_evidence: Array<SourceLink & { field: string; value: string }>
  nvidia_evidence: Array<{
    chunk_id: string
    title: string
    technology: string
    source_url: string
    source_section: string | null
  }>
}

export type BriefingStatement = {
  kind: 'confirmed_fact' | 'supported_inference' | 'uncertainty' | 'gap'
  text: string
  citation_ids: string[]
}

export type Briefing = {
  startup_id: string
  startup_name: string
  executive_summary: BriefingStatement[]
  inception_opportunities: BriefingStatement[]
  uncertainties_and_gaps: BriefingStatement[]
  business_facts: Array<{ field: string; value: string; citation_ids: string[] }>
  technical_gaps: Array<{
    name: string
    description: string
    citation_ids: string[]
  }>
  missing_sections: string[]
  markdown: string
}

export type SearchResponse = {
  outcome: AnalysisOutcome
  query_plan: QueryPlan | null
  candidate_startups: CandidateStartup[]
  selected_sources: SelectedSource[]
  structured_profiles: StartupProfile[]
  classifications: Classification[]
  validated_profiles: StartupProfile[]
  validated_classifications: Classification[]
  claim_validations: ClaimValidation[]
  classification_validations: ClaimValidation[]
  validated_claims: ClaimValidation[]
  rejected_claims: ClaimValidation[]
  conflicting_claims: ClaimValidation[]
  evidence_gaps: ClaimValidation[]
  nvidia_contexts: NvidiaContext[]
  recommendations: Recommendation[]
  briefings: Briefing[]
  warnings: string[]
  errors: ApiError[]
  metrics: Record<string, number>
}
