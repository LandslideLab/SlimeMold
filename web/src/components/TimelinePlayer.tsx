import { useEffect, useRef, useState } from 'react'
import type { SimResult } from '../types'
import { OrgChart } from './OrgChart'

interface TimelinePlayerProps {
  result: SimResult
}

export function TimelinePlayer({ result }: TimelinePlayerProps) {
  const maxTurn = result.config.turns
  const [turn, setTurn] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const rafRef = useRef<number | null>(null)
  const lastRef = useRef<number>(0)
  const turnRef = useRef(0)

  useEffect(() => {
    turnRef.current = turn
  }, [turn])

  useEffect(() => {
    if (!playing) return
    const step = (ts: number) => {
      if (lastRef.current === 0) lastRef.current = ts
      const dt = (ts - lastRef.current) / 1000
      lastRef.current = ts
      let t = turnRef.current + dt * speed
      if (t >= maxTurn) {
        t = maxTurn
        setPlaying(false)
      }
      turnRef.current = t
      setTurn(t)
      if (playing) rafRef.current = requestAnimationFrame(step)
    }
    lastRef.current = 0
    rafRef.current = requestAnimationFrame(step)
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [playing, speed, maxTurn])

  const reset = () => {
    setPlaying(false)
    turnRef.current = 0
    setTurn(0)
  }

  return (
    <div className="timeline-card">
      <div className="timeline-head">
        <span className="label">Run trajectory — tasks flowing along the reporting chain</span>
        <div className="timeline-playback">
          <button className="btn btn-sm btn-ghost" onClick={reset}>
            ↺
          </button>
          <button
            className="btn btn-sm"
            data-active={playing}
            onClick={() => setPlaying((v) => !v)}
          >
            {playing ? '⏸' : '▶'}
          </button>
          <button className="btn btn-sm btn-ghost" onClick={() => { setPlaying(false); turnRef.current = Math.max(0, turnRef.current - 1); setTurn(turnRef.current) }}>
            −
          </button>
          <button className="btn btn-sm btn-ghost" onClick={() => { setPlaying(false); turnRef.current = Math.min(maxTurn, turnRef.current + 1); setTurn(turnRef.current) }}>
            +
          </button>
          <span>
            turn {Math.min(maxTurn, Math.floor(turn))}/{maxTurn}
          </span>
          <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} style={{ width: 70 }}>
            <option value={0.5}>0.5×</option>
            <option value={1}>1×</option>
            <option value={2}>2×</option>
            <option value={4}>4×</option>
          </select>
        </div>
      </div>
      <OrgChart result={result} turn={turn} messages={result.messages} />
    </div>
  )
}
