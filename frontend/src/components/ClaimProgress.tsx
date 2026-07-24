import { Card, Steps, Tag, Space, Typography } from 'antd'
import {
  FileTextOutlined, SearchOutlined, TeamOutlined,
  CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined,
} from '@ant-design/icons'

const { Text } = Typography

interface Props {
  status: string
}

const stepsConfig: Record<string, { title: string; description: string; icon: any }> = {
  draft: { title: '已报案', description: '报案已提交，等待系统处理', icon: FileTextOutlined },
  processing: { title: '处理中', description: 'AI 正在识别材料并判断责任', icon: SearchOutlined },
  pending_review: { title: '待审核', description: '核赔人员正在审核中', icon: TeamOutlined },
  approved: { title: '已通过', description: '审核通过，等待付款', icon: CheckCircleOutlined },
  rejected: { title: '已驳回', description: '审核未通过', icon: CloseCircleOutlined },
}

const statusOrder = ['draft', 'processing', 'pending_review', 'approved', 'rejected']

export default function ClaimProgress({ status }: Props) {
  const currentIdx = statusOrder.indexOf(status)
  const isRejected = status === 'rejected'

  return (
    <Card size="small" style={{ marginBottom: 16 }}>
      <Space style={{ marginBottom: 12 }}>
        <Text strong style={{ fontSize: 15 }}>理赔进度</Text>
        <Tag color={
          status === 'approved' ? 'green' : status === 'rejected' ? 'red' :
          status === 'pending_review' ? 'orange' : 'processing'
        }>
          {stepsConfig[status]?.title || status}
        </Tag>
      </Space>
      <Steps
        current={isRejected ? 3 : Math.min(currentIdx, 3)}
        status={isRejected ? 'error' : 'process'}
        size="small"
        items={[
          {
            title: '提交报案',
            description: '已提交理赔申请',
            icon: <FileTextOutlined />,
            status: currentIdx >= 0 ? 'finish' : 'wait',
          },
          {
            title: 'AI 识别处理',
            description: currentIdx >= 1 ? '材料识别完成' : '等待处理中',
            icon: <SearchOutlined />,
            status: currentIdx >= 1 ? 'finish' : currentIdx === 0 ? 'process' : 'wait',
          },
          {
            title: isRejected ? '审核未通过' : '人工审核',
            description: isRejected ? '已驳回，请查看原因' :
              currentIdx >= 2 ? '核赔人员审核中' : '等待审核',
            icon: isRejected ? <CloseCircleOutlined /> : <TeamOutlined />,
            status: isRejected ? 'error' : currentIdx >= 3 ? 'finish' :
              currentIdx >= 2 ? 'process' : 'wait',
          },
          {
            title: isRejected ? '已结束' : '审核完成',
            description: isRejected ? '本次理赔流程结束' :
              status === 'approved' ? '已通过，等待付款' : '尚未完成',
            icon: isRejected ? <CloseCircleOutlined /> : <CheckCircleOutlined />,
            status: currentIdx >= 3 ? 'finish' : 'wait',
          },
        ]}
      />
    </Card>
  )
}
