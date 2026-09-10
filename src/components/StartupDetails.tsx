import type {
  BriefingStatement,
  ClaimValidation,
  Fact,
  SearchResponse,
  SourceLink,
} from '../api/analysis-types'

const fieldLabels: Record<string, string> = {
  product: 'Produto',
  business_model: 'Modelo de negócio',
  sector: 'Setor',
  target_audience: 'Público-alvo',
  ai_use_cases: 'Casos de uso de IA',
  technologies: 'Tecnologias',
  infrastructure: 'Infraestrutura',
  external_dependencies: 'Dependências externas',
  technical_needs: 'Necessidades técnicas',
  claims: 'Outras afirmações',
}

const maturityLabels: Record<string, string> = {
  'ai-native': 'AI-native',
  'ai-enabled': 'AI-enabled',
  'non-ai': 'Não baseada em IA',
}

const levelLabels: Record<string, string> = {
  low: 'Baixa',
  medium: 'Média',
  high: 'Alta',
}

type StartupDetailsProps = {
  response: SearchResponse
  startupId: string
}

export function StartupDetails({ response, startupId }: StartupDetailsProps) {
  const candidate = response.candidate_startups.find((item) => item.startup_id === startupId)
  const profile = response.validated_profiles.find((item) => item.startup_id === startupId)
    ?? response.structured_profiles.find((item) => item.startup_id === startupId)
  const classification = response.validated_classifications.find((item) => item.startup_id === startupId)
    ?? response.classifications.find((item) => item.startup_id === startupId)
  const validations = response.claim_validations.filter((item) => item.startup_id === startupId)
  const evidenceGaps = response.evidence_gaps.filter((item) => item.startup_id === startupId)
  const sources = response.selected_sources.filter((item) => item.startup_id === startupId)
  const context = response.nvidia_contexts.find((item) => item.startup_id === startupId)
  const recommendations = response.recommendations.filter((item) => item.startup_id === startupId)
  const briefing = response.briefings.find((item) => item.startup_id === startupId)

  if (!candidate) return null

  return (
    <article className="startup-details" aria-labelledby="startup-title">
      <header className="details-header">
        <div>
          <p className="section-kicker">Análise selecionada</p>
          <h2 id="startup-title">{candidate.name}</h2>
        </div>
        {briefing && <ExportButton name={briefing.startup_name} markdown={briefing.markdown} />}
      </header>

      <section className="detail-section" aria-labelledby="profile-title">
        <SectionTitle id="profile-title" number="01" title="Perfil da startup" />
        {profile ? <ProfileFacts profile={profile} /> : <EmptyText text="Perfil não disponível para esta startup." />}
      </section>

      <section className="detail-section" aria-labelledby="maturity-title">
        <SectionTitle id="maturity-title" number="02" title="Maturidade de IA" />
        {classification ? (
          <div className="maturity-card">
            <div>
              <span className="tag">{classification.category ? maturityLabels[classification.category] : 'Incerta'}</span>
              <span className="muted">Confiança {levelLabels[classification.confidence].toLowerCase()}</span>
            </div>
            <p>{classification.justification}</p>
            {classification.signals.length > 0 && (
              <ul>{classification.signals.map((signal) => <li key={`${signal.type}-${signal.description}`}>{signal.description}</li>)}</ul>
            )}
          </div>
        ) : <EmptyText text="Classificação não disponível para esta startup." />}
      </section>

      <section className="detail-section" aria-labelledby="evidence-title">
        <SectionTitle id="evidence-title" number="03" title="Evidências e validação" />
        {validations.length > 0 ? (
          <div className="stack-list">{validations.map((validation) => <ValidationCard key={validation.claim_key} validation={validation} />)}</div>
        ) : <EmptyText text="Nenhuma validação de evidência foi retornada." />}
        {sources.length > 0 && (
          <div className="source-list">
            <h3>Fontes da startup</h3>
            {sources.map((source) => (
              <div key={source.source_id} className="source-row">
                <ExternalLink url={source.source_url}>{source.title}</ExternalLink>
                {source.excerpt && <p>{source.excerpt}</p>}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="detail-section" aria-labelledby="gaps-title">
        <SectionTitle id="gaps-title" number="04" title="Gaps técnicos" />
        {briefing?.technical_gaps.length ? (
          <div className="stack-list">{briefing.technical_gaps.map((gap) => (
            <div className="info-card" key={`${gap.name}-${gap.description}`}><h3>{gap.name}</h3><p>{gap.description}</p></div>
          ))}</div>
        ) : evidenceGaps.length ? (
          <div className="stack-list">{evidenceGaps.map((gap) => <ValidationCard key={gap.claim_key} validation={gap} />)}</div>
        ) : <EmptyText text="Nenhum gap técnico foi registrado." />}
      </section>

      <section className="detail-section" aria-labelledby="nvidia-title">
        <SectionTitle id="nvidia-title" number="05" title="Contexto NVIDIA" />
        {context ? (
          <>
            <p className="context-status">Contexto {context.sufficiency.status === 'sufficient' ? 'suficiente' : 'insuficiente'}.</p>
            {context.gaps.map((gap) => <p key={gap.code} className="muted">{gap.message}</p>)}
            <div className="source-list">
              {context.chunks.map((chunk) => (
                <div className="source-row" key={chunk.chunk_id}>
                  <ExternalLink url={chunk.source_url} requireHttps>{chunk.title}</ExternalLink>
                  <span className="tag tag--quiet">{chunk.technology}</span>
                  <p>{chunk.content}</p>
                </div>
              ))}
            </div>
          </>
        ) : <EmptyText text="Nenhum contexto NVIDIA foi recuperado." />}
      </section>

      <section className="detail-section" aria-labelledby="recommendations-title">
        <SectionTitle id="recommendations-title" number="06" title="Recomendações NVIDIA" />
        {recommendations.length ? <div className="recommendation-grid">{recommendations.map((item) => (
          <article className="recommendation-card" key={`${item.technology}-${item.next_action}`}>
            <div className="recommendation-card__top"><h3>{item.technology}</h3><span className={`priority priority--${item.priority}`}>Prioridade {levelLabels[item.priority].toLowerCase()}</span></div>
            <p><strong>Justificativa técnica:</strong> {item.technical_justification}</p>
            <p><strong>Impacto no negócio:</strong> {item.business_justification}</p>
            <p><strong>Próxima ação:</strong> {item.next_action}</p>
            <p className="muted">Complexidade {levelLabels[item.implementation_complexity].toLowerCase()}</p>
            <div className="inline-links">
              {item.startup_evidence.map((source) => <ExternalLink key={source.source_id} url={source.source_url}>Evidência da startup</ExternalLink>)}
              {item.nvidia_evidence.map((source) => <ExternalLink key={source.chunk_id} url={source.source_url} requireHttps>Fonte NVIDIA</ExternalLink>)}
            </div>
          </article>
        ))}</div> : <EmptyText text={missingRecommendationText(response, startupId)} />}
      </section>

      <section className="detail-section" aria-labelledby="briefing-title">
        <SectionTitle id="briefing-title" number="07" title="Briefing executivo" />
        {briefing ? (
          <div className="briefing">
            <StatementList title="Síntese" statements={briefing.executive_summary} />
            <StatementList title="Oportunidades Inception" statements={briefing.inception_opportunities} />
            <StatementList title="Incertezas e lacunas" statements={briefing.uncertainties_and_gaps} />
            {briefing.missing_sections.length > 0 && <p className="muted">Seções sem dados: {briefing.missing_sections.join(', ')}.</p>}
            <details>
              <summary>Ver Markdown original</summary>
              <pre>{briefing.markdown}</pre>
            </details>
          </div>
        ) : <EmptyText text={missingBriefingText(response, startupId)} />}
      </section>
    </article>
  )
}

function ProfileFacts({ profile }: { profile: SearchResponse['structured_profiles'][number] }) {
  const entries: Array<[string, Fact[]]> = [
    ['product', profile.product ? [profile.product] : []],
    ['business_model', profile.business_model ? [profile.business_model] : []],
    ['sector', profile.sector ? [profile.sector] : []],
    ['target_audience', profile.target_audience ? [profile.target_audience] : []],
    ['ai_use_cases', profile.ai_use_cases],
    ['technologies', profile.technologies],
    ['infrastructure', profile.infrastructure],
    ['external_dependencies', profile.external_dependencies],
    ['technical_needs', profile.technical_needs],
  ]
  const available = entries.filter(([, facts]) => facts.length > 0)
  return available.length ? <dl className="facts-grid">{available.map(([field, facts]) => (
    <div key={field}><dt>{fieldLabels[field]}</dt><dd>{facts.map((fact) => fact.value).join(' · ')}</dd></div>
  ))}</dl> : <EmptyText text="O perfil não contém fatos disponíveis." />
}

function ValidationCard({ validation }: { validation: ClaimValidation }) {
  const urls = [...(validation.original_sources ?? []), ...validation.analyzed_sources]
  return <div className="info-card"><div className="info-card__top"><h3>{fieldLabels[validation.field ?? ''] ?? validation.claim_key}</h3><span className={`evidence-status evidence-status--${validation.status}`}>{validation.status}</span></div><p>{validation.value ?? validation.justification}</p><div className="inline-links">{uniqueSources(urls).map((source) => <ExternalLink key={`${source.source_id}-${source.source_url}`} url={source.source_url}>Abrir evidência</ExternalLink>)}</div></div>
}

function uniqueSources(sources: SourceLink[]): SourceLink[] {
  return sources.filter((source, index) => sources.findIndex((item) => item.source_url === source.source_url) === index)
}

function StatementList({ title, statements }: { title: string; statements: BriefingStatement[] }) {
  if (!statements.length) return null
  return <div className="statement-list"><h3>{title}</h3><ul>{statements.map((statement) => <li key={`${statement.kind}-${statement.text}`}><span className="tag tag--quiet">{statement.kind.replaceAll('_', ' ')}</span>{statement.text}</li>)}</ul></div>
}

function safeUrl(url: string, requireHttps = false): string | null {
  try {
    const parsed = new URL(url)
    if (requireHttps ? parsed.protocol !== 'https:' : !['http:', 'https:'].includes(parsed.protocol)) return null
    return parsed.href
  } catch {
    return null
  }
}

function ExternalLink({ url, requireHttps = false, children }: { url: string; requireHttps?: boolean; children: string }) {
  const href = safeUrl(url, requireHttps)
  return href ? <a className="external-link" href={href} target="_blank" rel="noopener noreferrer">{children}<span aria-hidden="true"> ↗</span></a> : <span className="muted">Fonte indisponível</span>
}

function ExportButton({ name, markdown }: { name: string; markdown: string }) {
  function download() {
    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    const filename = name.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-zA-Z0-9_-]+/g, '-').replace(/^-|-$/g, '').toLowerCase() || 'startup'
    link.href = url
    link.download = `briefing-${filename}.md`
    link.click()
    URL.revokeObjectURL(url)
  }
  return <button type="button" className="secondary-button" onClick={download}>Exportar briefing (.md)</button>
}

function SectionTitle({ id, number, title }: { id: string; number: string; title: string }) {
  return <div className="detail-title"><span>{number}</span><h3 id={id}>{title}</h3></div>
}

function EmptyText({ text }: { text: string }) {
  return <p className="empty-text">{text}</p>
}

function missingRecommendationText(response: SearchResponse, startupId: string): string {
  const errorNodes = new Set(response.errors.map((error) => error.node))
  const context = response.nvidia_contexts.find((item) => item.startup_id === startupId)
  if (errorNodes.has('evidence_validator')) {
    return 'A validação de evidências ficou indisponível e não liberou dados suficientes para recomendar.'
  }
  if (errorNodes.has('recommendation')) {
    return 'O agente de recomendação ficou indisponível ou não produziu uma saída válida.'
  }
  if (!context || context.sufficiency.status !== 'sufficient') {
    return 'O contexto NVIDIA recuperado não foi suficiente para sustentar uma recomendação.'
  }
  if (response.warnings.includes('recommendation_no_identified_need')) {
    return 'Nenhuma necessidade técnica validada foi identificada para relacionar a uma tecnologia NVIDIA.'
  }
  if (response.warnings.includes('recommendation_no_compatible_match')) {
    return 'Nenhuma tecnologia recuperada apresentou correspondência validada com as necessidades identificadas.'
  }
  return 'Nenhuma recomendação rastreável foi produzida para esta startup.'
}

function missingBriefingText(response: SearchResponse, startupId: string): string {
  if (response.errors.some((error) => error.node === 'briefing')) {
    return 'O agente de briefing ficou indisponível ou não produziu uma saída válida.'
  }
  if (!response.recommendations.some((item) => item.startup_id === startupId)) {
    return 'O briefing depende de pelo menos uma recomendação NVIDIA válida para esta startup.'
  }
  return 'O briefing executivo não pôde ser produzido para esta startup.'
}
