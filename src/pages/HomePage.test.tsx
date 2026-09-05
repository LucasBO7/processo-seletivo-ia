import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { HomePage } from './HomePage'

describe('HomePage', () => {
  it('comunica o produto e os limites desta entrega', () => {
    render(<HomePage />)

    expect(
      screen.getByRole('heading', {
        name: /inteligência para encontrar a próxima startup ai-native/i,
      }),
    ).toBeInTheDocument()
    expect(screen.getByText('Incluído nesta entrega')).toBeInTheDocument()
    expect(screen.getByText('Arquitetura do backend')).toBeInTheDocument()
  })
})
