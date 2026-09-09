import type { CandidateStartup } from '../api/analysis-types'

type StartupListProps = {
  startups: CandidateStartup[]
  selectedId: string
  onSelect: (startupId: string) => void
}

export function StartupList({ startups, selectedId, onSelect }: StartupListProps) {
  return (
    <aside className="startup-list" aria-labelledby="results-title">
      <p className="section-kicker">Resultados</p>
      <h2 id="results-title">{startups.length} startup{startups.length === 1 ? '' : 's'}</h2>
      <ul className="startup-list__items">
        {startups.map((startup, index) => (
          <li key={startup.startup_id}>
            <button
              type="button"
              className={startup.startup_id === selectedId ? 'startup-card is-selected' : 'startup-card'}
              aria-pressed={startup.startup_id === selectedId}
              onClick={() => onSelect(startup.startup_id)}
            >
              <span className="startup-card__index">{String(index + 1).padStart(2, '0')}</span>
              <strong>{startup.name}</strong>
              <span>{startup.score === null ? 'Score não disponível' : `${Math.round(startup.score * 100)}% de aderência`}</span>
            </button>
          </li>
        ))}
      </ul>
    </aside>
  )
}
