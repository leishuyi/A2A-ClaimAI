import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Card, Descriptions, Tag, Button, Space, Spin, Divider } from 'antd'
import { ArrowLeftOutlined, CheckCircleOutlined } from '@ant-design/icons'
import { api } from '../api/client'
import RiskBadge from '../components/RiskBadge'
import AgentTraceView from '../components/AgentTrace'
import DocumentViewer from '../components/DocumentViewer'
import type { Case, AgentTrace } from '../types'

const statusMap: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '待处理' },
  processing: { color: 'processing', text: '处理中' },
  agents_completed: { color: 'blue', text: 'Agent完成' },
  pending_review: { color: 'orange', text: '待审核' },
  approved: { color: 'green', text: '已通过' },
  rejected: { color: 'red', text: '已驳回' },
}

export default function CaseDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [caseData, setCaseData] = useState<Case | null>(null)
  const [traces, setTraces] = useState<AgentTrace[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    Promise.all([
      api.getCase(Number(id)),
      api.getTraces(Number(id)),
    ]).then(([c, t]) => {
      setCaseData(c)
      setTraces(t)
    }).finally(() => setLoading(false))
  }, [id])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />
  if (!caseData) return <div>案件不存在</div>

  const summaryTrace = traces.find(t => t.agent_name === 'agent_f_summary')
  const docTrace = traces.find(t => t.agent_name === 'agent_b_doc_parser')

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/cases')}>返回列表</Button>
      </Space>

      <Card title={
        <Space>
          <span>{caseData.case_no}</span>
          <Tag color={statusMap[caseData.status]?.color}>{statusMap[caseData.status]?.text}</Tag>
          <RiskBadge level={caseData.risk_level} />
        </Space>
      }>
        <Descriptions column={3} bordered size="small">
          <Descriptions.Item label="出险人">{caseData.insured_name}</Descriptions.Item>
          <Descriptions.Item label="险种">{caseData.insurance_product}</Descriptions.Item>
          <Descriptions.Item label="出险日期">
            {new Date(caseData.incident_date).toLocaleDateString('zh-CN')}
          </Descriptions.Item>
          <Descriptions.Item label="医疗总费用" span={1}>
            {caseData.total_amount ? `¥${caseData.total_amount.toLocaleString()}` : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="理算金额（AI建议）" span={1}>
            <strong style={{ color: '#1677ff' }}>
              {caseData.calculated_amount ? `¥${caseData.calculated_amount.toLocaleString()}` : '-'}
            </strong>
          </Descriptions.Item>
          <Descriptions.Item label="报案时间">
            {new Date(caseData.created_at).toLocaleString('zh-CN')}
          </Descriptions.Item>
          <Descriptions.Item label="出险描述" span={3}>
            {caseData.incident_desc}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Divider />

      {/* Agent 链路追溯 */}
      <AgentTraceView traces={traces} loading={false} />

      {/* 材料解析详情 */}
      {!!docTrace?.output_data?.documents_parsed && (
        <>
          <Divider />
          <DocumentViewer documents={docTrace.output_data.documents_parsed as any[]} />
        </>
      )}

      {/* 核责详情 */}
      {(traces.find(t => t.agent_name === 'agent_c_liability')?.output_data?.exclusions_checked as any) && (
        <>
          <Divider />
          <Card title="免责条款检查" size="small">
            <Descriptions column={1} bordered size="small">
              {(traces.find(t => t.agent_name === 'agent_c_liability')!.output_data.exclusions_checked as any[]).map((e: any, i: number) => (
                <Descriptions.Item label={e.item} key={i}>
                  <Tag color={e.matched ? 'red' : 'green'}>{e.matched ? '匹配' : '不匹配'}</Tag>
                  {e.detail}
                </Descriptions.Item>
              ))}
            </Descriptions>
          </Card>
        </>
      )}

      {/* 风控详情 */}
      {(traces.find(t => t.agent_name === 'agent_e_risk')?.output_data?.risk_findings as any) && (
        <>
          <Divider />
          <Card title="风控审查结果" size="small">
            <Descriptions column={1} bordered size="small">
              {(traces.find(t => t.agent_name === 'agent_e_risk')!.output_data.risk_findings as any[]).map((f: any, i: number) => (
                <Descriptions.Item label={f.rule} key={i}>
                  <Tag color={f.risk === 'low' ? 'green' : f.risk === 'medium' ? 'orange' : 'red'}>{f.risk}</Tag>
                  {f.detail}
                </Descriptions.Item>
              ))}
            </Descriptions>
          </Card>
        </>
      )}

      {/* 审核入口 */}
      {caseData.status === 'pending_review' && (
        <>
          <Divider />
          <div style={{ textAlign: 'center' }}>
            <Button
              type="primary"
              size="large"
              icon={<CheckCircleOutlined />}
              onClick={() => navigate(`/cases/${caseData.id}/review`)}
            >
              进入人工授权
            </Button>
          </div>
        </>
      )}
    </div>
  )
}
