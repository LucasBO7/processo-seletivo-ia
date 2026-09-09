import { useState, type FormEvent } from 'react'

type SearchFilters = {
  sector: string
  stage: string
  companySize: string
  location: string
}

const sectors = [
  ['financial_services', 'Serviços financeiros'],
  ['data_and_ai', 'Dados e IA'],
  ['conversational_ai', 'IA conversacional'],
  ['communications', 'Comunicações'],
  ['hr_tech', 'HR Tech'],
  ['accessibility', 'Acessibilidade'],
  ['vertical_saas', 'SaaS vertical'],
  ['events_and_ticketing', 'Eventos e ingressos'],
  ['managed_it_services', 'Serviços gerenciados de TI'],
  ['printing_services', 'Serviços de impressão'],
] as const

const stages = [
  ['pre_seed', 'Pré-seed'],
  ['seed', 'Seed'],
  ['series_a', 'Série A'],
  ['series_b', 'Série B'],
  ['series_c', 'Série C'],
  ['growth', 'Growth'],
  ['late_stage', 'Late stage'],
  ['public', 'Empresa pública'],
  ['acquired', 'Adquirida'],
  ['business_unit', 'Unidade de negócio'],
] as const

const companySizes = [
  ['micro', 'Micro'],
  ['small', 'Pequena'],
  ['medium', 'Média'],
  ['large', 'Grande'],
] as const

function composeSearchQuery(query: string, filters: SearchFilters): string {
  const selected = [
    filters.sector && `setor=${filters.sector}`,
    filters.stage && `estágio=${filters.stage}`,
    filters.companySize && `porte=${filters.companySize}`,
    filters.location.trim() && `localização=${filters.location.trim()}`,
  ].filter(Boolean)
  return selected.length
    ? `${query.trim()}\n\nFiltros explícitos: ${selected.join('; ')}.`
    : query.trim()
}

type SearchFormProps = {
  query: string
  loading: boolean
  onQueryChange: (query: string) => void
  onSubmit: (query: string) => void
}

export function SearchForm({
  query,
  loading,
  onQueryChange,
  onSubmit,
}: SearchFormProps) {
  const [filters, setFilters] = useState<SearchFilters>({
    sector: '',
    stage: '',
    companySize: '',
    location: '',
  })
  const [validation, setValidation] = useState('')

  function updateFilter(field: keyof SearchFilters, value: string) {
    setFilters((current) => ({ ...current, [field]: value }))
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const composed = composeSearchQuery(query, filters)
    if (!query.trim()) {
      setValidation('Descreva quais startups você quer analisar.')
      return
    }
    if (composed.length > 2_000) {
      setValidation('A consulta com os filtros deve ter no máximo 2.000 caracteres.')
      return
    }
    setValidation('')
    onSubmit(composed)
  }

  return (
    <form className="search-form" onSubmit={submit} aria-labelledby="search-title">
      <div className="section-kicker">Nova análise</div>
      <h1 id="search-title">Encontre a próxima oportunidade em IA.</h1>
      <label htmlFor="startup-query">Consulta em linguagem natural</label>
      <textarea
        id="startup-query"
        value={query}
        onChange={(event) => onQueryChange(event.target.value)}
        placeholder="Ex.: startups brasileiras de saúde que usam IA no produto principal"
        maxLength={2_000}
        rows={4}
        aria-describedby="query-help query-error"
        aria-invalid={Boolean(validation)}
        disabled={loading}
      />
      <div className="field-meta">
        <span id="query-help">Seja específico sobre setor, mercado ou tecnologia.</span>
        <span>{query.length}/2.000</span>
      </div>
      <p id="query-error" className="field-error" aria-live="polite">
        {validation}
      </p>

      <fieldset disabled={loading}>
        <legend>Filtros aprovados <span>(opcionais)</span></legend>
        <div className="filter-grid">
          <FilterSelect
            id="sector"
            label="Setor"
            value={filters.sector}
            options={sectors}
            onChange={(value) => updateFilter('sector', value)}
          />
          <FilterSelect
            id="stage"
            label="Estágio"
            value={filters.stage}
            options={stages}
            onChange={(value) => updateFilter('stage', value)}
          />
          <FilterSelect
            id="company-size"
            label="Porte"
            value={filters.companySize}
            options={companySizes}
            onChange={(value) => updateFilter('companySize', value)}
          />
          <div className="field-group">
            <label htmlFor="location">Localização</label>
            <input
              id="location"
              value={filters.location}
              maxLength={120}
              onChange={(event) => updateFilter('location', event.target.value)}
              placeholder="Ex.: São Paulo"
            />
          </div>
        </div>
      </fieldset>

      <button className="primary-button" type="submit" disabled={loading}>
        {loading ? 'Analisando…' : 'Analisar startups'}
      </button>
    </form>
  )
}

type FilterSelectProps = {
  id: string
  label: string
  value: string
  options: ReadonlyArray<readonly [string, string]>
  onChange: (value: string) => void
}

function FilterSelect({ id, label, value, options, onChange }: FilterSelectProps) {
  return (
    <div className="field-group">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Todos</option>
        {options.map(([optionValue, optionLabel]) => (
          <option key={optionValue} value={optionValue}>{optionLabel}</option>
        ))}
      </select>
    </div>
  )
}
