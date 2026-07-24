import { ReactNode } from 'react'
import { Layout as AntLayout, Menu } from 'antd'
import { useNavigate, useLocation } from 'react-router-dom'
import { FileTextOutlined, SafetyCertificateOutlined } from '@ant-design/icons'

const { Header, Content } = AntLayout

export default function Layout({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const location = useLocation()

  const selectedKey = location.pathname.startsWith('/cases') ? '/cases' : '/'

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', padding: '0 24px' }}>
        <div style={{ color: '#fff', fontSize: 18, fontWeight: 600, marginRight: 40, whiteSpace: 'nowrap' }}>
          <SafetyCertificateOutlined style={{ marginRight: 8 }} />
          星盾 StarShield
        </div>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[selectedKey]}
          items={[
            { key: '/cases', icon: <FileTextOutlined />, label: '理赔案件' },
          ]}
          onClick={({ key }) => navigate(key)}
          style={{ flex: 1, minWidth: 0 }}
        />
      </Header>
      <Content style={{ padding: '24px', background: '#f5f5f5' }}>
        {children}
      </Content>
    </AntLayout>
  )
}
