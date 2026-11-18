import test from 'node:test'
import assert from 'node:assert/strict'
import { planTiles, isCompleteInTile, mergeDetections, validateFrame } from '../src/lib/browserRecognitionTiling.ts'

const box = (overrides = {}) => ({ x: 30, y: 40, width: 100, height: 180, confidence: 0.8, pass: 0, ...overrides })

test('small inputs need no extra inference', () => {
  assert.deepEqual(planTiles(640, 360), [])
})

test('tiles cover landscape, portrait and large images within a fixed budget', () => {
  for (const [width, height] of [[1920, 1080], [1080, 1920], [4000, 4000], [8192, 100], [641, 10]]) {
    const tiles = planTiles(width, height)
    assert.ok(tiles.length <= 24)
    for (const tile of tiles) {
      assert.ok(tile.x >= 0 && tile.y >= 0)
      assert.ok(tile.x + tile.width <= width && tile.y + tile.height <= height)
    }
    for (let y = 0; y < height; y += 17) {
      for (let x = 0; x < width; x += 17) {
        assert.ok(tiles.some((t) => x >= t.x && x < t.x + t.width && y >= t.y && y < t.y + t.height))
      }
    }
    assert.ok(tiles.some((t) => t.x + t.width === width && t.y + t.height === height))
  }
})

test('reject invalid dimensions before allocating a canvas', () => {
  for (const [w, h] of [[0, 10], [NaN, 100], [Infinity, 10], [100.5, 10], [5000, 5000], [9000, 1]]) {
    assert.throws(() => validateFrame(w, h))
  }
})

test('discard cropped bodies on internal tile borders, preserve image edges', () => {
  const tile = { x: 360, y: 300, width: 480, height: 480 }
  for (const partial of [box({ x: 0 }), box({ y: 1 }), box({ x: 400 }), box({ y: 400 })]) {
    assert.equal(isCompleteInTile(partial, tile, 1920, 1080), false)
  }
  assert.equal(isCompleteInTile(box(), tile, 1920, 1080), true)
  assert.equal(isCompleteInTile(box({ x: 0, y: 0 }), { ...tile, x: 0, y: 0 }, 1920, 1080), true)
  assert.equal(isCompleteInTile(box({ x: 400 }), { ...tile, x: 1440 }, 1920, 1080), true)
})

test('duplicate boxes keep the strongest result without mutating candidates', () => {
  const input = [box({ confidence: 0.4 }), box({ pass: 1, confidence: 0.9, x: 32 })]
  const copy = structuredClone(input)
  const output = mergeDetections(input)
  assert.equal(output.length, 1)
  assert.equal(output[0].confidence, 0.9)
  assert.equal('pass' in output[0], false)
  assert.deepEqual(input, copy)
})

test('aligned head and torso from different scales count only once', () => {
  assert.equal(mergeDetections([box(), box({ x: 55, y: 42, width: 50, height: 50, pass: 1 })]).length, 1)
})

test('nearby people and vertically offset occlusions are not merged by containment', () => {
  assert.equal(mergeDetections([box(), box({ x: 120, pass: 1 })]).length, 2)
  assert.equal(mergeDetections([box(), box({ x: 55, y: 140, width: 50, height: 50, pass: 1 })]).length, 2)
  assert.equal(mergeDetections([box(), box({ x: 55, y: 42, width: 50, height: 50 })]).length, 2)
})

test('empty and invalid detections produce no results', () => {
  assert.deepEqual(mergeDetections([]), [])
  assert.deepEqual(mergeDetections([box({ width: 0 }), box({ confidence: NaN })]), [])
})
