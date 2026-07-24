import { Tag } from 'antd'
import type { RiskLevel } from '../types'

const config: Record<RiskLevel, { color: string; text: string }> = {
  low: { color: 'green', text: '低风险' },
  medium: { color: 'orange', text: '中风险' },
  high: { color: 'red', text: '高风险' },
}

export default function RiskBadge({ level }: { level: RiskLevel }) {
  const c = config[level] ?? config.low
  return <Tag color={c.color}>{c.text}</Tag>
}
