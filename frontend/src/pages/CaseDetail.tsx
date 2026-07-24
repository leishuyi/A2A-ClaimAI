import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Descriptions, Tag, Button, Space, Spin, Image, Upload,
  Select, Modal, message, Empty, Popconfirm, Tabs, Row, Col, Table, Typography,
} from 'antd'
import {
  ArrowLeftOutlined, CheckCircleOutlined, UploadOutlined,
  DeleteOutlined, EyeOutlined, FileTextOutlined, WarningOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons'
import { api } from '../api/client'
import RiskBadge from '../components/RiskBadge'
import ClaimProgress from '../components/ClaimProgress'
import AgentTraceView from '../components/AgentTrace'
import type { Case, AgentTrace, Document, DocType } from '../types'
import { DocTypeLabels } from '../types'

const { Text } = Typography

const statusMap: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '待处理' },
  processing: { color: 'processing', text: '处理中' },
  agents_completed: { color: 'blue', text: 'Agent完成' },
  pending_review: { color: 'orange', text: '待审核' },
  approved: { color: 'green', text: '已通过' },
  rejected: { color: 'red', text: '已驳回' },
}

const DocTypeColor: Record<string, string> = {
  id_card: '#1677ff', diagnosis: '#52c41a', invoice: '#faad14',
  medical_record: '#eb2f96', other: '#999',
}

