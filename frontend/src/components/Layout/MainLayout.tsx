import React, { useState, useEffect } from 'react';
import { Layout, Menu, theme, Typography, Drawer, Button } from 'antd';
import {
  HomeOutlined,
  FileTextOutlined,
  QuestionCircleOutlined,
  FilePptOutlined,
  HistoryOutlined,
  FileSearchOutlined,
  MenuOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';

const { Header, Content, Sider } = Layout;
const { Title } = Typography;

interface MainLayoutProps {
  children: React.ReactNode;
}

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const [collapsed, setCollapsed] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const {
    token: { colorBgContainer, borderRadiusLG },
  } = theme.useToken();

  // 检测是否为移动端
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  const menuItems = [
    {
      key: '/',
      icon: <HomeOutlined />,
      label: '首页',
    },
    {
      key: '/report',
      icon: <FileTextOutlined />,
      label: '报告生成',
    },
    {
      key: '/qa',
      icon: <QuestionCircleOutlined />,
      label: '智能问答',
    },
    {
      key: '/ppt',
      icon: <FilePptOutlined />,
      label: 'PPT生成',
    },
    {
      key: '/history',
      icon: <HistoryOutlined />,
      label: '历史记录',
    },
    {
      key: '/logs',
      icon: <FileSearchOutlined />,
      label: '系统日志',
    },
  ];

  const handleMenuClick = (info: { key: string }) => {
    navigate(info.key);
    if (isMobile) {
      setDrawerOpen(false);
    }
  };

  // 菜单内容组件
  const menuContent = (
    <>
      <div
        style={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderBottom: '1px solid #f0f0f0',
        }}
      >
        <Title
          level={4}
          style={{
            margin: 0,
            color: '#1890ff',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
          }}
        >
          {collapsed && !isMobile ? 'MA' : 'Multi-Agent'}
        </Title>
      </div>
      <Menu
        mode="inline"
        selectedKeys={[location.pathname]}
        items={menuItems}
        onClick={handleMenuClick}
        style={{ borderRight: 0 }}
      />
    </>
  );

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {/* 桌面端侧边栏 */}
      {!isMobile && (
        <Sider
          collapsible
          collapsed={collapsed}
          onCollapse={(value) => setCollapsed(value)}
          theme="light"
          style={{
            boxShadow: '2px 0 8px rgba(0,0,0,0.1)',
          }}
        >
          {menuContent}
        </Sider>
      )}

      {/* 移动端抽屉菜单 */}
      {isMobile && (
        <Drawer
          placement="left"
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          width={250}
          styles={{ body: { padding: 0 } }}
        >
          {menuContent}
        </Drawer>
      )}

      <Layout>
        <Header
          style={{
            padding: isMobile ? '0 16px' : '0 24px',
            background: colorBgContainer,
            display: 'flex',
            alignItems: 'center',
            boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
            position: 'sticky',
            top: 0,
            zIndex: 100,
          }}
        >
          {isMobile && (
            <Button
              type="text"
              icon={<MenuOutlined />}
              onClick={() => setDrawerOpen(true)}
              style={{ marginRight: 12 }}
            />
          )}
          <Title level={isMobile ? 4 : 3} style={{ margin: 0, color: '#333' }}>
            多智能体报告生成系统
          </Title>
        </Header>
        <Content
          style={{
            margin: isMobile ? '12px 8px' : '24px 16px',
            padding: isMobile ? 12 : 24,
            background: colorBgContainer,
            borderRadius: borderRadiusLG,
            minHeight: 280,
          }}
        >
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;
