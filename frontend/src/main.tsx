import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, HashRouter } from 'react-router-dom'
import App from './App'
import { isStaticData } from './api/client'
import './index.css'
import '@fontsource-variable/golos-text'
import '@fontsource-variable/onest'
import './production.css'

const basename =
  import.meta.env.BASE_URL === '/'
    ? undefined
    : import.meta.env.BASE_URL.replace(/\/$/, '')

const application = isStaticData ? (
  <HashRouter>
    <App />
  </HashRouter>
) : (
  <BrowserRouter basename={basename}>
    <App />
  </BrowserRouter>
)

createRoot(document.getElementById('root')!).render(<StrictMode>{application}</StrictMode>)
