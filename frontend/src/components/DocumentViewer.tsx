import { Table, Tag } from 'antd'
import { CheckCircleOutlined, WarningOutlined } from '@ant-design/icons'

interface DocItem {
  type: string
  status: string
  confidence: number
}

interface Props {
  documents: DocItem[]
}

export default function DocumentViewer({ documents }: Props) {
  if (!documents || documents.length === 0) return null

  return (
    <Table
      dataSource={documents}
      rowKey="type"
      size="small"
      pagination={false}
      columns={[
        { title: '材料类型', dataIndex: 'type' },
        {
          title: '识别状态',
          dataIndex: 'status',
          render: (v: string, record: DocItem) => (
            <span>
              {record.confidence >= 0.9
                ? <CheckCircleOutlined style={{ color: '#52c41a', marginRight: 4 }} />
                : <WarningOutlined style={{ color: '#faad14', marginRight: 4 }} />
              }
              {v}
            </span>
          ),
        },
        {
          title: '置信度',
          dataIndex: 'confidence',
          render: (v: number) => (
            <Tag color={v >= 0.9 ? 'green' : v >= 0.7 ? 'orange' : 'red'}>
              {(v * 100).toFixed(0)}%
            </Tag>
          ),
        },
      ]}
    />
  )
}
