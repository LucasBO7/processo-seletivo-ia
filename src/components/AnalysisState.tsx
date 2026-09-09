import type { ApiError, QueryPlan, SearchResponse } from '../api/analysis-types'

const pipelineSteps = [
  'Planejamento da consulta',
  'Recuperação de startups',
  'Extração do perfil',
  'Classificação de IA',
  'Validação de evidências',
  'Contexto NVIDIA',
  'Recomendações',
  'Briefing executivo',
]

export function LoadingState() {
  return (
    <section className="state-panel loading-panel" aria-live="polite" aria-busy="true">
      <span className="spinner" aria-hidden="true" />
      <div>
        <p className="section-kicker">Pipeline em execução</p>
        <h2>Analisando evidências e oportunidades</h2>
        <p>A requisição permanece aberta enquanto os agentes processam a consulta.</p>
        <ol className="pipeline-steps">
          {pipelineSteps.map((step) => <li key={step}>{step}</li>)}
        </ol>
      </div>
    </section>
  )
}

type AnalysisStateProps = {
  response: SearchResponse | null
  networkError: string
  onUseQuestion: (question: string) => void
}

export function AnalysisState({ response, networkError, onUseQuestion }: AnalysisStateProps) {
  if (networkError) {
    return <MessageState tone="error" title="Não foi possível concluir a análise" text={networkError} />
  }
  if (!response) return null

  if (response.outcome === 'success') {
    return (
      <MessageState
        tone="success"
        title="Análise concluída"
        text={`${response.candidate_startups.length} startup${response.candidate_startups.length === 1 ? '' : 's'} encontrada${response.candidate_startups.length === 1 ? '' : 's'}.`}
      />
    )
  }

  if (response.outcome === 'needs_clarification') {
    return <ClarificationState plan={response.query_plan} onUseQuestion={onUseQuestion} />
  }

  const states: Record<Exclude<SearchResponse['outcome'], 'success' | 'needs_clarification'>, [string, string, 'neutral' | 'warning' | 'error']> = {
    invalid_query: ['Revise a consulta', errorText(response.errors, 'A consulta não pôde ser validada.'), 'warning'],
    no_results: ['Nenhuma startup encontrada', 'Tente ampliar a consulta ou remover alguns filtros.', 'neutral'],
    temporarily_unavailable: ['Serviço temporariamente indisponível', errorText(response.errors, 'Uma dependência da análise não respondeu. Tente novamente em instantes.'), 'warning'],
    internal_failure: ['A análise não pôde ser concluída', errorText(response.errors, 'Ocorreu uma falha interna. Tente novamente.'), 'error'],
  }
  const [title, text, tone] = states[response.outcome]
  return <MessageState title={title} text={text} tone={tone} />
}

function errorText(errors: ApiError[], fallback: string): string {
  return errors.map((error) => error.message).filter(Boolean).join(' ') || fallback
}

function ClarificationState({ plan, onUseQuestion }: { plan: QueryPlan | null; onUseQuestion: (question: string) => void }) {
  const questions = plan?.clarification_questions ?? []
  return (
    <section className="state-panel state-panel--warning" aria-live="polite">
      <p className="section-kicker">Precisamos de mais contexto</p>
      <h2>Sua consulta tem mais de uma interpretação</h2>
      {plan?.ambiguities.map((ambiguity) => <p key={ambiguity}>{ambiguity}</p>)}
      {questions.length > 0 && (
        <div className="question-list">
          <h3>Perguntas para esclarecer</h3>
          {questions.map((question) => (
            <button key={question} type="button" onClick={() => onUseQuestion(question)}>
              {question}
            </button>
          ))}
        </div>
      )}
    </section>
  )
}

function MessageState({ title, text, tone }: { title: string; text: string; tone: 'success' | 'neutral' | 'warning' | 'error' }) {
  return (
    <section className={`state-panel state-panel--${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      <h2>{title}</h2>
      <p>{text}</p>
    </section>
  )
}
