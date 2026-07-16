import React, { useState, useEffect, useRef } from 'react';
import { Collapse, Tag, Typography, Spin, Empty } from 'antd';
import {
  LoadingOutlined, CheckCircleOutlined, SearchOutlined,
  FileTextOutlined, CodeOutlined, QuestionCircleOutlined,
  StopOutlined, ExclamationCircleOutlined
} from '@ant-design/icons';
import { LoopEvent } from '../types';

const { Text, Paragraph } = Typography;

interface AgentLoopTraceProps {
  events: LoopEvent[];
  status: 'running' | 'completed' | 'interrupted' | 'failed' | 'idle';
  totalLoops: number;
  maxLoops: number;
  totalTokens: number;
  onInterrupt?: () => void;
}

const toolIcons: Record<string, React.ReactNode> = {
  web_search: <SearchOutlined />,
  read_file: <FileTextOutlined />,
  write_file: <FileTextOutlined />,
  run_code: <CodeOutlined />,
  generate_report: <FileTextOutlined />,
  modify_report: <FileTextOutlined />,
  generate_ppt: <FileTextOutlined />,
  ask_user: <QuestionCircleOutlined />,
};

const statusColors: Record<string, string> = {
  running: '#1890ff',
  completed: '#52c41a',
  interrupted: '#faad14',
  failed: '#ff4d4f',
  idle: '#d9d9d9',
};

const formatTokens = (tokens: number): string => {
  if (tokens >= 1000) return `${(tokens / 1000).toFixed(1)}K`;
  return tokens.toString();
};

const AgentLoopTrace: React.FC<AgentLoopTraceProps> = ({
  events,
  status,
  totalLoops,
  maxLoops,
  totalTokens,
  onInterrupt,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  // 自动滚动到底部
  useEffect(() => {
    if (containerRef.current && status === 'running') {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [events, status]);

  // 按循环分组事件
  const groupedEvents: Record<number, LoopEvent[]> = {};
  events.forEach((event) => {
    const loop = event.loop || 0;
    if (!groupedEvents[loop]) groupedEvents[loop] = [];
    groupedEvents[loop].push(event);
  });

  const sortedLoops = Object.keys(groupedEvents)
    .map(Number)
    .sort((a, b) => a - b);

  if (events.length === 0 && status === 'idle') {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <Empty description="等待任务开始..." />
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* 顶部状态栏 */}
      <div
        style={{
          padding: '12px 16px',
          borderBottom: '1px solid #f0f0f0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: '#fafafa',
        }}
      >
        <div>
          <Tag color={statusColors[status]}>
            {status === 'running' && <LoadingOutlined style={{ marginRight: 4 }} spin />}
            {status === 'completed' && <CheckCircleOutlined style={{ marginRight: 4 }} />}
            {status === 'interrupted' && <StopOutlined style={{ marginRight: 4 }} />}
            {status === 'failed' && <ExclamationCircleOutlined style={{ marginRight: 4 }} />}
            {status === 'running' ? '运行中' : status === 'completed' ? '已完成' : status === 'interrupted' ? '已中断' : status === 'failed' ? '失败' : '空闲'}
          </Tag>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Token: {formatTokens(totalTokens)} | 轮次: {totalLoops}/{maxLoops}
          </Text>
        </div>
        {status === 'running' && onInterrupt && (
          <a onClick={onInterrupt} style={{ color: '#ff4d4f', fontSize: 12 }}>
            停止
          </a>
        )}
      </div>

      {/* 事件流 */}
      <div
        ref={containerRef}
        style={{
          flex: 1,
          overflow: 'auto',
          padding: '8px 0',
        }}
      >
        <Collapse
          ghost
          defaultActiveKey={sortedLoops.slice(-2)} // 默认展开最近2轮
          style={{ background: 'transparent' }}
        >
          {sortedLoops.map((loopNum) => {
            const loopEvents = groupedEvents[loopNum];
            const isActive = loopNum === sortedLoops[sortedLoops.length - 1] && status === 'running';

            return (
              <Collapse.Panel
                key={loopNum}
                header={
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {isActive ? (
                      <Spin indicator={<LoadingOutlined style={{ fontSize: 14 }} spin />} size="small" />
                    ) : (
                      <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 14 }} />
                    )}
                    <Text strong style={{ fontSize: 13 }}>
                      Loop {loopNum}
                    </Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {loopEvents.length} 个步骤
                    </Text>
                  </div>
                }
                style={{
                  border: 'none',
                  background: isActive ? '#e6f7ff' : 'transparent',
                  borderRadius: 4,
                  marginBottom: 4,
                }}
              >
                <div style={{ paddingLeft: 24 }}>
                  {loopEvents.map((event, idx) => (
                    <div
                      key={idx}
                      style={{
                        padding: '6px 0',
                        borderBottom: idx < loopEvents.length - 1 ? '1px solid #f5f5f5' : 'none',
                      }}
                    >
                      {event.type === 'think_chunk' && (
                        <Text style={{ fontSize: 12, color: '#666' }}>
                          {event.content}
                        </Text>
                      )}

                      {event.type === 'tool_call' && (
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                            <Tag color="blue" style={{ fontSize: 11, margin: 0 }}>
                              {toolIcons[event.tool || ''] || '🔧'} {event.tool}
                            </Tag>
                          </div>
                          {event.tool_input && (
                            <Paragraph
                              style={{ fontSize: 11, color: '#888', margin: 0 }}
                              ellipsis={{ rows: 2, expandable: true }}
                            >
                              输入: {JSON.stringify(event.tool_input, null, 2)}
                            </Paragraph>
                          )}
                          {event.tool_output && (
                            <Paragraph
                              style={{ fontSize: 11, color: '#52c41a', margin: 0 }}
                              ellipsis={{ rows: 3, expandable: true }}
                            >
                              输出: {event.tool_output}
                            </Paragraph>
                          )}
                        </div>
                      )}

                      {event.type === 'observe' && (
                        <Text style={{ fontSize: 12, color: '#999', fontStyle: 'italic' }}>
                          👁 {event.content}
                        </Text>
                      )}

                      {event.type === 'done' && (
                        <Tag color="green" style={{ fontSize: 11 }}>
                          完成
                        </Tag>
                      )}

                      {event.type === 'error' && (
                        <Tag color="red" style={{ fontSize: 11 }}>
                          错误
                        </Tag>
                      )}
                    </div>
                  ))}
                </div>
              </Collapse.Panel>
            );
          })}
        </Collapse>
      </div>
    </div>
  );
};

export default AgentLoopTrace;
