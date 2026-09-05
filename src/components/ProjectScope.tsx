type ProjectScopeProps = {
  title: string
  items: string[]
  tone: 'current' | 'future'
}

export function ProjectScope({ title, items, tone }: ProjectScopeProps) {
  return (
    <section className={`scope-card scope-card--${tone}`}>
      <p className="scope-card__eyebrow">
        {tone === 'current' ? 'Agora' : 'Próxima especificação'}
      </p>
      <h2>{title}</h2>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  )
}
