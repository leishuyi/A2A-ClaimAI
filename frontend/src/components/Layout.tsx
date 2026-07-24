import { ReactNode } from 'react'
import { Layout as AntLayout, Menu, Breadcrumb, theme } from 'antd'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  FileTextOutlined, SafetyCertificateOutlined,
  HomeOutlined, ProfileOutlined,
} from '@ant-design/icons'

const { Header, Content, Footer } = AntLayout

const breadcrumbMap: Record<string, { label: string; icon: ReactNode }> = {
  '/cases': { label: '理赔案件', icon: <FileTextOutlined /> },
}

export default function Layout({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const location = useLocation()
  const { token } = theme.useToken()

  const pathParts = location.pathname.split('/').filter(Boolean)
  const selectedKey = pathParts.length >= 1 ? `/${pathParts[0]}` : '/'

  // Build breadcrumb items
  const breadcrumbItems = [
    { title: <><HomeOutlined /> 首页</> },
  ]
  if (pathParts[0] === 'cases') {
    breadcrumbItems.push({ title: <><FileTextOutlined /> 理赔案件</> })
    if (pathParts[1]) {
      breadcrumbItems.push({ title: <span>案件 #${pathParts[1]}</span> })
      if (pathParts[2] === 'review') breadcrumbItems[breadcrumbItems.length - 1] = { title: <span>人工授权</span> }
    }
  }

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Header style={{
        display: 'flex', alignItems: 'center', padding: '0 24px',
        position: 'sticky', top: 0, zIndex: 100, boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
      }}>
        <div
          style={{ color: '#fff', fontSize: 18, fontWeight: 700, marginRight: 48, whiteSpace: 'nowrap', cursor: 'pointer', letterSpacing: 1 }}
          onClick={() => navigate('/cases')}
        >
          <SafetyCertificateOutlined style={{ marginRight: 10, fontSize: 20 }} />
          星盾·A2A 理赔
        </div>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[selectedKey]}
          items={[
            { key: '/cases', icon: <ProfileOutlined />, label: '理赔案件' },
          ]}
          onClick={({ key }) => navigate(key)}
          style={{ flex: 1, minWidth: 0, borderBottom: 'none' }}
        />
      </Header>
      <Content style={{ padding: '0 24px', marginTop: 16 }}>
        <Breadcrumb items={breadcrumbItems} style={{ marginBottom: 16 }} />
        <div style={{
          padding: 24,
          background: token.colorBgContainer,
          borderRadius: token.borderRadiusLG,
          minHeight: 360,
        }}>
          {children}
        </div>
      </Content>
      <Footer style={{ textAlign: 'center', color: '#999', fontSize: 12 }}>
        A2A 智能理赔助手 ©2024 星盾 StarShield
      </Footer>
    </AntLayout>
  )
}
