import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Table, Button, Modal, Form, Input, DatePicker, Select, InputNumber, Space, Tag, message } from 'antd'
import { PlusOutlined, PlayCircleOutlined, EyeOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { api } from '../api/client'
import RiskBadge from '../components/RiskBadge'
import type { Case } from '../types'

const statusMap: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '待处理' },
  processing: { color: 'processing', text: '处理中' },
  agents_completed: { color: 'blue', text: 'Agent完成' },
  pending_review: { color: 'orange', text: '待审核' },
  approved: { color: 'green', text: '已通过' },
  rejected: { color: 'red', text: '已驳回' },
}

export default function CaseList() {
  const [cases, setCases] = useState<Case[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()
  const [submitting, setSubmitting] = useState(false)
  const navigate = useNavigate()

  const load = async () => {
    setLoading(true)
    try {
      const data = await api.getCases()
      setCases(data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleCreate = async () => {
    const values = await form.validateFields()
    setSubmitting(true)
    try {
      await api.createCase({
        insured_name: values.insured_name,
        insurance_product: values.insurance_product,
        incident_desc: values.incident_desc,
        incident_date: values.incident_date.format('YYYY-MM-DD'),
        total_amount: values.total_amount,
      })
      message.success('报案成功')
      setModalOpen(false)
      form.resetFields()
      load()
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>理赔案件</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          新建报案
        </Button>
      </div>

      <Table
        dataSource={cases}
        rowKey="id"
        loading={loading}
        columns={[
          { title: '案件编号', dataIndex: 'case_no', width: 160 },
          { title: '出险人', dataIndex: 'insured_name', width: 100 },
          { title: '险种', dataIndex: 'insurance_product', width: 140 },
          {
            title: '状态',
            dataIndex: 'status',
            width: 110,
            render: (s: string) => {
              const m = statusMap[s] ?? { color: 'default', text: s }
              return <Tag color={m.color}>{m.text}</Tag>
            },
          },
          {
            title: '风险等级',
            dataIndex: 'risk_level',
            width: 100,
            render: (v: string) => <RiskBadge level={v as Case['risk_level']} />,
          },
          {
            title: '医疗费用',
            dataIndex: 'total_amount',
            width: 120,
            render: (v: number | null) => (v != null ? `¥${v.toLocaleString()}` : '-'),
          },
          {
            title: '理算金额',
            dataIndex: 'calculated_amount',
            width: 120,
            render: (v: number | null) => (v != null ? `¥${v.toLocaleString()}` : '-'),
          },
          {
            title: '报案时间',
            dataIndex: 'created_at',
            width: 170,
            render: (v: string) => new Date(v).toLocaleString('zh-CN'),
          },
          {
            title: '操作',
            width: 160,
            render: (_: unknown, record: Case) => (
              <Space>
                <Button size="small" icon={<EyeOutlined />} onClick={() => navigate(`/cases/${record.id}`)}>
                  详情
                </Button>
                {record.status === 'draft' && (
                  <Button
                    size="small"
                    type="primary"
                    icon={<PlayCircleOutlined />}
                    onClick={async () => {
                      await api.runAgents(record.id)
                      message.success('Agent链路已触发')
                      load()
                    }}
                  >
                    执行Agent
                  </Button>
                )}
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title="新建报案"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleCreate}
        confirmLoading={submitting}
        width={560}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="insured_name" label="出险人姓名" rules={[{ required: true }]}>
            <Input placeholder="请输入出险人姓名" />
          </Form.Item>
          <Form.Item name="insurance_product" label="险种" rules={[{ required: true }]}>
            <Select
              options={[
                { label: '住院医疗险A', value: '住院医疗险A' },
                { label: '住院医疗险B', value: '住院医疗险B' },
                { label: '意外医疗险', value: '意外医疗险' },
                { label: '重疾险', value: '重疾险' },
              ]}
              placeholder="请选择险种"
            />
          </Form.Item>
          <Form.Item name="incident_desc" label="出险描述" rules={[{ required: true }]}>
            <Input.TextArea rows={3} placeholder="描述出险经过、诊断结果等" />
          </Form.Item>
          <Form.Item name="incident_date" label="出险日期" rules={[{ required: true }]}>
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="total_amount" label="医疗总费用">
            <InputNumber style={{ width: '100%' }} min={0} placeholder="可选项，案件材料中提取" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
