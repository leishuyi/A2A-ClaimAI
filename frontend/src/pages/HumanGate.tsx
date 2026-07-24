import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Descriptions, Button, Space, Tag, Spin, Divider,
  Input, InputNumber, Radio, Form, message, Table, Typography,
  Row, Col, Alert,
} from 'antd'
import {
  ArrowLeftOutlined, CheckCircleOutlined, CloseCircleOutlined,
  EditOutlined, SafetyCertificateOutlined, FileTextOutlined,
  WarningOutlined, DollarOutlined,
} from '@ant-design/icons'
import { api } from '../api/client'
import RiskBadge from '../components/RiskBadge'
import AgentTraceView from '../components/AgentTrace'
import ClaimProgress from '../components/ClaimProgress'
import type { Case, AgentTrace } from '../types'

const { Text, Title } = Typography

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
    if (!operator.trim()) { message.error('请输入操作人姓名'); return }
    if (action === 'modify' && modifiedAmount == null) { message.error('修改后通过需填写理算金额'); return }

    setSubmitting(true)
    try {
      await api.submitReview(Number(id), {
        action: action as 'approve' | 'reject' | 'modify',
        comment, operator,
        modified_amount: action === 'modify' ? modifiedAmount : undefined,
      })
      message.success('审核完成')
      navigate(`/cases/${id}`)
    } catch (e: any) {
      message.error(e.message || '操作失败')
    } finally { setSubmitting(false) }
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />
  if (!caseData) return <div>案件不存在</div>

  const summaryTrace = traces.find(t => t.agent_name === 'agent_f_summary')
  const riskTrace = traces.find(t => t.agent_name === 'agent_e_risk')
  const calcTrace = traces.find(t => t.agent_name === 'agent_d_calculation')
  const report = summaryTrace?.output_data as any

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/cases/${id}`)}>返回详情</Button>
      </Space>

      {/* 理赔进度 */}
      <ClaimProgress status={caseData.status} />

      {/* 审核工作台 */}
      <Card
        title={
          <Space>
            <SafetyCertificateOutlined style={{ fontSize: 20, color: '#1677ff' }} />
            <span style={{ fontSize: 16 }}>人工授权工作台</span>
          </Space>
        }
      >
        {/* 案件基本信息 */}
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={6}>
            <Text type="secondary">案件编号</Text>
            <div><Text strong style={{ fontFamily: 'monospace' }}>{caseData.case_no}</Text></div>
          </Col>
          <Col span={6}>
            <Text type="secondary">出险人</Text>
            <div><Text strong>{caseData.insured_name}</Text></div>
          </Col>
          <Col span={6}>
            <Text type="secondary">险种</Text>
            <div><Text strong>{caseData.insurance_product}</Text></div>
          </Col>
          <Col span={6}>
            <Text type="secondary">风险等级</Text>
            <div><RiskBadge level={caseData.risk_level} /></div>
          </Col>
        </Row>

        {/* AI 建议摘要 - 关键数据卡片 */}
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={6}>
            <Card size="small" style={{ background: '#f6ffed', border: '1px solid #b7eb8f' }}>
              <Text type="secondary" style={{ fontSize: 12 }}>医疗总费用</Text>
              <div style={{ fontSize: 24, fontWeight: 700 }}>
                {caseData.total_amount ? `¥${caseData.total_amount.toLocaleString()}` : '-'}
              </div>
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small" style={{ background: '#e6f4ff', border: '1px solid #91caff' }}>
              <Text type="secondary" style={{ fontSize: 12 }}>AI 建议理算</Text>
              <div style={{ fontSize: 24, fontWeight: 700, color: '#1677ff' }}>
                {caseData.calculated_amount ? `¥${caseData.calculated_amount.toLocaleString()}` : '-'}
              </div>
              {caseData.total_amount && caseData.calculated_amount && (
                <Text style={{ fontSize: 12, color: '#666' }}>
                  赔付比例 {caseData.total_amount > 0 ? (caseData.calculated_amount / caseData.total_amount * 100).toFixed(0) : 0}%
                </Text>
              )}
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small" style={{ background: '#fff7e6', border: '1px solid #ffd591' }}>
              <Text type="secondary" style={{ fontSize: 12 }}>AI 置信度</Text>
              <div style={{ fontSize: 24, fontWeight: 700, color: '#faad14' }}>
                {summaryTrace?.confidence != null
                  ? `${(summaryTrace.confidence * 100).toFixed(0)}%`
                  : '-'}
              </div>
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small" style={{ background: '#fff0f0', border: '1px solid #ffa39e' }}>
              <Text type="secondary" style={{ fontSize: 12 }}>审核优先级</Text>
              <div style={{ fontSize: 18, fontWeight: 600 }}>
                {report?.review_priority || '正常'}
              </div>
            </Card>
          </Col>
        </Row>

        {/* 理算明细 */}
        {calcTrace?.output_data?.calculation_items && (
          <Card title="理算明细" size="small" style={{ marginBottom: 16 }}>
            <Table
              dataSource={calcTrace.output_data.calculation_items as any[]}
              rowKey="category"
              pagination={false}
              size="small"
              summary={() => (
                <Table.Summary.Row>
                  <Table.Summary.Cell index={0}><Text strong>合计</Text></Table.Summary.Cell>
                  <Table.Summary.Cell index={1}>
                    <Text strong>¥{((calcTrace.output_data as any).medical_total || 0).toLocaleString()}</Text>
                  </Table.Summary.Cell>
                  <Table.Summary.Cell index={2}></Table.Summary.Cell>
                  <Table.Summary.Cell index={3}>
                    <Text strong style={{ color: '#1677ff', fontSize: 16 }}>
                      ¥{((calcTrace.output_data as any).calculated_amount || 0).toLocaleString()}
                    </Text>
                  </Table.Summary.Cell>
                  <Table.Summary.Cell index={4}></Table.Summary.Cell>
                </Table.Summary.Row>
              )}
              columns={[
                { title: '费用项', dataIndex: 'category', width: 100 },
                { title: '原始金额', dataIndex: 'original', width: 120,
                  render: (v: number) => `¥${v.toLocaleString()}` },
                { title: '赔付比例', dataIndex: 'ratio', width: 100,
                  render: (v: number) => `${(v * 100).toFixed(0)}%` },
                { title: '赔付金额', dataIndex: 'amount', width: 120,
                  render: (v: number) => <Text strong style={{ color: '#1677ff' }}>¥{v.toLocaleString()}</Text> },
                { title: '依据', dataIndex: 'basis', ellipsis: true },
              ]}
            />
          </Card>
        )}

        {/* 风控审查发现 */}
        {riskTrace?.output_data?.risk_findings && (
          <Card title="风控审查发现" size="small" style={{ marginBottom: 16 }}>
            <Table
              dataSource={riskTrace.output_data.risk_findings as any[]}
              rowKey="rule"
              pagination={false}
              size="small"
              columns={[
                { title: '检查项', dataIndex: 'rule', width: 120 },
                {
                  title: '风险', dataIndex: 'risk', width: 80,
                  render: (v: string) => (
                    <Tag color={v === 'low' ? 'green' : v === 'medium' ? 'orange' : 'red'}>
                      {v === 'low' ? '低' : v === 'medium' ? '中' : '高'}
                    </Tag>
                  ),
                },
                { title: '详情', dataIndex: 'detail' },
              ]}
            />
          </Card>
        )}

        {/* AI 全链路置信度 */}
        {report?.agent_confidences && (
          <Card title="AI 全链路置信度" size="small" style={{ marginBottom: 16 }}>
            <Row gutter={[16, 8]}>
              {Object.entries(report.agent_confidences).map(([agent, conf]: [string, any]) => (
                <Col span={8} key={agent}>
                  <Space>
                    <Text>{agent}</Text>
                    {conf > 0 ? (
                      <Tag color={conf >= 0.9 ? 'green' : conf >= 0.7 ? 'orange' : 'red'}>
                        {(conf * 100).toFixed(0)}%
                      </Tag>
                    ) : <Tag>未执行</Tag>}
                  </Space>
                </Col>
              ))}
            </Row>
            <Divider />
            <Text strong>综合置信度: </Text>
            <Tag color={report.overall_confidence >= 0.9 ? 'green' : report.overall_confidence >= 0.7 ? 'orange' : 'red'}
              style={{ fontSize: 14, padding: '2px 12px' }}>
              {(report.overall_confidence * 100).toFixed(0)}%
            </Tag>
            <Text type="secondary" style={{ marginLeft: 16 }}>
              AI 建议: {report.suggestion}
            </Text>
          </Card>
        )}

        {/* Agent 链路追溯 */}
        <Card title="Agent 处理链路" size="small" style={{ marginBottom: 16 }}>
          <AgentTraceView traces={traces} loading={false} />
        </Card>

        <Divider />

        {/* 审核操作 */}
        <Card title={<span><FileTextOutlined style={{ marginRight: 8 }} />审核操作</span>} size="small">
          <Alert
            message="请仔细核对以上 AI 处理结果后做出审核决定。此操作不可撤回。"
            type="warning" showIcon style={{ marginBottom: 16 }}
          />

          <div style={{ marginBottom: 16 }}>
            <Radio.Group value={action} onChange={e => setAction(e.target.value)}>
              <Radio.Button value="approve"><CheckCircleOutlined /> 通过</Radio.Button>
              <Radio.Button value="reject"><CloseCircleOutlined /> 驳回</Radio.Button>
              <Radio.Button value="modify"><EditOutlined /> 修改后通过</Radio.Button>
            </Radio.Group>
          </div>

          {action === 'modify' && (
            <Form.Item label="修改理算金额">
              <InputNumber style={{ width: 240 }} min={0}
                value={modifiedAmount} onChange={v => setModifiedAmount(v ?? undefined)}
                prefix="¥" />
            </Form.Item>
          )}

          <Form.Item label="审核意见">
            <Input.TextArea rows={3}
              placeholder={action === 'approve' ? '确认通过，可补充审核意见...' : '请填写驳回或修改理由...'}
              value={comment} onChange={e => setComment(e.target.value)} />
          </Form.Item>

          <Form.Item label="核赔人员" required>
            <Input style={{ width: 240 }} placeholder="请输入核赔人员姓名"
              value={operator} onChange={e => setOperator(e.target.value)} />
          </Form.Item>

          <div style={{ textAlign: 'center', marginTop: 24 }}>
            <Space size={16}>
              <Button onClick={() => navigate(`/cases/${id}`)}>取消</Button>
              <Button type="primary" size="large"
                icon={action === 'reject' ? <CloseCircleOutlined /> : <CheckCircleOutlined />}
                loading={submitting} onClick={handleSubmit}
                danger={action === 'reject'}>
                {action === 'approve' ? '确认通过' : action === 'reject' ? '确认驳回' : '确认修改后通过'}
              </Button>
            </Space>
          </div>
        </Card>
      </Card>
    </div>
  )
}
