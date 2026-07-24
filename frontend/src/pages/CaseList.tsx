import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Table, Button, Modal, Form, Input, DatePicker, Select,
  InputNumber, Space, Tag, message, Upload, Progress, Statistic,
  Card, Row, Col, Tabs, Steps, Result, Typography, Divider, List,
  Descriptions,
} from 'antd'
import {
  PlusOutlined, PlayCircleOutlined, EyeOutlined, InboxOutlined,
  BulbOutlined, FileTextOutlined, DollarOutlined, CheckCircleOutlined,
  SafetyCertificateOutlined, RightOutlined, FileDoneOutlined,
  UserOutlined, MedicineBoxOutlined, WalletOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { api } from '../api/client'
import RiskBadge from '../components/RiskBadge'
import type { Case, DocType } from '../types'
import { DocTypeLabels } from '../types'

const { Text, Title } = Typography
const { Dragger } = Upload
const { Step } = Steps

const statusMap: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '待处理' },
  processing: { color: 'processing', text: '处理中' },
  agents_completed: { color: 'blue', text: 'Agent完成' },
  pending_review: { color: 'orange', text: '待审核' },
  approved: { color: 'green', text: '已通过' },
  rejected: { color: 'red', text: '已驳回' },
}

// ── 模拟保单数据 ──
const MOCK_POLICIES = [
  { id: 'POL2024001', product: '住院医疗险A', insured: '张三', holder: '张三', start: '2024-01-01', end: '2024-12-31', amount: 100000, premium: 680 },
  { id: 'POL2024002', product: '住院医疗险B', insured: '张三', holder: '张三', start: '2024-01-01', end: '2024-12-31', amount: 200000, premium: 1280 },
  { id: 'POL2024003', product: '意外医疗险', insured: '张三(子女)', holder: '张三', start: '2024-03-01', end: '2024-12-31', amount: 50000, premium: 320 },
  { id: 'POL2024004', product: '重疾险', insured: '张三', holder: '张三', start: '2024-01-01', end: '2024-12-31', amount: 500000, premium: 4500 },
]

const MOCK_CLAIMANT_INFO = {
  name: '张三',
  id_card: '110101199001011234',
  phone: '138****8000',
  bank_card: '**** **** **** 6789',
}

interface FileItem {
  uid: string; file: File; docType: DocType
  status: 'pending' | 'uploading' | 'done' | 'error'
  progress: number; errorMsg?: string
  extractedName?: string; invoiceNo?: string; documentDate?: string
}

