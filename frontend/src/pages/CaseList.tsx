import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Table, Button, Modal, Form, Input, DatePicker, Select,
  InputNumber, Space, Tag, message, Upload, Progress,
} from 'antd'
import { PlusOutlined, PlayCircleOutlined, EyeOutlined, InboxOutlined, BulbOutlined, RobotOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { api } from '../api/client'
import RiskBadge from '../components/RiskBadge'
import type { Case, DocType } from '../types'
import { DocTypeLabels } from '../types'

const { Dragger } = Upload

const statusMap: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '待处理' },
  processing: { color: 'processing', text: '处理中' },
  agents_completed: { color: 'blue', text: 'Agent完成' },
  pending_review: { color: 'orange', text: '待审核' },
  approved: { color: 'green', text: '已通过' },
  rejected: { color: 'red', text: '已驳回' },
}

interface FileItem {
  uid: string
  file: File
  docType: DocType
  status: 'pending' | 'uploading' | 'done' | 'error'
  progress: number
  errorMsg?: string
  extractedName?: string
  invoiceNo?: string
  documentDate?: string
}

export default function CaseList() {
  const [cases, setCases] = useState<Case[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()
  const [submitting, setSubmitting] = useState(false)
  const [intentText, setIntentText] = useState("")
  const [fileItems, setFileItems] = useState<FileItem[]>([])
  const navigate = useNavigate()

  const load = async (p = 1) => {
    setLoading(true)
    try {
      const data = await api.getCases({ page: p, page_size: 20 })
      setCases(data.items)
      setTotal(data.total)
      setPage(data.page)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleCreate = async () => {
    const values = await form.validateFields()
    setSubmitting(true)
    try {
      // 1. 创建案件
      const newCase = await api.createCase({
        insured_name: values.insured_name,
        insurance_product: values.insurance_product,
        incident_desc: values.incident_desc,
        incident_date: values.incident_date.format('YYYY-MM-DD'),
        total_amount: values.total_amount,
      })
      const caseId = newCase.id

      // 2. 逐个上传文件
      let uploadOk = true
      for (const item of fileItems) {
        setFileItems(prev => prev.map(f =>
          f.uid === item.uid ? { ...f, status: 'uploading' as const, progress: 0 } : f
        ))
        try {
          await api.uploadDocument(caseId, item.file, item.docType,
            { extracted_name: item.extractedName, invoice_no: item.invoiceNo, document_date: item.documentDate },
            (pct) => {
              setFileItems(prev => prev.map(f =>
                f.uid === item.uid ? { ...f, progress: pct } : f
              ))
            })
          setFileItems(prev => prev.map(f =>
            f.uid === item.uid ? { ...f, status: 'done' as const, progress: 100 } : f
          ))
        } catch (err: any) {
          uploadOk = false
          setFileItems(prev => prev.map(f =>
            f.uid === item.uid ? { ...f, status: 'error' as const, errorMsg: err.message } : f
          ))
        }
      }

      if (uploadOk && fileItems.length > 0) {
        message.success(`报案成功，${fileItems.length} 份影像已上传`)
      } else if (fileItems.length > 0) {
        message.warning('报案成功，部分影像上传失败，可在详情页重新上传')
      } else {
        message.success('报案成功')
      }

      setModalOpen(false)
      form.resetFields()
      setFileItems([])
      load()
    } catch (err: any) {
      message.error(err.message || '报案失败')
    } finally {
      setSubmitting(false)
    }
  }

  const handleModalClose = () => {
    setModalOpen(false)
    form.resetFields()
    setFileItems([])
  }

  const handleFileDrop = (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase()
    const allowed = ['jpg', 'jpeg', 'png', 'bmp', 'tiff', 'pdf']
    if (!ext || !allowed.includes(ext)) {
      message.error(`不支持的文件类型 .${ext}`)
      return false
    }
    if (file.size > 10 * 1024 * 1024) {
      message.error('文件大小不能超过 10MB')
      return false
    }

    const newItem: FileItem = {
      uid: `${Date.now()}_${Math.random().toString(36).slice(2)}`,
      file,
      docType: 'other',
      status: 'pending',
      progress: 0,
    }
    setFileItems(prev => [...prev, newItem])
    return false // 阻止 antd 默认上传行为
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
        pagination={{
          current: page,
          total,
          pageSize: 20,
          onChange: load,
          showTotal: (t) => `共 ${t} 条`,
        }}
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
        onCancel={handleModalClose}
        onOk={handleCreate}
        confirmLoading={submitting}
        width={640}
      >
        <Form form={form} layout="vertical">
          {/* 智能填写 */}
          <div style={{ marginBottom: 16, padding: 12, background: '#f0f5ff', borderRadius: 6 }}>
            <div style={{ marginBottom: 8, fontWeight: 500, fontSize: 13 }}>
              <BulbOutlined style={{ color: '#1677ff', marginRight: 6 }} />智能填写（输入自然语言自动识别）
            </div>
            <Input.TextArea
              rows={2}
              placeholder="例如：张三住院花了12500要报销"
              value={intentText}
              onChange={e => setIntentText(e.target.value)}
            />
            <Button
              size="small" type="primary" ghost
              icon={<BulbOutlined />}
              style={{ marginTop: 6 }}
              disabled={!intentText.trim()}
              onClick={async () => {
                try {
                  const res = await api.classifyIntent(intentText)
                  const data = res.data
                  const entities = data.extracted_entities || {}
                  // 自动填充表单
                  const values: any = {}
                  if (entities.name) values.insured_name = entities.name[0]
                  if (entities.name_candidate) values.insured_name = entities.name_candidate[0]
                  if (entities.amount) values.total_amount = parseFloat(entities.amount[0]) || undefined
                  form.setFieldsValue(values)
                  message.info(`识别为: ${data.intent_label}（置信度 ${Math.round(data.confidence * 100)}%）`)
                } catch (e: any) {
                  message.error(e.message || '识别失败')
                }
              }}
            >
              识别并填充
            </Button>
          </div>

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

          {/* 影像上传区域 */}
          <div style={{ marginTop: 16 }}>
            <h4>上传影像资料</h4>
            <Dragger
              multiple
              showUploadList={false}
              beforeUpload={handleFileDrop}
              accept=".jpg,.jpeg,.png,.bmp,.tiff,.pdf"
            >
              <p className="ant-upload-drag-icon"><InboxOutlined /></p>
              <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
              <p className="ant-upload-hint">支持 JPG/PNG/BMP/TIFF/PDF，单文件最大 10MB</p>
            </Dragger>

            {fileItems.length > 0 && (
              <div style={{ marginTop: 12 }}>
                {fileItems.map((item) => (
                  <div key={item.uid}
                    style={{ padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}
                  >
                    {/* 第一行：文档类型 + 文件名 + 大小 + 操作 */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: item.status === 'pending' ? 6 : 0 }}>
                      <Select
                        size="small"
                        value={item.docType}
                        onChange={(v) => setFileItems(prev => prev.map(f =>
                          f.uid === item.uid ? { ...f, docType: v } : f
                        ))}
                        style={{ width: 100 }}
                        options={Object.entries(DocTypeLabels).map(([k, v]) => ({ label: v, value: k }))}
                      />
                      <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 13 }}>
                        {item.file.name}
                      </span>
                      <span style={{ width: 60, color: '#999', fontSize: 12 }}>
                        {(item.file.size / 1024).toFixed(0)} KB
                      </span>
                      {item.status === 'uploading' && (
                        <Progress size="small" style={{ width: 100 }} percent={item.progress} />
                      )}
                      {item.status === 'done' && <Tag color="green">已上传</Tag>}
                      {item.status === 'error' && <Tag color="red" title={item.errorMsg}>失败</Tag>}
                      {item.status === 'pending' && (
                        <Button size="small" danger onClick={() => setFileItems(prev => prev.filter(f => f.uid !== item.uid))}>移除</Button>
                      )}
                    </div>
                    {/* 第二行（待上传状态）：风控辅助字段 */}
                    {item.status === 'pending' && (
                      <div style={{ display: 'flex', gap: 8, marginLeft: 4 }}>
                        <Input
                          size="small" placeholder="文档姓名" style={{ width: 120 }}
                          value={item.extractedName}
                          onChange={(e) => setFileItems(prev => prev.map(f =>
                            f.uid === item.uid ? { ...f, extractedName: e.target.value } : f
                          ))}
                        />
                        {item.docType === 'invoice' && (
                          <Input
                            size="small" placeholder="发票号码" style={{ width: 140 }}
                            value={item.invoiceNo}
                            onChange={(e) => setFileItems(prev => prev.map(f =>
                              f.uid === item.uid ? { ...f, invoiceNo: e.target.value } : f
                            ))}
                          />
                        )}
                        <DatePicker
                          size="small" placeholder="单据日期" style={{ width: 140 }}
                          value={item.documentDate ? dayjs(item.documentDate) : null}
                          onChange={(d) => setFileItems(prev => prev.map(f =>
                            f.uid === item.uid ? { ...f, documentDate: d?.format('YYYY-MM-DD') } : f
                          ))}
                        />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </Form>
      </Modal>
    </div>
  )
}
