import React, { useState, useEffect } from 'react';
import {
  Card,
  List,
  Typography,
  Tag,
  Space,
  Button,
  Empty,
  Tabs,
  Input,
  message,
  Spin,
  Modal,
  Popconfirm,
  Row,
  Col,
  Radio,
} from 'antd';
import {
  HistoryOutlined,
  FileTextOutlined,
  QuestionCircleOutlined,
  ReloadOutlined,
  DeleteOutlined,
  ImportOutlined,
  DownloadOutlined,
} from '@ant-design/icons';
import { historyAPI, memoryAPI, reportAPI } from '../services/api';
import { ConversationMessage, QAHistoryItem } from '../types';
import { useNavigate } from 'react-router-dom';
import { useResponsive } from '../hooks/useResponsive';

const { Title, Paragraph, Text } = Typography;
const { Search } = Input;

const HistoryPage: React.FC = () => {
  const { isMobile } = useResponsive();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [conversations, setConversations] = useState<ConversationMessage[]>([]);
  const [qaHistory, setQaHistory] = useState<QAHistoryItem[]>([]);
  const [reports, setReports] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState('reports');
  const [downloadModalVisible, setDownloadModalVisible] = useState(false);
  const [downloadFormat, setDownloadFormat] = useState('markdown');
  const [downloading, setDownloading] = useState(false);
  const [currentReport, setCurrentReport] = useState<any>(null);

  useEffect(() => {
    loadHistory();
    loadReports();

    // 监听报告保存事件，自动刷新列表
    const handleReportSaved = () => {
      loadReports();
    };
    window.addEventListener('report-saved', handleReportSaved);
    return () => window.removeEventListener('report-saved', handleReportSaved);
  }, []);

  const loadHistory = async () => {
    setLoading(true);
    try {
      const response = await historyAPI.getHistory(100);
      if (response.success && response.data) {
        setConversations(response.data.conversations);
        setQaHistory(response.data.qa_history);
      }
    } catch (error) {
      console.error('加载历史记录失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadReports = async () => {
    try {
      const response = await reportAPI.list(50, 0);
      if (response.success && response.data) {
        setReports(response.data);
      }
    } catch (error) {
      console.error('加载报告列表失败:', error);
    }
  };

  const handleSearchMemory = async (query: string) => {
    if (!query.trim()) {
      message.warning('请输入搜索关键词');
      return;
    }

    setLoading(true);
    try {
      const response = await memoryAPI.search(query, 10);
      if (response.success && response.data) {
        setSearchResults(response.data);
        message.success(`找到 ${response.data.length} 条相关记忆`);
      }
    } catch (error) {
      console.error('搜索记忆失败:', error);
      message.error('搜索记忆失败');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteReport = async (reportId: string) => {
    try {
      await reportAPI.delete(reportId);
      message.success('删除成功');
      loadReports();
    } catch (error) {
      message.error('删除失败');
    }
  };

  const handleImportToQA = async (report: any) => {
    // 先获取完整报告内容
    try {
      const response = await reportAPI.get(report.id);
      if (response.success && response.data) {
        navigate('/qa', { state: { reportContent: response.data.content, reportTopic: response.data.topic } });
      } else {
        message.error('获取报告内容失败');
      }
    } catch (error) {
      message.error('获取报告内容失败');
    }
  };

  const handleImportToPPT = async (report: any) => {
    // 先获取完整报告内容
    try {
      const response = await reportAPI.get(report.id);
      if (response.success && response.data) {
        navigate('/ppt', { state: { reportContent: response.data.content } });
      } else {
        message.error('获取报告内容失败');
      }
    } catch (error) {
      message.error('获取报告内容失败');
    }
  };

  const handleDownloadReport = (report: any) => {
    setCurrentReport(report);
    setDownloadFormat('markdown');
    setDownloadModalVisible(true);
  };

  const handleConfirmDownload = async () => {
    if (!currentReport) return;
    setDownloading(true);
    try {
      // 1. 获取报告内容
      const response = await reportAPI.get(currentReport.id);
      if (!response.success || !response.data) {
        message.error('获取报告内容失败');
        return;
      }
      // 2. 调用后端导出接口
      const exportRes = await reportAPI.export(
        response.data.content,
        downloadFormat,
        currentReport.topic || 'report'
      );
      if (!exportRes.success || !exportRes.data) {
        message.error('导出失败');
        return;
      }
      // 3. 下载生成的文件
      const downloadUrl = reportAPI.download(exportRes.data.filename);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = exportRes.data.filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      message.success('下载成功');
      setDownloadModalVisible(false);
    } catch (error) {
      message.error('下载失败');
    } finally {
      setDownloading(false);
    }
  };

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const tabItems = [
    {
      key: 'reports',
      label: (
        <span>
          <FileTextOutlined />
          历史报告
        </span>
      ),
      children: (
        <Card>
          {reports.length === 0 ? (
            <Empty description="暂无历史报告" />
          ) : (
            <List
              dataSource={reports}
              renderItem={(item) => (
                <List.Item
                  actions={[
                    <Button
                      type="link"
                      icon={<DownloadOutlined />}
                      onClick={() => handleDownloadReport(item)}
                    >
                      下载
                    </Button>,
                    <Button
                      type="link"
                      icon={<ImportOutlined />}
                      onClick={() => handleImportToQA(item)}
                    >
                      导入问答
                    </Button>,
                    <Button
                      type="link"
                      icon={<ImportOutlined />}
                      onClick={() => handleImportToPPT(item)}
                    >
                      导入PPT
                    </Button>,
                    <Popconfirm
                      title="确定删除此报告吗？"
                      onConfirm={() => handleDeleteReport(item.id)}
                    >
                      <Button type="link" danger icon={<DeleteOutlined />}>
                        删除
                      </Button>
                    </Popconfirm>,
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <Space>
                        <Text strong>{item.topic}</Text>
                        <Tag color="blue">{item.mode}</Tag>
                        <Tag color="green">{item.format}</Tag>
                      </Space>
                    }
                    description={
                      <div>
                        <Text type="secondary">{formatTime(item.created_at)}</Text>
                        <br />
                        <Text type="secondary" ellipsis style={{ maxWidth: 500 }}>
                          {item.content_preview}
                        </Text>
                      </div>
                    }
                  />
                </List.Item>
              )}
              pagination={{
                pageSize: 10,
                showSizeChanger: true,
                showQuickJumper: true,
              }}
            />
          )}
        </Card>
      ),
    },
    {
      key: 'conversations',
      label: (
        <span>
          <HistoryOutlined />
          对话历史
        </span>
      ),
      children: (
        <Card>
          {conversations.length === 0 ? (
            <Empty description="暂无对话历史" />
          ) : (
            <List
              dataSource={conversations}
              renderItem={(item) => (
                <List.Item>
                  <List.Item.Meta
                    avatar={
                      <Tag color={item.role === 'user' ? 'blue' : 'green'}>
                        {item.role === 'user' ? '用户' : 'AI助手'}
                      </Tag>
                    }
                    title={
                      <Space>
                        <Text strong>{item.role === 'user' ? '用户' : 'AI助手'}</Text>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {formatTime(item.timestamp)}
                        </Text>
                      </Space>
                    }
                    description={
                      <div style={{ whiteSpace: 'pre-wrap', maxHeight: 100, overflow: 'hidden' }}>
                        {item.content}
                      </div>
                    }
                  />
                </List.Item>
              )}
              pagination={{
                pageSize: 10,
                showSizeChanger: true,
                showQuickJumper: true,
              }}
            />
          )}
        </Card>
      ),
    },
    {
      key: 'qa',
      label: (
        <span>
          <QuestionCircleOutlined />
          问答历史
        </span>
      ),
      children: (
        <Card>
          {qaHistory.length === 0 ? (
            <Empty description="暂无问答历史" />
          ) : (
            <List
              dataSource={qaHistory}
              renderItem={(item) => {
                // 兼容旧格式
                const msgs = item.messages?.length > 0
                  ? item.messages
                  : [
                      ...(item as any).question ? [{ role: 'user', content: (item as any).question }] : [],
                      ...(item as any).answer ? [{ role: 'assistant', content: (item as any).answer }] : [],
                    ];
                const firstQ = msgs.find((m: any) => m.role === 'user');
                const firstA = msgs.find((m: any) => m.role === 'assistant');
                return (
                <List.Item>
                  <List.Item.Meta
                    title={
                      <Space>
                        <Tag color="orange">问题</Tag>
                        <Text strong>{firstQ?.content || '空对话'}</Text>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {formatTime(item.timestamp)}
                        </Text>
                      </Space>
                    }
                    description={
                      <div>
                        <Tag color="green">回答</Tag>
                        <div style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>
                          {firstA?.content || ''}
                        </div>
                      </div>
                    }
                  />
                </List.Item>
              );}}
              pagination={{
                pageSize: 10,
                showSizeChanger: true,
                showQuickJumper: true,
              }}
            />
          )}
        </Card>
      ),
    },
    {
      key: 'memory',
      label: (
        <span>
          <FileTextOutlined />
          记忆搜索
        </span>
      ),
      children: (
        <Card>
          <div style={{ marginBottom: 16 }}>
            <Search
              placeholder="搜索记忆内容..."
              enterButton="搜索"
              size="large"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onSearch={handleSearchMemory}
              loading={loading}
            />
          </div>

          {searchResults.length > 0 ? (
            <List
              dataSource={searchResults}
              renderItem={(item) => (
                <List.Item>
                  <List.Item.Meta
                    title={
                      <Space>
                        <Text strong>记忆片段</Text>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {formatTime(item.timestamp)}
                        </Text>
                      </Space>
                    }
                    description={item.content}
                  />
                </List.Item>
              )}
            />
          ) : (
            <Empty description="输入关键词搜索记忆" />
          )}
        </Card>
      ),
    },
  ];

  return (
    <div style={{ padding: isMobile ? '12px 0' : '24px 0' }}>
      <div style={{
        display: 'flex',
        flexDirection: isMobile ? 'column' : 'row',
        justifyContent: 'space-between',
        alignItems: isMobile ? 'flex-start' : 'center',
        marginBottom: isMobile ? 12 : 24,
        gap: isMobile ? 8 : 0,
      }}>
        <div>
          <Title level={isMobile ? 3 : 2} style={{ margin: 0 }}>
            <HistoryOutlined style={{ marginRight: 12 }} />
            历史记录
          </Title>
          <Paragraph style={{ margin: 0, marginTop: isMobile ? 4 : 8 }}>
            查看历史报告、对话记录和问答历史
          </Paragraph>
        </div>
        <Space>
          <Button
            icon={<ReloadOutlined />}
            onClick={() => {
              loadHistory();
              loadReports();
            }}
            loading={loading}
            size={isMobile ? 'small' : 'middle'}
          >
            刷新
          </Button>
        </Space>
      </div>

      <Spin spinning={loading}>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabItems}
          size={isMobile ? 'small' : 'middle'}
        />
      </Spin>

      <Modal
        title="选择下载格式"
        open={downloadModalVisible}
        onOk={handleConfirmDownload}
        onCancel={() => setDownloadModalVisible(false)}
        confirmLoading={downloading}
        okText="下载"
        cancelText="取消"
      >
        <Radio.Group
          value={downloadFormat}
          onChange={(e) => setDownloadFormat(e.target.value)}
          style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '12px 0' }}
        >
          <Radio value="markdown">Markdown (.md)</Radio>
          <Radio value="word">Word (.docx)</Radio>
          <Radio value="pdf">PDF (.pdf)</Radio>
        </Radio.Group>
      </Modal>
    </div>
  );
};

export default HistoryPage;
