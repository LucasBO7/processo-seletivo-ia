import { ProjectScope } from '../components/ProjectScope'

const currentScope = [
  'Documentação orientada por especificações',
  'Diagramas do problema e do pipeline',
  'Fundação do frontend React',
]

const futureScope = [
  'Arquitetura do backend',
  'Orquestração multiagente',
  'Persistência e recuperação de conhecimento',
]

export function HomePage() {
  return (
    <main>
      <section className="hero">
        <div className="hero__glow" aria-hidden="true" />
        <nav className="hero__nav" aria-label="Identificação do projeto">
          <span className="brand-mark" aria-hidden="true">
            IA
          </span>
          <span>Inteli Academy</span>
          <span className="status-pill">Fundação</span>
        </nav>

        <div className="hero__content">
          <p className="hero__eyebrow">NVIDIA STARTUP AI RADAR</p>
          <h1>Inteligência para encontrar a próxima startup AI-native.</h1>
          <p className="hero__summary">
            Uma plataforma em formação para analisar evidências, diagnosticar
            maturidade técnica e orientar recomendações da stack NVIDIA.
          </p>
          <a className="hero__link" href="/README.md">
            Conhecer a especificação <span aria-hidden="true">→</span>
          </a>
        </div>
      </section>

      <section className="scope" aria-labelledby="scope-title">
        <div className="section-heading">
          <p>Escopo controlado</p>
          <h2 id="scope-title">Uma fundação clara antes da arquitetura.</h2>
        </div>

        <div className="scope-grid">
          <ProjectScope
            title="Incluído nesta entrega"
            items={currentScope}
            tone="current"
          />
          <ProjectScope
            title="Reservado para depois"
            items={futureScope}
            tone="future"
          />
        </div>
      </section>
    </main>
  )
}
