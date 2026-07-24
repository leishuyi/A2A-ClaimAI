import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Descriptions, Button, Space, Tag, Spin, Divider,
  Input, InputNumber, Radio, Form, message, Modal, Timeline,
} from 'antd'
import {
  ArrowLeftOutlined, CheckCircleOutlined, CloseCircleOutlined,
  EditOutlined, SafetyCertificateOutlined,
} from '@ant-design/icons'
import { api } from '../api/client'
import RiskBadge from '../components/RiskBadge'
import AgentTraceView from '../components/AgentTrace'
import type { Case, AgentTrace } from '../types'

const statusMap: Record<string, { color: string; text: string }> = {
  pending_review: { color: 'orange', text: '待审核' },
  approved: { color: 'green', text: '已通过' },
  rejected: { color: 'red', text: '已驳回' },
}

export default function HumanGate() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [caseData, setCaseData] = useState<Case | null>(null)
  const [traces, setTraces] = useState<AgentTrace[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [action, setAction] = useState<string>('approve')
  const [comment, setComment] = useState('')
  const [modifiedAmount, setModifiedAmount] = useState<number | undefined>()
  const [operator, setOperator] = useState('')

  useEffect(() => {
    if (!id) return
    setLoading(true)
    Promise.all([
      api.getCase(Number(id)),
      api.getTraces(Number(id)),
    ]).then(([c, t]) => {
      setCaseData(c)
      setTraces(t)
      setModifiedAmount(c.calculated_amount ?? undefined)
    }).finally(() => setLoading(false))
  }, [id])

  const handleSubmit = async () => {
    if (!operator.trim()) {
      message.error('请输入操作人姓名')
      return
    }
    if (action === 'modify' && modifiedAmount == null) {
      message.error('修改后通过需填写理算金额')
      return
    }

    setSubmitting(true)
    try {
      await api.submitReview(Number(id), {
        action: action as 'approve' | 'reject' | 'modify',
        comment,
        operator,
        modified_amount: action === 'modify' ? modifiedAmount : undefined,
      })
      message.success('审核完成')
      navigate(`/cases/${id}`)
    } catch (e: any) {
      message.error(e.message || '操作失败')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />
  if (!caseData) return <div>案件不存在</div>

  const summaryTrace = traces.find(t => t.agent_name === 'agent_f_summary')

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/cases/${id}`)}>返回详情</Button>
      </Space>

      {/* 案件摘要卡片 */}
      <Card
        title={
          <Space>
            <SafetyCertificateOutlined style={{ fontSize: 20, color: '#1677ff' }} />
            <span>人工授权工作台</span>
          </Space>
        }
      >
        <Descriptions column={3} bordered size="small">
          <Descriptions.Item label="案件编号">{caseData.case_no}</Descriptions.Item>
          <Descriptions.Item label="出险人">{caseData.insured_name}</Descriptions.Item>
          <Descriptions.Item label="险种">{caseData.insurance_product}</Descriptions.Item>
          <Descriptions.Item label="出险描述" span={3}>{caseData.incident_desc}</Descriptions.Item>
        </Descriptions>

        <Divider />

        {/* 审核摘要 */}
        <div style={{
          background: '#f6ffed',
          border: '1px solid #b7eb8f',
          borderRadius: 8,
          padding: '16px 24px',
          marginBottom: 16,
        }}>
          <Space size={24}>
            <div>
              <div style={{ fontSize: 12, color: '#666' }}>医疗总费用</div>
              <div style={{ fontSize: 20, fontWeight: 600 }}>
                {caseData.total_amount ? `¥${caseData.total_amount.toLocaleString()}` : '-'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: '#666' }}>AI 建议理算金额</div>
              <div style={{ fontSize: 20, fontWeight: 600, color: '#1677ff' }}>
                {caseData.calculated_amount ? `¥${caseData.calculated_amount.toLocaleString()}` : '-'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: '#666' }}>AI 置信度</div>
              <div style={{ fontSize: 20, fontWeight: 600 }}>
                {summaryTrace?.confidence != null
                  ? `${(summaryTrace.confidence * 100).toFixed(0)}%`
                  : '-'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: '#666' }}>风险等级</div>
              <div><RiskBadge level={caseData.risk_level} /></div>
            </div>
          </Space>
        </div>

        {/* Agent 链路摘要 */}
        {summaryTrace?.output_data?.audit_trail != null && (() => {
          const a = summaryTrace!.output_data.audit_trail as Record<string, any>
          return (
          <Card title="Agent 处理摘要" size="small" style={{ marginBottom: 16 }}>
            <Timeline
              items={[
                { color: 'green', children: `报案受理: ${a.agent_a_intake}` },
                { color: 'green', children: `材料解析: 诊断 ${a.agent_b_doc_parser?.diagnosis}` },
                { color: 'green', children: `核责判断: ${a.agent_c_liability}` },
                { color: 'green', children: `理算: ¥${a.agent_d_calculation}` },
                {
                  color: a.agent_e_risk?.level === 'low' ? 'green' : 'orange',
                  children: `风控审查: 评分 ${a.agent_e_risk?.score}`,
                },
              ]}
            />
          </Card>
          )
        })()}

        {/* Agent 全链路追溯（可展开） */}
        <AgentTraceView traces={traces} loading={false} />

        <Divider />

        {/* 操作表单 */}
        <Card title="审核操作" size="small">
          <div style={{ marginBottom: 16 }}>
            <Radio.Group value={action} onChange={e => setAction(e.target.value)}>
              <Radio.Button value="approve">
                <CheckCircleOutlined /> 通过
              </Radio.Button>
              <Radio.Button value="reject">
                <CloseCircleOutlined /> 驳回
              </Radio.Button>
              <Radio.Button value="modify">
                <EditOutlined /> 修改后通过
              </Radio.Button>
            </Radio.Group>
          </div>

          {action === 'modify' && (
            <Form.Item label="理算金额">
              <InputNumber
                style={{ width: 240 }}
                min={0}
                value={modifiedAmount}
                onChange={v => setModifiedAmount(v ?? undefined)}
                prefix="¥"
              />
            </Form.Item>
          )}

          <Form.Item label="审核意见">
            <Input.TextArea
              rows={3}
              placeholder={action === 'approve' ? '确认通过，可补充审核意见...' : '请填写驳回或修改理由...'}
              value={comment}
              onChange={e => setComment(e.target.value)}
            />
          </Form.Item>

          <Form.Item label="操作人" required>
            <Input
              style={{ width: 240 }}
              placeholder="请输入核赔人员姓名"
              value={operator}
              onChange={e => setOperator(e.target.value)}
            />
          </Form.Item>

          <div style={{ textAlign: 'center', marginTop: 24 }}>
            <Space size={16}>
              <Button onClick={() => navigate(`/cases/${id}`)}>取消</Button>
              <Button
                type="primary"
                size="large"
                icon={action === 'reject' ? <CloseCircleOutlined /> : <CheckCircleOutlined />}
                loading={submitting}
                onClick={handleSubmit}
                danger={action === 'reject'}
              >
                {action === 'approve' ? '确认通过' : action === 'reject' ? '确认驳回' : '确认修改后通过'}
              </Button>
            </Space>
          </div>

          <div style={{ textAlign: 'center', marginTop: 12 }}>
            <Tag color="warning">此操作不可撤回，请确认AI推理结果后再执行</Tag>
          </div>
        </Card>
      </Card>
    </div>
  )
}
