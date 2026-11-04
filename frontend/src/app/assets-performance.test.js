import { existsSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const assetsDirectory = join(process.cwd(), 'public', 'assets')
const optimizedAssets = [
  'bobo-idle-v1.webp',
  'careerpilot-landscape-v1.webp',
  'careerpilot-wordmark-v1.webp',
]

describe('first-load visual assets', () => {
  it('uses versioned WebP assets within a one megabyte combined budget', () => {
    const paths = optimizedAssets.map((name) => join(assetsDirectory, name))

    for (const path of paths) expect(existsSync(path), path).toBe(true)
    const totalBytes = paths.reduce((total, path) => total + statSync(path).size, 0)
    expect(totalBytes).toBeLessThan(1_000_000)
  })
})
