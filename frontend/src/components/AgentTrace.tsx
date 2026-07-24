import { useState } from 'react'
import { Timeline, Card, Button, Descriptions, Tag, Spin } from 'antd'
import { EyeOutlined, CheckCircleOutlined, ClockCircleOutlined, LoadingOutlined } from '@ant-design/icons'
import type { AgentTrace as AgentTraceType } from '../types'
import AgentDetail from './AgentDetail'

interface Props {
  traces: AgentTraceType[]
  loading: boolean
}

const statusIcon: Record<string, React.ReactNode> = {
  completed: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
  running: <LoadingOutlined style={{ color: '#1677ff' }} />,
  pending: <ClockCircleOutlined style={{ color: '#d9d9d9' }} />,
  failed: <ClockCircleOutlined style={{ color: '#ff4d4f' }} />,
}

export default function AgentTraceView({ traces, loading }: Props) {
  const [selected, setSelected] = useState<AgentTraceType | null>(null)

  if (loading) {
    return <Spin tip="加载 Agent 链路..." />
  }

  return (
    <>
      <Card title="Agent 全链路追溯" size="small">
        <Timeline
          items={traces.map((t) => ({
            dot: statusIcon[t.status] || statusIcon.pending,
            children: (
              <div key={t.id}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <strong>{t.agent_label}</strong>
                  <span>
                    <Tag>{t.agent_name}</Tag>
                    {t.confidence != null && (
                      <Tag color={t.confidence >= 0.9 ? 'green' : t.confidence >= 0.7 ? 'orange' : 'red'}>
                        置信度 {(t.confidence * 100).toFixed(0)}%
                      </Tag>
                    )}
                    {t.status === 'completed' && (
                      <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => setSelected(t)}>
                        查看详情
                      </Button>
                    )}
                  </span>
                </div>
                {t.status === 'completed' && t.output_data?.case_summary != null && (
                  <div style={{ color: '#666', marginTop: 4, fontSize: 13 }}>
                    {String(t.output_data.case_summary)}
                  </div>
                )}
              </div>
            ),
          }))}
        />
      </Card>
      <AgentDetail trace={selected} onClose={() => setSelected(null)} />
    </>
  )
}
