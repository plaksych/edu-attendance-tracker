import { getBrowserRecognizer, releaseBrowserRecognizer } from '../src/lib/browserRecognition'

// Test-only entry. Never imported by the application.
Object.assign(window, { browserRecognitionTest: { get: getBrowserRecognizer, release: releaseBrowserRecognizer } })
