import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { HomePage } from './pages/HomePage'
import './styles/global.css'

const rootElement = document.getElementById('root')

if (!rootElement) {
  throw new Error('Elemento raiz da aplicação não encontrado.')
}

createRoot(rootElement).render(
  <StrictMode>
    <HomePage />
  </StrictMode>,
)