export default function CaseDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [caseData, setCaseData] = useState<Case | null>(null)
  const [traces, setTraces] = useState<AgentTrace[]>([])
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [uploadModalOpen, setUploadModalOpen] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadDocType, setUploadDocType] = useState<DocType>('other')
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('overview')

  const loadData = () => {
    if (!id) return
    setLoading(true)
    Promise.all([
      api.getCase(Number(id)),
      api.getTraces(Number(id)),
      api.getDocuments(Number(id)),
    ]).then(([c, t, d]) => {
      setCaseData(c)
      setTraces(t)
      setDocuments(d)
    }).finally(() => setLoading(false))
  }

  useEffect(() => { loadData() }, [id])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />
  if (!caseData) return <Empty description="案件不存在" style={{ marginTop: 100 }} />

  const summaryTrace = traces.find(t => t.agent_name === 'agent_f_summary')
  const docTrace = traces.find(t => t.agent_name === 'agent_b_doc_parser') as any
  const riskTrace = traces.find(t => t.agent_name === 'agent_e_risk') as any

  const isImage = (doc: Document) =>
    doc.mime_type?.startsWith('image/') || /\.(jpg|jpeg|png|bmp|tiff?)$/i.test(doc.file_name)

  const handleUpload = async (file: File) => {
    setUploading(true)
    try {
      await api.uploadDocument(caseData.id, file, uploadDocType)
      message.success('上传成功')
      loadData()
      setUploadModalOpen(false)
    } catch (err: any) { message.error(err.message || '上传失败') }
    finally { setUploading(false) }
    return false
  }

  const handleDelete = async (doc: Document) => {
    try {
      await api.deleteDocument(caseData.id, doc.id)
      message.success('已删除')
      loadData()
    } catch (err: any) { message.error(err.message || '删除失败') }
  }

  // ── Tabs content ──

  const overviewTab = (
    <div>
      {/* Claim Progress */}
      <ClaimProgress status={caseData.status} />

      {/* Case Summary Card */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Descriptions column={{ xs: 1, sm: 2, md: 3 }} bordered size="small">
          <Descriptions.Item label="出险人">{caseData.insured_name}</Descriptions.Item>
          <Descriptions.Item label="险种">{caseData.insurance_product}</Descriptions.Item>
          <Descriptions.Item label="出险日期">
            {new Date(caseData.incident_date).toLocaleDateString('zh-CN')}
          </Descriptions.Item>
          <Descriptions.Item label="医疗总费用" span={1}>
            {caseData.total_amount ? <Text strong>¥{caseData.total_amount.toLocaleString()}</Text> : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="理算金额（AI建议）" span={1}>
            {caseData.calculated_amount
              ? <Text strong style={{ color: '#1677ff' }}>¥{caseData.calculated_amount.toLocaleString()}</Text>
              : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="报案时间">
            {new Date(caseData.created_at).toLocaleString('zh-CN')}
          </Descriptions.Item>
          <Descriptions.Item label="出险描述" span={3}>
            {caseData.incident_desc}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* AI Summary */}
      {((summaryTrace?.output_data as any)?.case_summary) && (
        <Card size="small" style={{ marginBottom: 16, background: '#f6ffed', border: '1px solid #b7eb8f' }}>
          <Space>
            <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 16 }} />
            <span style={{ fontWeight: 500 }}>AI 处理摘要</span>
          </Space>
          <div style={{ marginTop: 8, color: '#666' }}>
            {String((summaryTrace?.output_data as any)?.case_summary || "")}
          </div>
        </Card>
      )}

      {/* Agent Trace */}
      <Card title="Agent 全链路追溯" size="small" style={{ marginBottom: 16 }}>
        <AgentTraceView traces={traces} loading={false} />
      </Card>

      {/* Risk Findings */}
      {((riskTrace?.output_data as any)?.risk_findings) && (
        <Card title="风控审查结果" size="small" style={{ marginBottom: 16 }}>
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

      {/* Human Gate Entry */}
      {caseData.status === 'pending_review' && (
        <div style={{ textAlign: 'center', marginTop: 16 }}>
          <Button type="primary" size="large" icon={<SafetyCertificateOutlined />}
            onClick={() => navigate(`/cases/${caseData.id}/review`)}>
            进入人工授权
          </Button>
        </div>
      )}
    </div>
  )

  const documentsTab = (
    <div>
      <div style={{ textAlign: 'right', marginBottom: 16 }}>
        <Button icon={<UploadOutlined />} onClick={() => setUploadModalOpen(true)}>上传影像</Button>
      </div>
      {documents.length === 0 ? (
        <Empty description="暂无影像材料" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <Row gutter={[16, 16]}>
          {documents.map(doc => (
            <Col key={doc.id} xs={12} sm={8} md={6} lg={4}>
              <Card
                hoverable
                size="small"
                cover={
                  <div style={{ height: 140, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#fafafa', cursor: isImage(doc) ? 'pointer' : 'default' }}
                    onClick={() => isImage(doc) && setPreviewUrl(doc.url)}>
                    {isImage(doc) ? (
                      <Image src={doc.url} alt={doc.file_name} style={{ maxWidth: '100%', maxHeight: 130, objectFit: 'contain' }}
                        preview={false}
                        fallback="data:image/png;base64,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"
                      />
                    ) : (
                      <div style={{ textAlign: 'center', color: '#999' }}>
                        <FileTextOutlined style={{ fontSize: 32 }} />
                        <div style={{ fontSize: 12, marginTop: 4 }}>PDF</div>
                      </div>
                    )}
                  </div>
                }
                actions={[
                  isImage(doc) ? <EyeOutlined key="preview" onClick={() => setPreviewUrl(doc.url)} /> : null,
                  <Popconfirm key="del" title="确定删除？" onConfirm={() => handleDelete(doc)}>
                    <DeleteOutlined style={{ color: '#ff4d4f' }} />
                  </Popconfirm>,
                ].filter(Boolean)}
              >
                <Card.Meta
                  title={<Tag color={DocTypeColor[doc.doc_type] ?? '#999'} style={{ fontSize: 11, marginBottom: 0 }}>
                    {DocTypeLabels[doc.doc_type] ?? doc.doc_type}
                  </Tag>}
                  description={
                    <div>
                      <div style={{ fontSize: 12, color: '#666', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {doc.file_name}
                      </div>
                      <div style={{ fontSize: 11, color: '#999' }}>{(doc.file_size / 1024).toFixed(0)} KB</div>
                      {doc.extracted_name && <div style={{ fontSize: 11, color: '#1677ff' }}>姓名: {doc.extracted_name}</div>}
                      {doc.invoice_no && <div style={{ fontSize: 11, color: '#faad14' }}>发票: {doc.invoice_no}</div>}
                    </div>
                  }
                />
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {/* Upload Modal */}
      <Modal title="上传影像材料" open={uploadModalOpen} onCancel={() => setUploadModalOpen(false)} footer={null} width={480}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <div style={{ marginBottom: 8 }}>文档类型：</div>
            <Select value={uploadDocType} onChange={setUploadDocType} style={{ width: '100%' }}
              options={Object.entries(DocTypeLabels).map(([k, v]) => ({ label: v, value: k }))} />
          </div>
          <Upload.Dragger multiple showUploadList beforeUpload={(f) => { handleUpload(f); return false }}
            accept=".jpg,.jpeg,.png,.bmp,.tiff,.pdf" disabled={uploading}>
            <p className="ant-upload-drag-icon"><UploadOutlined /></p>
            <p className="ant-upload-text">点击或拖拽文件上传</p>
          </Upload.Dragger>
        </Space>
      </Modal>

      {/* Image Preview */}
      {previewUrl && (
        <Image src={previewUrl} style={{ display: 'none' }}
          preview={{ visible: true, src: previewUrl, onVisibleChange: (v) => { if (!v) setPreviewUrl(null) } }} />
      )}
    </div>
  )

  const agentTab = (
    <div>
      <AgentTraceView traces={traces} loading={false} />
      {((docTrace?.output_data as any)?.documents_parsed) && (
        <Card title="材料解析结果" size="small" style={{ marginTop: 16 }}>
          <Table dataSource={docTrace.output_data.documents_parsed as any[]} rowKey="type" pagination={false} size="small"
            columns={[
              { title: '文档类型', dataIndex: 'type', width: 120 },
              {
                title: '状态', dataIndex: 'status', width: 100,
                render: (v: string) => <Tag color="green">{v}</Tag>,
              },
              {
                title: '置信度', dataIndex: 'confidence', width: 100,
                render: (v: number) => (
                  <Tag color={v >= 0.95 ? 'green' : v >= 0.85 ? 'orange' : 'red'}>
                    {(v * 100).toFixed(0)}%
                  </Tag>
                ),
              },
              { title: '文件名', dataIndex: 'file_name' },
            ]} />
        </Card>
      )}
      {((riskTrace?.output_data as any)?.risk_findings) && (
        <Card title="风控审查结果" size="small" style={{ marginTop: 16 }}>
          <Table dataSource={riskTrace.output_data.risk_findings as any[]} rowKey="rule" pagination={false} size="small"
            columns={[
              { title: '检查项', dataIndex: 'rule', width: 120 },
              { title: '风险', dataIndex: 'risk', width: 80,
                render: (v: string) => <Tag color={v === 'low' ? 'green' : v === 'medium' ? 'orange' : 'red'}>{v}</Tag> },
              { title: '详情', dataIndex: 'detail' },
            ]} />
        </Card>
      )}
    </div>
  )

  const tabItems = [
    { key: 'overview', label: '案件概览', children: overviewTab },
    { key: 'documents', label: `影像材料 (${documents.length})`, children: documentsTab },
    { key: 'agents', label: 'Agent 链路', children: agentTab },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/cases')}>返回列表</Button>
      </Space>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Space size="middle">
          <span style={{ fontSize: 20, fontWeight: 600, fontFamily: 'monospace' }}>{caseData.case_no}</span>
          <Tag color={statusMap[caseData.status]?.color} style={{ fontSize: 13, padding: '2px 8px' }}>
            {statusMap[caseData.status]?.text}
          </Tag>
          <RiskBadge level={caseData.risk_level} />
        </Space>
      </div>

      {/* Main Content */}
      <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
    </div>
  )
}
