// Raw classic worker: preserves the vendored UMD runtime's global `ort`.
// Vite bundles the processing module separately for both dev and build.
self.onmessage = async (event) => {
  const { id, type, baseUrl, moduleUrl } = event.data
  if (type !== 'init') return
  self.onmessage = null
  try {
    importScripts(new URL('ort/ort.min.js', baseUrl).href)
    await import(moduleUrl)
    self.onmessage(event)
  } catch (error) {
    self.postMessage({ id, error: `Не удалось загрузить локальный движок: ${error.message || String(error)}` })
  }
}
