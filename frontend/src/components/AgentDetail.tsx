import { Modal, Descriptions, Tag } from 'antd'
import type { AgentTrace } from '../types'

interface Props {
  trace: AgentTrace | null
  onClose: () => void
}

export default function AgentDetail({ trace, onClose }: Props) {
  if (!trace) return null

  return (
    <Modal
      title={`${trace.agent_label} - 详情`}
      open={!!trace}
      onCancel={onClose}
      footer={null}
      width={720}
    >
      <Descriptions column={2} bordered size="small">
        <Descriptions.Item label="Agent 名称" span={2}>
          <Tag>{trace.agent_name}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="状态">
          <Tag color={trace.status === 'completed' ? 'green' : 'orange'}>
            {trace.status === 'completed' ? '已完成' : trace.status}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label="置信度">
          {trace.confidence != null ? `${(trace.confidence * 100).toFixed(1)}%` : '-'}
        </Descriptions.Item>
        <Descriptions.Item label="开始时间" span={2}>
          {trace.started_at ? new Date(trace.started_at).toLocaleString('zh-CN') : '-'}
        </Descriptions.Item>
        <Descriptions.Item label="完成时间" span={2}>
          {trace.completed_at ? new Date(trace.completed_at).toLocaleString('zh-CN') : '-'}
        </Descriptions.Item>
      </Descriptions>

      <div style={{ marginTop: 16 }}>
        <h4>输入数据</h4>
        <pre style={{ background: '#f5f5f5', padding: 12, borderRadius: 6, fontSize: 12, maxHeight: 200, overflow: 'auto' }}>
          {JSON.stringify(trace.input_data, null, 2)}
        </pre>
      </div>

      <div style={{ marginTop: 16 }}>
        <h4>输出数据</h4>
        <pre style={{ background: '#f5f5f5', padding: 12, borderRadius: 6, fontSize: 12, maxHeight: 300, overflow: 'auto' }}>
          {JSON.stringify(trace.output_data, null, 2)}
        </pre>
      </div>
    </Modal>
  )
}
