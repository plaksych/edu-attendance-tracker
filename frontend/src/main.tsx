import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, HashRouter } from 'react-router-dom'
import App from './App'
import { isStaticData } from './api/client'
import './index.css'

const basename =
  import.meta.env.BASE_URL === '/'
    ? undefined
    : import.meta.env.BASE_URL.replace(/\/$/, '')

const future = { v7_startTransition: true, v7_relativeSplatPath: true }

const application = isStaticData ? (
  <HashRouter future={future}>
    <App />
  </HashRouter>
) : (
  <BrowserRouter basename={basename} future={future}>
    <App />
  </BrowserRouter>
)

createRoot(document.getElementById('root')!).render(<StrictMode>{application}</StrictMode>)
