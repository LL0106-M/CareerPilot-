import { Compass, MoonStars, Sparkle } from '@phosphor-icons/react'
import { motion, useReducedMotion } from 'framer-motion'

import './bobo.css'

export type BoboMood =
  | 'idle'
  | 'listen'
  | 'organize'
  | 'explore'
  | 'act'
  | 'thinking'
  | 'dreaming'

const moodLabels: Record<BoboMood, string> = {
  idle: '泊泊正在陪伴你',
  listen: '泊泊正在倾听',
  organize: '泊泊正在帮你梳理',
  explore: '泊泊正在和你探索',
  act: '泊泊准备和你行动',
  thinking: '泊泊正在思考',
  dreaming: '泊泊正在 Dreaming',
}

const motionByMood: Record<BoboMood, { y: number[]; rotate: number[]; scale: number[] }> = {
  idle: { y: [0, -3, 0], rotate: [0, 0.4, 0], scale: [1, 1.006, 1] },
  listen: { y: [0, 1, 0], rotate: [0, -0.8, 0], scale: [1, 1.004, 1] },
  organize: { y: [0, -2, 0], rotate: [0, 1.2, 0], scale: [1, 1.004, 1] },
  explore: { y: [0, -5, 0], rotate: [0, 1.8, 0], scale: [1, 1.012, 1] },
  act: { y: [0, -2, 0], rotate: [0, -1, 0], scale: [1, 1.01, 1] },
  thinking: { y: [0, -4, 0], rotate: [-1.2, 1.2, -1.2], scale: [1, 1.008, 1] },
  dreaming: { y: [3, -7, 3], rotate: [-1.4, 1.4, -1.4], scale: [1, 1.01, 1] },
}

export function Bobo({
  mood,
  size = 160,
  showLabel = false,
}: {
  mood: BoboMood
  size?: number
  showLabel?: boolean
}) {
  const reduceMotion = useReducedMotion()
  const animation = motionByMood[mood]

  return (
    <figure
      className={`bobo bobo-${mood}`}
      style={{ '--bobo-size': `${size}px` } as React.CSSProperties}
      role="img"
      aria-label={moodLabels[mood]}
      data-mood={mood}
    >
      <motion.div
        className="bobo-image-wrap"
        animate={reduceMotion ? undefined : animation}
        transition={{
          duration: mood === 'dreaming' ? 4.2 : mood === 'thinking' ? 1.4 : 3.6,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      >
        <img src="/assets/bobo-idle.png" alt="" draggable="false" />
      </motion.div>

      <span className="bobo-state-mark" aria-hidden="true">
        {mood === 'dreaming' ? (
          <MoonStars size={18} weight="fill" />
        ) : mood === 'thinking' ? (
          <Sparkle size={18} weight="fill" />
        ) : (
          <Compass size={18} weight={mood === 'listen' ? 'regular' : 'fill'} />
        )}
      </span>

      {showLabel && <figcaption>{moodLabels[mood]}</figcaption>}
    </figure>
  )
}