export default function CaseList() {
  const [cases, setCases] = useState<Case[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()
  const [submitting, setSubmitting] = useState(false)
  const [intentText, setIntentText] = useState('')
  const [fileItems, setFileItems] = useState<FileItem[]>([])
  const [statusFilter, setStatusFilter] = useState('')
  const [step, setStep] = useState(0)               // 报案向导步骤
  const [selectedPolicy, setSelectedPolicy] = useState<string | null>(null)
  const [submitResult, setSubmitResult] = useState<any>(null) // 提交结果
  const navigate = useNavigate()

  const load = async (p = 1) => {
    setLoading(true)
    try {
      const params: any = { page: p, page_size: 20 }
      if (statusFilter) params.status = statusFilter
      const data = await api.getCases(params)
      setCases(data.items)
      setTotal(data.total)
      setPage(data.page)
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [statusFilter])

  const stats = {
    total: cases.length,
    pendingReview: cases.filter(c => c.status === 'pending_review').length,
    approved: cases.filter(c => c.status === 'approved').length,
    totalAmount: cases.reduce((s, c) => s + (c.total_amount || 0), 0),
  }

  // ── 提交报案 ──
  const handleSubmit = async () => {
    const values = await form.validateFields()
    const policy = MOCK_POLICIES.find(p => p.id === selectedPolicy)
    setSubmitting(true)
    try {
      const newCase = await api.createCase({
        insured_name: policy?.insured || values.insured_name,
        insurance_product: policy?.product || values.insurance_product,
        incident_desc: values.incident_desc,
        incident_date: values.incident_date.format('YYYY-MM-DD'),
        total_amount: values.total_amount,
      })
      const caseId = newCase.id

      // Upload files
      let uploadOk = true
      for (const item of fileItems) {
        setFileItems(prev => prev.map(f =>
          f.uid === item.uid ? { ...f, status: 'uploading', progress: 0 } : f
        ))
        try {
          await api.uploadDocument(caseId, item.file, item.docType,
            { extracted_name: item.extractedName, invoice_no: item.invoiceNo, document_date: item.documentDate },
            (pct) => setFileItems(prev => prev.map(f =>
              f.uid === item.uid ? { ...f, progress: pct } : f
            )))
          setFileItems(prev => prev.map(f =>
            f.uid === item.uid ? { ...f, status: 'done', progress: 100 } : f
          ))
        } catch {
          uploadOk = false
          setFileItems(prev => prev.map(f => f.uid === item.uid ? { ...f, status: 'error' } : f))
        }
      }

      // Auto-trigger Agent chain
      try {
        await api.runAgents(caseId)
      } catch { /* agent processing will show as draft */ }

      setSubmitResult({ caseNo: newCase.case_no, caseId: newCase.id, uploadOk, fileCount: fileItems.length })
      setStep(4) // Show result step
      load()
    } catch (err: any) {
      message.error(err.message || '报案失败')
    } finally { setSubmitting(false) }
  }

  const resetModal = () => {
    setModalOpen(false)
    setStep(0)
    setSelectedPolicy(null)
    setSubmitResult(null)
    form.resetFields()
    setFileItems([])
    setIntentText('')
  }

  const handleFileDrop = (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (!ext || !['jpg', 'jpeg', 'png', 'bmp', 'tiff', 'pdf'].includes(ext)) { message.error(`不支持 .${ext}`); return false }
    if (file.size > 10 * 1024 * 1024) { message.error('文件不能超过 10MB'); return false }
    setFileItems(prev => [...prev, { uid: `${Date.now()}_${Math.random().toString(36).slice(2)}`, file, docType: 'other', status: 'pending', progress: 0 }])
    return false
  }

  const selectedPolicyData = MOCK_POLICIES.find(p => p.id === selectedPolicy)

  // ── 渲染步骤内容 ──
  const renderStepContent = () => {
    switch (step) {
      case 0: return (
        <div>
          <Title level={5}><SafetyCertificateOutlined style={{ marginRight: 8 }} />选择保单</Title>
          <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>请选择需要理赔的保单：</Text>
          <List
            dataSource={MOCK_POLICIES}
            renderItem={p => (
              <List.Item
                key={p.id}
                onClick={() => setSelectedPolicy(p.id)}
                style={{
                  cursor: 'pointer', padding: '12px 16px', borderRadius: 8,
                  border: selectedPolicy === p.id ? '2px solid #1677ff' : '1px solid #f0f0f0',
                  background: selectedPolicy === p.id ? '#f0f5ff' : '#fff',
                  marginBottom: 8, transition: 'all 0.2s',
                }}
              >
                <List.Item.Meta
                  avatar={<SafetyCertificateOutlined style={{ fontSize: 24, color: selectedPolicy === p.id ? '#1677ff' : '#999' }} />}
                  title={<span style={{ fontWeight: selectedPolicy === p.id ? 600 : 400 }}>{p.product}</span>}
                  description={
                    <Space size={16}>
                      <span>被保人: {p.insured}</span>
                      <span>保额: ¥{p.amount.toLocaleString()}</span>
                      <span>有效期: {p.start} ~ {p.end}</span>
                    </Space>
                  }
                />
                {selectedPolicy === p.id && <CheckCircleOutlined style={{ color: '#1677ff', fontSize: 20 }} />}
              </List.Item>
            )}
          />
        </div>
      )

      case 1: return (
        <div>
          <Title level={5}><MedicineBoxOutlined style={{ marginRight: 8 }} />出险信息</Title>
          <div style={{ padding: '8px 12px', background: '#f6ffed', borderRadius: 6, marginBottom: 16, border: '1px solid #b7eb8f' }}>
            <Text strong>保单: {selectedPolicyData?.product}</Text>
            <Text style={{ marginLeft: 16, color: '#666' }}>被保人: {selectedPolicyData?.insured}</Text>
          </div>

          {/* Smart fill */}
          <div style={{ marginBottom: 16, padding: '10px 12px', background: '#f0f5ff', borderRadius: 6, border: '1px solid #d6e4ff' }}>
            <Text style={{ fontSize: 13, color: '#1677ff' }}><BulbOutlined style={{ marginRight: 6 }} />智能填写</Text>
            <Input.TextArea rows={2} placeholder="输入自然语言快速填写，如：急性阑尾炎住院花了12500"
              value={intentText} onChange={e => setIntentText(e.target.value)}
              style={{ marginTop: 6 }} />
            <Button size="small" type="primary" ghost icon={<BulbOutlined />}
              style={{ marginTop: 6 }} disabled={!intentText.trim()}
              onClick={async () => {
                try {
                  const res = await api.classifyIntent(intentText)
                  const entities = res.data.extracted_entities || {}
                  const vals: any = {}
                  if (entities.name?.[0]) vals.insured_name = entities.name[0]
                  if (entities.name_candidate?.[0]) vals.insured_name = entities.name_candidate[0]
                  if (entities.amount?.[0]) vals.total_amount = parseFloat(entities.amount[0]) || undefined
                  if (!vals.insured_name) vals.incident_desc = intentText
                  form.setFieldsValue(vals)
                  message.info(`识别为: ${res.data.intent_label}`)
                } catch { message.error('识别失败') }
              }}>
              识别并填充
            </Button>
          </div>

          <Form form={form} layout="vertical">
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item name="insured_name" label="出险人" rules={[{ required: true }]}
                  initialValue={selectedPolicyData?.insured || ''}>
                  <Input placeholder="出险人姓名" prefix={<UserOutlined />} />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="incident_date" label="出险日期" rules={[{ required: true }]}>
                  <DatePicker style={{ width: '100%' }} />
                </Form.Item>
              </Col>
            </Row>
            <Form.Item name="incident_desc" label="出险描述" rules={[{ required: true }]}>
              <Input.TextArea rows={3} placeholder="描述出险经过、诊断结果、就诊医院等" />
            </Form.Item>
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item name="total_amount" label="医疗总费用">
                  <InputNumber style={{ width: '100%' }} min={0} placeholder="请输入总费用" prefix="¥" />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item label="就诊医院">
                  <Input placeholder="医院名称（可选）" />
                </Form.Item>
              </Col>
            </Row>
          </Form>
        </div>
      )

      case 2: return (
        <div>
          <Title level={5}><InboxOutlined style={{ marginRight: 8 }} />上传影像资料</Title>
          <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
            请上传以下材料（支持 JPG/PNG/BMP/PDF，单文件 ≤10MB）
          </Text>

          <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
            {[{ key: 'id_card', label: '身份证' }, { key: 'diagnosis', label: '诊断证明' },
              { key: 'invoice', label: '费用发票' }, { key: 'medical_record', label: '住院病历' },
            ].map(dt => (
              <Col span={6} key={dt.key}>
                <div style={{
                  padding: '12px 8px', textAlign: 'center', borderRadius: 6, cursor: 'pointer',
                  border: fileItems.some(f => f.docType === dt.key) ? '2px solid #52c41a' : '1px dashed #d9d9d9',
                  background: fileItems.some(f => f.docType === dt.key) ? '#f6ffed' : '#fafafa',
                  transition: 'all 0.2s',
                }}>
                  <FileTextOutlined style={{ fontSize: 20, color: fileItems.some(f => f.docType === dt.key) ? '#52c41a' : '#999' }} />
                  <div style={{ fontSize: 13, marginTop: 4 }}>{dt.label}</div>
                  {fileItems.some(f => f.docType === dt.key) && <Tag color="green" style={{ marginTop: 4 }}>已上传</Tag>}
                </div>
              </Col>
            ))}
          </Row>

          <Dragger multiple showUploadList={false} beforeUpload={handleFileDrop}
            accept=".jpg,.jpeg,.png,.bmp,.tiff,.pdf">
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <p className="ant-upload-text">点击或拖拽文件到此处上传</p>
            <p className="ant-upload-hint">可一次选择多份文件</p>
          </Dragger>

          {fileItems.map(item => (
            <div key={item.uid} style={{ padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Select size="small" value={item.docType}
                  onChange={v => setFileItems(prev => prev.map(f => f.uid === item.uid ? { ...f, docType: v } : f))}
                  style={{ width: 100 }}
                  options={Object.entries(DocTypeLabels).map(([k, v]) => ({ label: v, value: k }))} />
                <span style={{ flex: 1, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {item.file.name}
                </span>
                <span style={{ color: '#999', fontSize: 12 }}>{(item.file.size / 1024).toFixed(0)} KB</span>
                {item.status === 'uploading' && <Progress size="small" style={{ width: 80 }} percent={item.progress} />}
                {item.status === 'done' && <Tag color="green">已上传</Tag>}
                {item.status === 'error' && <Tag color="red">失败</Tag>}
                {item.status === 'pending' && (
                  <Button size="small" danger onClick={() => setFileItems(prev => prev.filter(f => f.uid !== item.uid))}>移除</Button>
                )}
              </div>
              {item.status === 'pending' && (
                <div style={{ display: 'flex', gap: 8, marginLeft: 4, marginTop: 4 }}>
                  <Input size="small" placeholder="姓名" style={{ width: 100 }} value={item.extractedName}
                    onChange={e => setFileItems(prev => prev.map(f => f.uid === item.uid ? { ...f, extractedName: e.target.value } : f))} />
                  {item.docType === 'invoice' && (
                    <Input size="small" placeholder="发票号" style={{ width: 120 }} value={item.invoiceNo}
                      onChange={e => setFileItems(prev => prev.map(f => f.uid === item.uid ? { ...f, invoiceNo: e.target.value } : f))} />
                  )}
                  <DatePicker size="small" placeholder="日期" style={{ width: 120 }}
                    value={item.documentDate ? dayjs(item.documentDate) : null}
                    onChange={d => setFileItems(prev => prev.map(f => f.uid === item.uid ? { ...f, documentDate: d?.format('YYYY-MM-DD') } : f))} />
                </div>
              )}
            </div>
          ))}
        </div>
      )

      case 3: return (
        <div>
          <Title level={5}><FileDoneOutlined style={{ marginRight: 8 }} />确认报案信息</Title>
          <Divider />
          <Descriptions column={2} size="small" bordered>
            <Descriptions.Item label="保单号">{selectedPolicy}</Descriptions.Item>
            <Descriptions.Item label="险种">{selectedPolicyData?.product}</Descriptions.Item>
            <Descriptions.Item label="出险人">{selectedPolicyData?.insured}</Descriptions.Item>
            <Descriptions.Item label="出险日期">{form.getFieldValue('incident_date')?.format('YYYY-MM-DD')}</Descriptions.Item>
            <Descriptions.Item label="医疗费用" span={2}>
              ¥{form.getFieldValue('total_amount')?.toLocaleString() || '待定'}
            </Descriptions.Item>
            <Descriptions.Item label="上传文件" span={2}>{fileItems.length} 份</Descriptions.Item>
            <Descriptions.Item label="出险描述" span={2}>{form.getFieldValue('incident_desc')}</Descriptions.Item>
          </Descriptions>
          <Divider />
          <Text type="secondary">提交后系统将自动进行材料识别和责任判断，预计 1-3 分钟完成初审。</Text>
        </div>
      )

      case 4: return (
        <Result
          status="success"
          title="报案成功"
          subTitle={`案件编号: ${submitResult?.caseNo}，已自动进入审核流程`}
          extra={[
            <Button type="primary" key="detail" onClick={() => {
              resetModal()
              navigate(`/cases/${submitResult?.caseId}`)
            }}>
              查看案件详情
            </Button>,
            <Button key="list" onClick={resetModal}>返回案件列表</Button>,
          ]}
        >
          <div style={{ background: '#f6ffed', padding: 12, borderRadius: 6 }}>
            <Text><CheckCircleOutlined style={{ color: '#52c41a', marginRight: 8 }} />
              已提交 {submitResult?.fileCount || 0} 份影像材料
            </Text>
            <br />
            <Text><CheckCircleOutlined style={{ color: '#52c41a', marginRight: 8 }} />
              Agent 自动处理链路已启动
            </Text>
            <br />
            <Text><CheckCircleOutlined style={{ color: '#52c41a', marginRight: 8 }} />
              审核完成后将通知您
            </Text>
          </div>
        </Result>
      )
    }
  }

  return (
    <div>
      {/* Stats Cards */}
      <Row gutter={16} style={{ marginBottom: 20 }}>
        <Col xs={12} sm={6}>
          <Card size="small" hoverable>
            <Statistic title="待审核" value={stats.pendingReview} valueStyle={{ color: '#faad14' }} prefix={<FileTextOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small" hoverable>
            <Statistic title="已通过" value={stats.approved} valueStyle={{ color: '#52c41a' }} prefix={<CheckCircleOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small" hoverable>
            <Statistic title="累计费用" value={stats.totalAmount} precision={0} prefix="¥" valueStyle={{ color: '#1677ff' }} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small" hoverable>
            <Statistic title="案件总数" value={total} prefix={<DollarOutlined />} />
          </Card>
        </Col>
      </Row>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Tabs activeKey={statusFilter} onChange={k => { setStatusFilter(k); setPage(1) }}
          items={[
            { key: '', label: '全部' }, { key: 'draft', label: '待处理' },
            { key: 'processing', label: '处理中' }, { key: 'pending_review', label: '待审核' },
            { key: 'approved', label: '已通过' }, { key: 'rejected', label: '已驳回' },
          ]} style={{ marginBottom: 0 }} />
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)} size="large">
          我要报案
        </Button>
      </div>

      {/* Table */}
      <Table dataSource={cases} rowKey="id" loading={loading}
        pagination={{ current: page, total, pageSize: 20, onChange: load, showTotal: t => `共 ${t} 条`, showSizeChanger: false }}
        columns={[
          { title: '案件编号', dataIndex: 'case_no', width: 160,
            render: (v: string) => <Text code>{v}</Text> },
          { title: '出险人', dataIndex: 'insured_name', width: 100 },
          { title: '险种', dataIndex: 'insurance_product', width: 130, ellipsis: true },
          { title: '状态', dataIndex: 'status', width: 110,
            render: (s: string) => <Tag color={statusMap[s]?.color}>{statusMap[s]?.text || s}</Tag> },
          { title: '风险', dataIndex: 'risk_level', width: 80,
            render: (v: string) => <RiskBadge level={v as Case['risk_level']} /> },
          { title: '医疗费', dataIndex: 'total_amount', width: 110,
            render: (v: number | null) => v != null ? `¥${v.toLocaleString()}` : '-' },
          { title: '理算金额', dataIndex: 'calculated_amount', width: 110,
            render: (v: number | null) => v != null
              ? <Text strong style={{ color: '#1677ff' }}>¥{v.toLocaleString()}</Text> : '-' },
          { title: '报案时间', dataIndex: 'created_at', width: 160,
            render: (v: string) => <Text type="secondary">{new Date(v).toLocaleString('zh-CN')}</Text> },
          {
            title: '操作', width: 150, fixed: 'right',
            render: (_: any, r: Case) => (
              <Space>
                <Button size="small" icon={<EyeOutlined />} onClick={() => navigate(`/cases/${r.id}`)}>详情</Button>
                {r.status === 'draft' && (
                  <Button size="small" type="primary" icon={<PlayCircleOutlined />}
                    onClick={async () => { await api.runAgents(r.id); message.success('Agent链路已触发'); load() }}>
                    处理
                  </Button>
                )}
              </Space>
            ),
          },
        ]}
        scroll={{ x: 1100 }}
      />

      {/* ── 报案向导 Modal ── */}
      <Modal
        title={<span style={{ fontSize: 16, fontWeight: 600 }}>申请理赔</span>}
        open={modalOpen} onCancel={resetModal}
        width={720} destroyOnClose
        footer={step < 4 ? (
          <Space>
            {step > 0 && <Button onClick={() => setStep(s => s - 1)}>上一步</Button>}
            {step < 3 ? (
              <Button type="primary" onClick={() => {
                if (step === 0 && !selectedPolicy) { message.warning('请选择保单'); return }
                if (step === 1) { form.validateFields().then(() => setStep(2)).catch(() => {}) }
                else setStep(2)
              }}>
                下一步 <RightOutlined />
              </Button>
            ) : (
              <Button type="primary" size="large" loading={submitting} onClick={handleSubmit}
                icon={<CheckCircleOutlined />}>
                确认提交报案
              </Button>
            )}
          </Space>
        ) : null}
      >
        {step < 4 && (
          <Steps current={step} size="small" style={{ marginBottom: 24 }}>
            <Step title="选择保单" icon={<SafetyCertificateOutlined />} />
            <Step title="出险信息" icon={<MedicineBoxOutlined />} />
            <Step title="上传影像" icon={<InboxOutlined />} />
            <Step title="确认提交" icon={<FileDoneOutlined />} />
          </Steps>
        )}
        {renderStepContent()}
      </Modal>
    </div>
  )
}
