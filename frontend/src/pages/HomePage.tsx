import React from 'react';
import { Card, Row, Col, Typography, Button, Space } from 'antd';
import {
  FileTextOutlined,
  SearchOutlined,
  FilePptOutlined,
  QuestionCircleOutlined,
  RobotOutlined,
  CloudOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

const { Title, Paragraph } = Typography;

const HomePage: React.FC = () => {
  const navigate = useNavigate();

  const features = [
    {
      icon: <RobotOutlined style={{ fontSize: 48, color: '#1890ff' }} />,
      title: 'AI智能生成',
      description: '基于大模型的智能理解，自动生成高质量报告',
      action: () => navigate('/report'),
    },
    {
      icon: <SearchOutlined style={{ fontSize: 48, color: '#52c41a' }} />,
      title: '网络搜索',
      description: '实时搜索最新信息，确保报告内容的时效性',
      action: () => navigate('/report'),
    },
    {
      icon: <FileTextOutlined style={{ fontSize: 48, color: '#722ed1' }} />,
      title: '文档分析',
      description: '上传文档，AI自动分析并生成报告',
      action: () => navigate('/report'),
    },
    {
      icon: <QuestionCircleOutlined style={{ fontSize: 48, color: '#fa8c16' }} />,
      title: '智能问答',
      description: '基于报告内容进行深度问答，保留历史记录',
      action: () => navigate('/qa'),
    },
    {
      icon: <FilePptOutlined style={{ fontSize: 48, color: '#f5222d' }} />,
      title: 'PPT生成',
      description: '一键将报告转换为专业的汇报PPT',
      action: () => navigate('/ppt'),
    },
    {
      icon: <CloudOutlined style={{ fontSize: 48, color: '#13c2c2' }} />,
      title: '记忆系统',
      description: '长期记忆功能，支持跨会话的上下文关联',
      action: () => navigate('/history'),
    },
  ];

  return (
    <div style={{ padding: '24px 0' }}>
      <div style={{ textAlign: 'center', marginBottom: 48 }}>
        <Title level={1}>
          <RobotOutlined style={{ marginRight: 12 }} />
          多智能体报告生成系统
        </Title>
        <Paragraph style={{ fontSize: 18, color: '#666' }}>
          基于多智能体协作的智能报告生成平台，支持AI理解、文档分析、网络搜索三种模式
        </Paragraph>
        <Space size="large">
          <Button type="primary" size="large" onClick={() => navigate('/report')}>
            开始生成报告
          </Button>
          <Button size="large" onClick={() => navigate('/history')}>
            查看历史记录
          </Button>
        </Space>
      </div>

      <Title level={2} style={{ textAlign: 'center', marginBottom: 32 }}>
        核心功能
      </Title>

      <Row gutter={[24, 24]}>
        {features.map((feature, index) => (
          <Col xs={24} sm={12} md={8} key={index}>
            <Card
              hoverable
              onClick={feature.action}
              style={{ height: '100%', textAlign: 'center' }}
            >
              <div style={{ marginBottom: 16 }}>{feature.icon}</div>
              <Title level={4}>{feature.title}</Title>
              <Paragraph style={{ color: '#666' }}>{feature.description}</Paragraph>
            </Card>
          </Col>
        ))}
      </Row>

      <div style={{ marginTop: 48, textAlign: 'center' }}>
        <Title level={3}>使用流程</Title>
        <Row gutter={[24, 24]} style={{ marginTop: 24 }}>
          <Col xs={12} sm={12} md={6}>
            <Card>
              <Title level={4}>1. 选择模式</Title>
              <Paragraph>选择AI理解、文档分析或网络搜索模式</Paragraph>
            </Card>
          </Col>
          <Col xs={12} sm={12} md={6}>
            <Card>
              <Title level={4}>2. 输入内容</Title>
              <Paragraph>输入主题、上传文档或进行搜索</Paragraph>
            </Card>
          </Col>
          <Col xs={12} sm={12} md={6}>
            <Card>
              <Title level={4}>3. 生成报告</Title>
              <Paragraph>AI自动生成高质量报告</Paragraph>
            </Card>
          </Col>
          <Col xs={12} sm={12} md={6}>
            <Card>
              <Title level={4}>4. 导出使用</Title>
              <Paragraph>导出为Markdown、Word或PPT格式</Paragraph>
            </Card>
          </Col>
        </Row>
      </div>
    </div>
  );
};

export default HomePage;
