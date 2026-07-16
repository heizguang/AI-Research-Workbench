import React, { useState, useEffect, useRef } from 'react';
import {
  Card,
  Typography,
  Button,
  Space,
  Select,
  Switch,
  Spin,
  message,
  Tag,
  Grid,
} from 'antd';
import {
  ReloadOutlined,
  DownloadOutlined,
  ClearOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import { logAPI } from '../services/api';

const { Title, Text } = Typography;
const { useBreakpoint } = Grid;

const LogPage: React.FC = () => {
  const screens = useBreakpoint();
  const isMobile = !screens.md;

  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [logType, setLogType] = useState<'backend' | 'frontend'>('backend');
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [totalLines, setTotalLines] = useState(0);
  const logContainerRef = useRef<HTMLDivElement>(null);
  const refreshTimerRef = useRef<NodeJS.Timeout | null>(null);

  // 加载日志
  const loadLogs = async (showLoading = true) => {
    if (showLoading) setLoading(true);
    try {
      const response = await logAPI.getLogs(500, logType);
      if (response.success && response.data) {
        setLogs(response.data.lines || []);
        setTotalLines(response.data.total_lines || 0);
      }
    } catch (error) {
      console.error('加载日志失败:', error);
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  // 初始加载
  useEffect(() => {
    loadLogs();
  }, [logType]);

  // 自动刷新
  useEffect(() => {
    if (autoRefresh) {
      refreshTimerRef.current = setInterval(() => {
        loadLogs(false);
      }, 3000);
    } else {
      if (refreshTimerRef.current) {
        clearInterval(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
    }

    return () => {
      if (refreshTimerRef.current) {
        clearInterval(refreshTimerRef.current);
      }
    };
  }, [autoRefresh]);

  // 自动滚动到底部
  useEffect(() => {
    if (logContainerRef.current && autoRefresh) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs, autoRefresh]);

  // 下载日志
  const handleDownload = () => {
    const content = logs.join('\n');
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${logType}_log_${new Date().toISOString().slice(0, 10)}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    message.success('日志已下载');
  };

  // 清空显示（不清空文件）
  const handleClearDisplay = () => {
    setLogs([]);
    message.info('显示已清空');
  };

  // 根据日志内容返回颜色
  const getLogLevel = (line: string): string => {
    if (line.includes('ERROR') || line.includes('error')) return '#ff4d4f';
    if (line.includes('WARNING') || line.includes('warning') || line.includes('WARN')) return '#faad14';
    if (line.includes('INFO') || line.includes('info')) return '#52c41a';
    if (line.includes('DEBUG') || line.includes('debug')) return '#1890ff';
    return '#d9d9d9';
  };

  // 高亮日志行
  const renderLogLine = (line: string, index: number) => {
    const level = getLogLevel(line);
    const timestampMatch = line.match(/\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}/);
    const timestamp = timestampMatch ? timestampMatch[0] : '';
    const rest = timestamp ? line.replace(timestamp, '').trim() : line;

    return (
      <div
        key={index}
        style={{
          padding: '2px 8px',
          borderBottom: '1px solid #f0f0f0',
          fontFamily: 'Monaco, Menlo, Consolas, monospace',
          fontSize: '12px',
          lineHeight: '1.6',
          backgroundColor: index % 2 === 0 ? '#fafafa' : '#fff',
        }}
      >
        <span style={{ color: '#999', marginRight: 8 }}>
          {String(index + 1).padStart(4, '0')}
        </span>
        {timestamp && (
          <span style={{ color: '#1890ff', marginRight: 8 }}>{timestamp}</span>
        )}
        <span style={{ color: level }}>{rest}</span>
      </div>
    );
  };

  return (
    <div style={{ padding: isMobile ? '12px' : '24px', height: 'calc(100vh - 64px)', display: 'flex', flexDirection: 'column' }}>
      <Card
        style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
        bodyStyle={{ flex: 1, display: 'flex', flexDirection: 'column', padding: isMobile ? '12px' : '16px' }}
      >
        {/* 头部控制栏 */}
        <div style={{
          marginBottom: 16,
          display: 'flex',
          flexDirection: isMobile ? 'column' : 'row',
          justifyContent: 'space-between',
          alignItems: isMobile ? 'flex-start' : 'center',
          gap: isMobile ? 12 : 0,
        }}>
          <Space wrap>
            <Title level={isMobile ? 5 : 4} style={{ margin: 0 }}>
              <FileTextOutlined /> 系统日志
            </Title>
            <Tag color={logType === 'backend' ? 'blue' : 'green'}>
              {logType === 'backend' ? '后端' : '前端'}
            </Tag>
            <Text type="secondary">共 {totalLines} 行</Text>
          </Space>

          <Space wrap>
            <Select
              value={logType}
              onChange={(value) => setLogType(value)}
              style={{ width: isMobile ? 100 : 120 }}
              size={isMobile ? 'small' : 'middle'}
              options={[
                { label: '后端日志', value: 'backend' },
                { label: '前端日志', value: 'frontend' },
              ]}
            />
            <span style={{ fontSize: isMobile ? 12 : 14 }}>
              自动刷新：
              <Switch
                checked={autoRefresh}
                onChange={setAutoRefresh}
                size="small"
                style={{ marginLeft: 4 }}
              />
            </span>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => loadLogs()}
              loading={loading}
              size={isMobile ? 'small' : 'middle'}
            >
              {isMobile ? '' : '刷新'}
            </Button>
            <Button
              icon={<DownloadOutlined />}
              onClick={handleDownload}
              size={isMobile ? 'small' : 'middle'}
            >
              {isMobile ? '' : '下载'}
            </Button>
            <Button
              icon={<ClearOutlined />}
              onClick={handleClearDisplay}
              size={isMobile ? 'small' : 'middle'}
            >
              {isMobile ? '' : '清空'}
            </Button>
          </Space>
        </div>

        {/* 日志内容 */}
        <div
          ref={logContainerRef}
          style={{
            flex: 1,
            overflow: 'auto',
            border: '1px solid #d9d9d9',
            borderRadius: '4px',
            backgroundColor: '#fff',
          }}
        >
          {loading && logs.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 50 }}>
              <Spin size="large" />
            </div>
          ) : logs.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 50, color: '#999' }}>
              暂无日志
            </div>
          ) : (
            logs.map((line, index) => renderLogLine(line, index))
          )}
        </div>
      </Card>
    </div>
  );
};

export default LogPage;
