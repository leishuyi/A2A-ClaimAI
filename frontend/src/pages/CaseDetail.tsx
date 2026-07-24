import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Descriptions, Tag, Button, Space, Spin, Divider, Image, Modal,
  Upload, Select, message, Empty, Popconfirm,
} from 'antd'
import { ArrowLeftOutlined, CheckCircleOutlined, UploadOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons'
import { api } from '../api/client'
import RiskBadge from '../components/RiskBadge'
import AgentTraceView from '../components/AgentTrace'
import DocumentViewer from '../components/DocumentViewer'
import type { Case, AgentTrace, Document, DocType } from '../types'
import { DocTypeLabels } from '../types'

const statusMap: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '待处理' },
  processing: { color: 'processing', text: '处理中' },
  agents_completed: { color: 'blue', text: 'Agent完成' },
  pending_review: { color: 'orange', text: '待审核' },
  approved: { color: 'green', text: '已通过' },
  rejected: { color: 'red', text: '已驳回' },
}

const DocTypeColor: Record<DocType, string> = {
  id_card: '#1677ff',
  diagnosis: '#52c41a',
  invoice: '#faad14',
  medical_record: '#eb2f96',
  other: '#999999',
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
  if (!caseData) return <div>案件不存在</div>

  const summaryTrace = traces.find(t => t.agent_name === 'agent_f_summary')
  const docTrace = traces.find(t => t.agent_name === 'agent_b_doc_parser')

  const handleUpload = async (file: File) => {
    setUploading(true)
    try {
      await api.uploadDocument(caseData.id, file, uploadDocType)
      message.success('上传成功')
      loadData()
      setUploadModalOpen(false)
    } catch (err: any) {
      message.error(err.message || '上传失败')
    } finally {
      setUploading(false)
    }
    return false
  }

  const handleDelete = async (doc: Document) => {
    try {
      await api.deleteDocument(caseData.id, doc.id)
      message.success('已删除')
      loadData()
    } catch (err: any) {
      message.error(err.message || '删除失败')
    }
  }

  const isImage = (doc: Document) =>
    doc.mime_type?.startsWith('image/') || /\.(jpg|jpeg|png|bmp|tiff?)$/i.test(doc.file_name)

  const isPdf = (doc: Document) =>
    doc.mime_type === 'application/pdf' || /\.pdf$/i.test(doc.file_name)

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

      {/* 影像材料 */}
      <Card
        title="影像材料"
        size="small"
        extra={
          <Button size="small" icon={<UploadOutlined />} onClick={() => setUploadModalOpen(true)}>
            上传影像
          </Button>
        }
      >
        {documents.length === 0 ? (
          <Empty description="暂无影像材料" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
            {documents.map((doc) => (
              <div
                key={doc.id}
                style={{
                  width: 180, border: '1px solid #f0f0f0', borderRadius: 8,
                  overflow: 'hidden', background: '#fafafa',
                }}
              >
                {/* 缩略图/图标 */}
                <div
                  style={{
                    height: 120, display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: '#fff', cursor: isImage(doc) ? 'pointer' : 'default',
                  }}
                  onClick={() => {
                    if (isImage(doc)) {
                      setPreviewUrl(doc.url)
                    }
                  }}
                >
                  {isImage(doc) ? (
                    <Image
                      src={doc.url}
                      alt={doc.file_name}
                      style={{ maxWidth: '100%', maxHeight: 120, objectFit: 'contain' }}
                      preview={false}
                      fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAYAAABw4pVUAAAAAXNSR0IArs4c6QAABaVJREFUeF7tnU9u00AUh7+OoqScgC2q6AVYEhZI3LEDFkgckU07UKW0hx6hcY7QHIEj0J4B2rArLQtW/AkYq0JEJ0mcZ8d2HDtvPPZn2/PyFk3azNhvfr+Z9+a9SSzL4h8NEAABEAABGlH2n6cUQQAEQIAGhIEABCAAASmAMAQCs4PAONL9NI1pFMd0H4vnSf6Lx+SSSAgpBMhMPowjih4e6P32lu5OT+hDGFHbaJLtpC9/QwiZ1UHu0kQ3d0k8HtBbu6Ll0iV9rNdoo14n0uA80sL7UZ9u+h16H8YEAtZvIZdJTJdJTB6CAQMQAAE9AghBz4K3IAACIEAIQRGAAAQgIAWQEEAABAoQQAgKQiAAAQgIAYQgCIAACKSTkC9hRJdRggoBgekQmEtoILbV4D0UQaAQBGxLCJmQkCPtL2FEP90evY9iijSaaogZbEAgJwK2JYRMSMgB9JewTz/dHn3cC1lXaUAz4xkE5kOAav0+fbCiEQu5fBP2qVeJOiPWHPRL8xkKsQiBfAiMhTxYY2IDgbAIAAh9PViHwFwI5EN4TCFkQkI+8kH3W2H0V8L+zZQu40Q3NYJCBgRAoAICU/Mh14CAgJkBgQnNw0L2VF8DYkI+L0G/+0E80n0Nk5CZ4Q3msyAwASAfc6EDYkI+MaH99eGbl03KmkJ+wxUiYLAMw8mHkAvBpQkImAoQ7dQICgkBMwMCY2s4+QohZEJCPs2h9uFSs0Hn6/V3W+X2w+fjYzrt9+nN9hY1ajW6igb09c8fehNFdNJuE43T7aP3vyh5t01P0ggmF/J5EqYRYR0QmB0B7dQICqkUAmazkAkJ+fLy5Yv/4k0mB5QqIY+bTdo4PqZv7TYVZSEmk/W63T5HnskIQqokZNLtkzRjKg2FAAAgAElEQVT+TJKEdB0iL3XQbDQIuZvwk4emO+bKQn5E6vl5Sld2m36dnVHa7ZJdr9Pqygqt2jY5jkNLS0u0uLhI9XqdbNsm0zTz5k6IEHI96lP8lC4vnfX7RB6bG3Ih0SQfE6VTIzYhk5Kw8cjA31hdpePeKb1/u0urLzeosb5Og6srOjw8pN57j46Pj+nq6oqGwyHxY4VCUkg2pPk+r25u0t7eHq2urpK5YYaFhEy4fZKK6W4Z5hEyNol8TPA2hU7bXRNSv0mH5HHYX+cYYhHyZ2eH3m5tUbPZJNu2yeM3Gg35gnl5eUkXFxfk+z5dXFzQ+/fv6ezsjHzfJ4/HeQxBbFZWiOO10Dz3OTExQ5gH5iUiFOZ5VqtV2tzepp3dXQo4F2JrLkIajQa1223iB5NUI8MHRxHzPI8ajYb2INM0p8opZiG8O9d1hymkCBE+r4h5nidUKokbcx2WYp7nScVi2qvF1AhxHEc7iq9CzBRFEpmM2bCvYpgXMvGB08UwK0Q8n4phXoh4PhXDvBDxfCqGeSHi+VQM80LE86kY5oWI51MxzAsRz6dimBcink/FMC9EPJ+KYV6IeD4Vw7wQ8Xwqhnkh4vlUDPNCxPOpGOaFiOdTMcwLEc+nYpgXIp5PxTAvRDyfimFeiHg+FcO8EPF8KoZ5IeL5VAzzQsTzVS5z3TCMQg1QMa1S2GZbmVqWYRhc9ViYGKbte1qY7XgQJQZIGOYJiRkDYibk5uZG2yTjB51MJh5bLNOyrCwb9fV6nRKTYWKAF8MqI2R8Ml+EkPj6mgzDkP1fFcO0CJGMCAGMADIDTBlCxkn7OgSqIKSqWP0WsipWf4RULcRsirYQMJsFMZsFYhNiNkN3ITMo5+4mhITM4Jc7bKJmQkImJHLTLHhf2UJK4D9jxi5kGmIFi+cT+j36H2YqmL1Iu4R9AAAAAElFTkSuQmCC"
                    />
                  ) : (
                    <div style={{ textAlign: 'center', color: '#999' }}>
                      <div style={{ fontSize: 32, marginBottom: 4 }}>
                        {isPdf(doc) ? '📄' : '📎'}
                      </div>
                      <div style={{ fontSize: 12 }}>{isPdf(doc) ? 'PDF' : '其他'}</div>
                    </div>
                  )}
                </div>
                {/* 文档信息 */}
                <div style={{ padding: '6px 8px' }}>
                  <Tag color={DocTypeColor[doc.doc_type] ?? '#999'} style={{ fontSize: 11, marginBottom: 4 }}>
                    {DocTypeLabels[doc.doc_type] ?? doc.doc_type}
                  </Tag>
                  <div style={{ fontSize: 12, color: '#666', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {doc.file_name}
                  </div>
                  <div style={{ fontSize: 11, color: '#999' }}>
                    {(doc.file_size / 1024).toFixed(0)} KB
                  </div>
                  <Space size={4} style={{ marginTop: 4 }}>
                    {isImage(doc) && (
                      <Button size="small" type="text" icon={<EyeOutlined />}
                        onClick={() => setPreviewUrl(doc.url)}
                      />
                    )}
                    <Popconfirm title="确定删除此影像？" onConfirm={() => handleDelete(doc)}>
                      <Button size="small" type="text" danger icon={<DeleteOutlined />} />
                    </Popconfirm>
                  </Space>
                </div>
              </div>
            ))}
          </div>
        )}
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

      {/* 上传弹窗 */}
      <Modal
        title="上传影像材料"
        open={uploadModalOpen}
        onCancel={() => setUploadModalOpen(false)}
        footer={null}
        width={480}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <div style={{ marginBottom: 8 }}>文档类型：</div>
            <Select
              value={uploadDocType}
              onChange={setUploadDocType}
              style={{ width: '100%' }}
              options={Object.entries(DocTypeLabels).map(([k, v]) => ({ label: v, value: k }))}
            />
          </div>
          <Upload.Dragger
            multiple
            showUploadList={true}
            beforeUpload={(file) => {
              handleUpload(file)
              return false
            }}
            accept=".jpg,.jpeg,.png,.bmp,.tiff,.pdf"
            disabled={uploading}
          >
            <p className="ant-upload-drag-icon"><UploadOutlined /></p>
            <p className="ant-upload-text">点击或拖拽文件上传</p>
          </Upload.Dragger>
        </Space>
      </Modal>

      {/* 图片预览 */}
      {previewUrl && (
        <Image
          src={previewUrl}
          style={{ display: 'none' }}
          preview={{
            visible: true,
            src: previewUrl,
            onVisibleChange: (v) => { if (!v) setPreviewUrl(null) },
          }}
        />
      )}
    </div>
  )
}
