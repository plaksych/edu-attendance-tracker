# Browser Recognition Verification

Run from `frontend` with the main frontend owner's installed test dependencies:

```sh
./node_modules/.bin/tsc --noEmit -p tsconfig.app.json
./node_modules/.bin/vitest run tests/browserRecognition.test.ts tests/browserRecognitionWorker.test.ts tests/browserRecognitionDialog.test.tsx tests/browserRecognitionAssets.test.ts
```

The asset test requires Playwright Chromium. To use an existing Google Chrome
installation, prefix the Vitest command with `BROWSER_TEST_CHANNEL=chrome`.
Required dev dependencies: `vitest`, `@testing-library/react`, `jsdom`, and
`@playwright/test`; package ownership remains with the main frontend agent.

The tests cover geometry, channel layouts, probabilities, finite tensors, NMS,
RGB normalization, signature/size/dimension/duration limits, SHA-256 inventory,
lazy initialization, cancellation, retries, disposal, UI races, media errors,
provenance and local JSON export. Worker and dialog tests mock the runtime
session explicitly; their outputs are NOT inference or accuracy evidence.

The real-browser test builds the worker in memory, serves it under
`/edu-attendance-tracker/`, and loads the actual vendored runtime in dedicated
workers. It rejects or holds model requests deliberately, verifying cold-load
laziness, retries, cancellation and subpath routing without running a model.
Its HTTP server, browser and worker contexts are closed even on failure.
No production files, containers, model weights or heavy inference are launched.

## Opt-In Real-Model Smoke

```sh
BROWSER_TEST_CHANNEL=chrome node tests/browserRecognitionSmoke.mjs
```

Omit the environment variable to use installed Playwright Chromium. This script
does run the existing pinned model, explicitly outside the default test suite.
It uses one headless browser and one WASM thread, builds only the direct harness
in memory, and serves assets on loopback under `/edu-attendance-tracker/`.
The only input is a generated 320x240 canvas with simple colored geometry.
There are no fabricated model/session outputs and no containers/private media.

The latest run produced `browserRecognition-smoke.json` (source hashes, timings,
actual results, request traces and cleanup) and `browserRecognition-smoke.png`.
On 2026-09-23, Chrome 154.0.8037.57 on Apple M1 passed:

- First real inference: 1267.6 ms initialization, 940.9 ms worker preprocessing /
  inference / postprocessing, 960.9 ms client detect wall time, 0 people.
- Retry after cancellation: 998.5 ms initialization, 940.1 ms worker processing,
  949.3 ms detect wall time, 0 people. Average confidence is null for both.
- Real vendored `ort-wasm-simd-threaded.jsep.wasm` fetched with HTTP 200,
  `application/wasm`, 21,872,216 bytes; ONNX hash verified before session creation.
- Initial load: no worker/runtime/model requests. Intentional model HTTP 503,
  cancelled initialization, and cancellation after real `run()` entry all recover.
  A diagnostic wrapper announces `run()` entry then calls the original unchanged;
  this does not claim interruption at a specific WASM kernel instruction.
- 22 requests, all allowlisted same-origin static GETs with no query/body;
  zero upload bytes, unexpected requests, page errors or console errors.
- All worker contexts, browser and server closed after the run.

The first real run exposed WASM sigmoid roundoff of `-5.960464477539063e-8`
in a non-person score. Strict `[0,1]` rejection incorrectly failed that output.
The decoder now permits only a bounded `1e-6` excursion and clamps the selected
person score; regression tests still reject nonfinite and materially invalid
probabilities. This is a real-smoke-discovered fix, not a mocked inference result.

These local timings are observations, not a benchmark. Zero detections on this
synthetic negative input does not establish person-detection or classroom quality.

## Integrated UI Smoke

```sh
BROWSER_TEST_CHANNEL=chrome node tests/browserRecognitionUiSmoke.mjs
```

This optional test needs an installed `ffmpeg` with libx264 and Chrome (or
Playwright Chromium with the environment variable omitted). It builds the full
current static frontend in memory under `/edu-attendance-tracker/`, with the
actual routing, styles, recognition page and LocalRecognitionDialog. It does
not import a custom dialog, mock inference, call the recognizer directly, write
to either shared dist directory, use the other agent's dev server, or execute
the shared Vite config's filesystem cleanup hooks.

The script generates a 320x240 blank PNG and a six-second, 4 fps white MP4 with
one encoder/filter thread. It uses one browser and one WASM thread. Through the
real file input and buttons it checks:

- No runtime/model loading on dialog opening or file selection.
- Visible HTTP 503 error and enabled retry; Stop during held initialization,
  worker termination, and successful actual-model retry.
- Actual PNG recognition and decoded-video frame recognition; local JSON
  downloads retain browser provenance, model hash, elapsed time and parameters.
- Actual video playback/sampling, Stop, paused media, worker closure, and no
  restarted sampling after another interval.
- Clear releases all tracked main-thread object URLs; close/reopen is empty.
- A full network trace accepts only exact-allowlist static GETs on loopback;
  no query/body uploads, API traffic, external hosts or derived-media requests.
- Desktop 1440x1000 and responsive mobile 390x844 controls/result screenshots,
  no horizontal overflow, and preserved 4:3 media geometry. Mobile is a viewport
  check in desktop Chrome, not physical-device certification.

Generated evidence is `browserRecognition-ui-smoke.json` with full downloaded
results, trace, worker lifecycle, source/build hashes, timings and screenshot
paths. Generated inputs are `browserRecognition-ui-input.png` and
`browserRecognition-ui-input.mp4`. Screenshots are `browserRecognition-ui-*.png`;
`*-controls.png` shows the dialog top and the other view shows the result.
The surrounding static example remains a fixture; assertions/export collection
are scoped to the local dialog and require `browser_inference`, never that fixture.

The integration is execution evidence for synthetic negative inputs only. It
does not establish accuracy, video-wide unique-person tracking, live-server
authorization, real-device compatibility or production CSP suitability.

## Required Before Release

- Run real inference on an authorized small image and a short video with the
  pinned model, both in Vite dev and the production subpath build. Verify WASM
  MIME/CSP and browser support on the supported desktop/mobile browsers.
- Repeat the successful-analysis network trace for the integrated image/video UI
  in supported browsers: the direct-worker synthetic smoke already verifies no
  outgoing media, frames, tensors, detections or derived data on its tested path.
- Check pause/seek/stop/close/reopen, failed runtime/WASM/model downloads, slow
  devices, unsupported codecs, memory cleanup, and visual alignment on portrait
  and landscape media. Current file/dimension guards are not a replacement for
  the browser's native decoder security; dimensions are checked after decoding.
- Evaluate counting quality against a separately annotated classroom dataset.
  Confidence is not accuracy; no classroom accuracy claim is currently justified.
- Resolve original model provenance and AGPL/redistribution obligations. The
  manifest pins existing bytes but does not establish permission to redistribute.
