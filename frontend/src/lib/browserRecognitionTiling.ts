export interface Box {
  x: number
  y: number
  width: number
  height: number
  confidence: number
}

export interface Tile { x: number; y: number; width: number; height: number }
export interface Candidate extends Box { pass: number }

export function validateFrame(width: number, height: number): void {
  if (![width, height].every((n) => Number.isSafeInteger(n) && n > 0 && n <= 8192)
    || width * height > 16_000_000) {
    throw new Error('Размер кадра должен быть не более 16 Мп и 8192 пикселей по стороне')
  }
}

function positions(length: number, size: number): number[] {
  const last = Math.max(0, length - size)
  const count = Math.ceil(last / (size * 0.75))
  return count === 0 ? [0] : Array.from({ length: count + 1 }, (_, i) => Math.round(last * i / count))
}

export function planTiles(width: number, height: number): Tile[] {
  validateFrame(width, height)
  if (Math.max(width, height) <= 640) return []
  let size = 480
  // Bound runtime and memory even for very large uploads.
  while (positions(width, size).length * positions(height, size).length > 24) size += 32
  return positions(height, size).flatMap((y) => positions(width, size).map((x) => ({
    x, y, width: Math.min(size, width), height: Math.min(size, height),
  })))
}

export function isCompleteInTile(box: Box, tile: Tile, width: number, height: number): boolean {
  const margin = 4
  return !(tile.x > 0 && box.x <= margin)
    && !(tile.y > 0 && box.y <= margin)
    && !(tile.x + tile.width < width && box.x + box.width >= tile.width - margin)
    && !(tile.y + tile.height < height && box.y + box.height >= tile.height - margin)
}

export function mergeDetections(candidates: Candidate[]): Box[] {
  const kept: Candidate[] = []
  for (const candidate of [...candidates].sort((a, b) => b.confidence - a.confidence)) {
    if (![candidate.x, candidate.y, candidate.width, candidate.height, candidate.confidence].every(Number.isFinite)
      || candidate.width <= 0 || candidate.height <= 0) continue
    if (kept.every((other) => !sameDetection(candidate, other))) kept.push(candidate)
  }
  return kept.map(({ pass: _pass, ...box }) => box)
}

function sameDetection(a: Candidate, b: Candidate): boolean {
  const intersection = Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x))
    * Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y))
  const areaA = a.width * a.height
  const areaB = b.width * b.height
  if (intersection / (areaA + areaB - intersection) >= 0.45) return true
  // Cross-scale head/torso boxes can have low IoU. Require aligned tops and
  // centres before suppressing a contained box, not merely overlapping people.
  return a.pass !== b.pass && intersection / Math.min(areaA, areaB) >= 0.8
    && Math.abs(a.y - b.y) <= 0.25 * Math.min(a.height, b.height)
    && Math.abs(a.x + a.width / 2 - b.x - b.width / 2) <= 0.35 * Math.min(a.width, b.width)
}
