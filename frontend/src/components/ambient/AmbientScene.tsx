import { useRef } from 'react'
import type { PointerEvent } from 'react'

import './ambient-scene.css'

export function AmbientScene() {
  const scene = useRef<HTMLDivElement>(null)

  function onPointerMove(event: PointerEvent<HTMLDivElement>) {
    const target = scene.current
    if (!target) return
    const x = event.clientX / window.innerWidth - 0.5
    const y = event.clientY / window.innerHeight - 0.5
    target.style.setProperty('--scene-x', `${x * -18}px`)
    target.style.setProperty('--scene-y', `${y * -12}px`)
  }

  function reset() {
    scene.current?.style.setProperty('--scene-x', '0px')
    scene.current?.style.setProperty('--scene-y', '0px')
  }

  return (
    <div ref={scene} className="ambient-scene" aria-hidden="true" onPointerMove={onPointerMove} onPointerLeave={reset}>
      <div className="ambient-landscape" />
      <div className="ambient-light ambient-light-one" />
      <div className="ambient-light ambient-light-two" />
      <div className="ambient-grain" />
    </div>
  )
}
