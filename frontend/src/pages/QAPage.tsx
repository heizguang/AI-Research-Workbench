import React, { useState, useRef, useEffect } from 'react';
import {
  Card,
  Input,
  Button,
  List,
  Typography,
  message,
  Tag,
  Empty,
  Drawer,
} from 'antd';
import {
  SendOutlined,
  UserOutlined,
  RobotOutlined,
  HistoryOutlined,
  EyeOutlined,
  MenuOutlined,
} from '@ant-design/icons';
import { agentLoopAPI, historyAPI } from '../services/api';
import { QAHistoryItem, ConversationMessage } from '../types';
import { useLocation } from 'react-router-dom';
import { stripMarkdown, generateUUID, hashString } from '../utils';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useResponsive } from '../hooks/useResponsive';

const { Title, Text } = Typography;
const { TextArea } = Input;

const QAPage: React.FC = () => {
  const { isMobile } = useResponsive();
  const location = useLocation();
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [reportContent, setReportContent] = useState('');
  const [currentSessionId, setCurrentSessionId] = useState('');
  const [history, setHistory] = useState<QAHistoryItem[]>([]);
  const [showReportPreview, setShowReportPreview] = useState(false);

  const [drawerOpen, setDrawerOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fullAnswerRef = useRef('');

  // 接收从历史页面传递过来的报告内容
  useEffect(() => {
    if (location.state?.reportContent) {
      setReportContent(stripMarkdown(location.state.reportContent));
      message.success(`已导入报告: ${location.state.reportTopic || '未命名'}`);
    }
  }, [location.state]);

  // 滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 加载历史记录
  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    try {
      const response = await historyAPI.getHistory(50);
      if (response.success && response.data) {
        setHistory(response.data.qa_history);
      }
    } catch (error) {
      console.error('加载历史记录失败:', error);
    }
  };

  const upsertHistoryPreview = ({
    sessionId,
    question,
    answer,
    reportContent: nextReportContent,
  }: {
    sessionId: string;
    question: string;
    answer?: string;
    reportContent: string;
  }) => {
    setHistory((prev) => {
      const next = [...prev];
      const existingIndex = next.findIndex(
        (item) => (item.session_id || item.id) === sessionId,
      );
      const timestamp = new Date().toISOString();

      if (existingIndex >= 0) {
        const existing = next[existingIndex];
        const messages = [...(existing.messages || [])];
        const lastMessage = messages[messages.length - 1];

        if (question) {
          const hasSamePendingQuestion =
            lastMessage?.role === 'user' && lastMessage.content === question;
          const hasCompletedSameTurn =
            messages.length >= 2 &&
            messages[messages.length - 2]?.role === 'user' &&
            messages[messages.length - 2]?.content === question &&
            messages[messages.length - 1]?.role === 'assistant';

          if (!hasSamePendingQuestion && !hasCompletedSameTurn) {
            messages.push({ role: 'user', content: question });
          }
        }

        if (answer) {
          const latestAssistant = messages[messages.length - 1];
          const hasSameAnswer =
            latestAssistant?.role === 'assistant' &&
            latestAssistant.content === answer;

          if (!hasSameAnswer) {
            messages.push({ role: 'assistant', content: answer });
          }
        }

        const updatedItem: QAHistoryItem = {
          ...existing,
          session_id: existing.session_id || sessionId,
          report_content: existing.report_content || nextReportContent,
          messages,
          timestamp,
        };

        next.splice(existingIndex, 1);
        return [updatedItem, ...next].slice(0, 50);
      }

      const messages: Array<{ role: string; content: string }> = [];
      if (question) {
        messages.push({ role: 'user', content: question });
      }
      if (answer) {
        messages.push({ role: 'assistant', content: answer });
      }

      const newItem: QAHistoryItem = {
        id: sessionId,
        session_id: sessionId,
        report_content: nextReportContent,
        messages,
        timestamp,
      };

      return [newItem, ...next].slice(0, 50);
    });
  };

  const handleNewChat = () => {
    setMessages([]);
    setQuestion('');
    setCurrentSessionId('');
  };

  const handleAsk = async () => {
    if (!question.trim()) {
      message.warning('请输入问题');
      return;
    }

    if (!reportContent.trim() && messages.length === 0) {
      message.warning('请先输入或粘贴报告内容');
      return;
    }

    // 添加用户消息
    const currentQuestion = question.trim();
    const sessionId = currentSessionId || generateUUID();
    if (!currentSessionId) {
      setCurrentSessionId(sessionId);
    }

    const userMessage: ConversationMessage = {
      role: 'user',
      content: currentQuestion,
      timestamp: new Date().toISOString(),
      metadata: {},
    };
    setMessages((prev) => [...prev, userMessage]);
    setQuestion('');
    setLoading(true);

    // 提问时立即创建后端历史记录
    try {
      let sessionId = currentSessionId;
      if (!sessionId && reportContent) {
        sessionId = await hashString(reportContent);
      }
      await historyAPI.saveQAHistory({
        question: currentQuestion,
        answer: '',
        report_content: reportContent,
        session_id: sessionId,
      });
    } catch (e) {
      console.error('创建问答历史失败:', e);
    }

    // 流式输出：先添加空的 AI 消息，然后逐块追加
    const aiMessage: ConversationMessage = {
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      metadata: {},
    };
    setMessages((prev) => [...prev, aiMessage]);

    let fullAnswer = '';
    fullAnswerRef.current = '';

    // 构建 agent loop 目标
    const contextPart = reportContent.trim()
      ? `\n\n参考报告内容：\n${reportContent}`
      : '';
    const historyPart = messages.length > 0
      ? `\n\n对话历史：\n${messages.slice(-6).map(m => `${m.role === 'user' ? '用户' : '助手'}：${m.content}`).join('\n')}`
      : '';
    const goal = `${question}${contextPart}${historyPart}`;

    try {
      const response = await agentLoopAPI.run({
        goal,
        tool_group: 'full',
        model: 'smart',
        max_loops: 10,
      }) as any;

      if (!response.task_id) {
        setLoading(false);
        message.error('启动问答任务失败');
        setMessages((prev) => prev.slice(0, -1));
        return;
      }

      const taskId = response.task_id;

      agentLoopAPI.stream(
        taskId,
        // onStep
        (event: any) => {
          if (event.type === 'think_chunk' && event.content) {
            // 流式文字 → 逐块追加
            fullAnswer += event.content;
            fullAnswerRef.current = fullAnswer;
            setMessages((prev) => {
              const updated = [...prev];
              const lastMsg = updated[updated.length - 1];
              if (lastMsg && lastMsg.role === 'assistant') {
                updated[updated.length - 1] = { ...lastMsg, content: fullAnswer };
              }
              return updated;
            });
          } else if (event.type === 'tool_call' && event.tool === 'web_search') {
            // 搜索中 → 显示状态
            fullAnswer = '正在搜索相关信息...\n\n';
            fullAnswerRef.current = fullAnswer;
            setMessages((prev) => {
              const updated = [...prev];
              const lastMsg = updated[updated.length - 1];
              if (lastMsg && lastMsg.role === 'assistant') {
                updated[updated.length - 1] = { ...lastMsg, content: fullAnswer };
              }
              return updated;
            });
          } else if (event.type === 'done' && event.result) {
            // 最终结果（agent loop 的 done 事件）
            fullAnswer = event.result;
            fullAnswerRef.current = fullAnswer;
            setMessages((prev) => {
              const updated = [...prev];
              const lastMsg = updated[updated.length - 1];
              if (lastMsg && lastMsg.role === 'assistant') {
                updated[updated.length - 1] = { ...lastMsg, content: fullAnswer };
              }
              return updated;
            });
            setLoading(false);
          } else if (event.type === 'error') {
            message.error(event.content || '问答失败');
            setLoading(false);
            setMessages((prev) => prev.slice(0, -1));
          }
        },
        // onDone
        async () => {
          // 保存问答历史到后端（同一报告的多次问答合并为一条记录）
          const answer = fullAnswerRef.current || fullAnswer;
          if (answer.trim()) {
            try {
              // 优先使用已有 session_id（从历史加载时带过来），否则用报告哈希
              let sessionId = currentSessionId;
              if (!sessionId && reportContent) {
                sessionId = await hashString(reportContent);
              }
              await historyAPI.saveQAHistory({
                question,
                answer,
                report_content: reportContent,
                session_id: sessionId,
              });
            } catch (e) {
              console.error('保存问答历史失败:', e);
            }
          }
          setLoading(false);
          loadHistory();
        },
        // onError
        (error: string) => {
          message.error(error);
          setLoading(false);
          setMessages((prev) => prev.slice(0, -1));
        },
      );
    } catch (err: any) {
      message.error(err.message || '问答失败');
      setLoading(false);
      setMessages((prev) => prev.slice(0, -1));
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleAsk();
    }
  };

  // 兼容旧格式：{question, answer} → {messages: [{role, content}]}
  const normalizeHistoryItem = (item: QAHistoryItem) => {
    if (item.messages && item.messages.length > 0) return item;
    // 旧格式：question + answer 转为 messages
    const msgs: Array<{ role: string; content: string }> = [];
    if ((item as any).question) msgs.push({ role: 'user', content: (item as any).question });
    if ((item as any).answer) msgs.push({ role: 'assistant', content: (item as any).answer });
    return { ...item, messages: msgs, session_id: item.session_id || item.id };
  };

  const loadFromHistory = (item: QAHistoryItem) => {
    const normalized = normalizeHistoryItem(item);
    // 恢复报告内容和会话ID
    if (normalized.report_content) {
      setReportContent(normalized.report_content);
    }
    // 记住 session_id，后续对话合并到同一条记录
    if (normalized.session_id) {
      setCurrentSessionId(normalized.session_id);
    }
    // 将完整对话导入到对话框
    const restoredMessages: ConversationMessage[] = normalized.messages.map((msg) => ({
      role: msg.role as 'user' | 'assistant',
      content: msg.content,
      timestamp: normalized.timestamp,
      metadata: {},
    }));
    setMessages(restoredMessages);
    setQuestion('');
  };

  return (
    <div style={{ padding: isMobile ? '12px 0' : '24px 0' }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: isMobile ? 12 : 0 }}>
        {isMobile && (
          <Button
            type="text"
            icon={<MenuOutlined />}
            onClick={() => setDrawerOpen(true)}
            style={{ marginRight: 8 }}
          />
        )}
        <Title level={isMobile ? 4 : 2} style={{ margin: 0 }}>
          <RobotOutlined style={{ marginRight: 12 }} />
          智能问答
        </Title>
      </div>
      <div style={{ height: 'calc(100vh - 270px)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

      <div style={{ display: 'flex', gap: isMobile ? 8 : 12, flex: 1, minHeight: 0 }}>
        {/* 左侧：报告输入 - 移动端用抽屉 */}
        {!isMobile && (
          <Card
            title="报告内容"
            style={{ width: 280, flexShrink: 0, display: 'flex', flexDirection: 'column' }}
            styles={{ body: { padding: 12, flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }, header: { flexShrink: 0 } }}
            extra={
              <Button
                size="small"
                type="link"
                icon={<EyeOutlined />}
                onClick={() => setShowReportPreview(!showReportPreview)}
                style={{ padding: 0 }}
              >
                {showReportPreview ? '编辑' : '预览'}
              </Button>
            }
          >
            {showReportPreview ? (
              <div className="report-content" style={{ flex: 1, overflowY: 'auto', padding: '0 4px' }}>
                {reportContent ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{reportContent}</ReactMarkdown>
                ) : (
                  <Empty description="暂无报告内容" style={{ padding: '48px 0' }} />
                )}
              </div>
            ) : (
              <TextArea
                placeholder="请粘贴或输入报告内容，AI将基于此内容回答您的问题..."
                value={reportContent}
                onChange={(e) => setReportContent(e.target.value)}
                style={{ resize: 'none', flex: 1 }}
              />
            )}
          </Card>
        )}

        {/* 移动端抽屉 */}
        {isMobile && (
          <Drawer
            title="报告内容"
            placement="left"
            open={drawerOpen}
            onClose={() => setDrawerOpen(false)}
            width={300}
          >
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
              <div style={{ marginBottom: 8 }}>
                <Button
                  size="small"
                  type="link"
                  icon={<EyeOutlined />}
                  onClick={() => setShowReportPreview(!showReportPreview)}
                >
                  {showReportPreview ? '编辑' : '预览'}
                </Button>
              </div>
              {showReportPreview ? (
                <div className="report-content" style={{ flex: 1, overflowY: 'auto', padding: '0 4px' }}>
                  {reportContent ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{reportContent}</ReactMarkdown>
                  ) : (
                    <Empty description="暂无报告内容" style={{ padding: '48px 0' }} />
                  )}
                </div>
              ) : (
                <TextArea
                  placeholder="请粘贴或输入报告内容..."
                  value={reportContent}
                  onChange={(e) => setReportContent(e.target.value)}
                  style={{ resize: 'none', flex: 1 }}
                />
              )}
            </div>
          </Drawer>
        )}

        {/* 中间：对话区域 */}
        <Card
          title="对话"
          style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}
          styles={{ body: { padding: isMobile ? '8px' : '8px 12px', flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }, header: { flexShrink: 0 } }}
          extra={
            <Button size="small" onClick={handleNewChat}>
              新建对话
            </Button>
          }
        >
          <div className="chat-container" style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
            <div className="chat-messages" style={{ flex: 1, overflowY: 'auto', marginBottom: 8 }}>
              {messages.length === 0 ? (
                <Empty
                  description="暂无对话，请输入问题开始提问"
                  style={{ marginTop: 48 }}
                />
              ) : (
                <List
                  dataSource={messages}
                  renderItem={(msg) => (
                    <List.Item
                      style={{
                        justifyContent:
                          msg.role === 'user' ? 'flex-end' : 'flex-start',
                        padding: '8px 0',
                        border: 'none',
                      }}
                    >
                      <div
                        style={{
                          maxWidth: '85%',
                          padding: '10px 14px',
                          borderRadius: 12,
                          backgroundColor:
                            msg.role === 'user' ? '#1890ff' : '#f5f5f5',
                          color: msg.role === 'user' ? '#fff' : '#333',
                          wordBreak: 'break-word',
                          lineHeight: 1.6,
                        }}
                      >
                        <div style={{ marginBottom: 4 }}>
                          {msg.role === 'user' ? (
                            <UserOutlined style={{ marginRight: 8 }} />
                          ) : (
                            <RobotOutlined style={{ marginRight: 8 }} />
                          )}
                          <Text
                            strong
                            style={{
                              color: msg.role === 'user' ? '#fff' : '#333',
                            }}
                          >
                            {msg.role === 'user' ? '用户' : 'AI助手'}
                          </Text>
                        </div>
                        {msg.role === 'user' ? (
                          <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                        ) : (
                          <div className="report-content"><ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown></div>
                        )}
                      </div>
                    </List.Item>
                  )}
                />
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="chat-input">
              <TextArea
                rows={2}
                placeholder="请输入问题... (Enter发送，Shift+Enter换行)"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyPress={handleKeyPress}
                disabled={loading}
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleAsk}
                loading={loading}
                style={{ height: 'auto' }}
              >
                发送
              </Button>
            </div>
          </div>
        </Card>

        {/* 右侧：历史记录 - 移动端隐藏 */}
        {!isMobile && (
          <Card
            title="历史记录"
            style={{ width: 200, flexShrink: 0, display: 'flex', flexDirection: 'column' }}
            styles={{ body: { padding: '4px 0', flex: 1, overflowY: 'auto' }, header: { flexShrink: 0 } }}
            extra={
              <Tag icon={<HistoryOutlined />} color="green" style={{ margin: 0 }}>
                {history.length}
              </Tag>
            }
          >
          <div className="history-list">
            {history.length === 0 ? (
              <Empty description="暂无" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <List
                dataSource={history.map(normalizeHistoryItem)}
                renderItem={(item) => (
                  <div
                    className="history-item"
                    onClick={() => loadFromHistory(item)}
                    style={{ cursor: 'pointer', padding: '8px 12px', borderBottom: '1px solid #f0f0f0' }}
                  >
                    <div className="history-item-question" style={{ fontSize: 14, marginBottom: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {item.messages?.[0]?.content || '空对话'}
                    </div>
                    <div style={{ fontSize: 12, color: '#999', display: 'flex', justifyContent: 'space-between' }}>
                      <span>{new Date(item.timestamp).toLocaleString('zh-CN')}</span>
                      <Tag color="blue" style={{ fontSize: 11, lineHeight: '18px', padding: '0 4px' }}>
                        {Math.floor((item.messages?.length || 0) / 2)}轮
                      </Tag>
                    </div>
                  </div>
                )}
              />
            )}
          </div>
        </Card>
        )}
      </div>
      </div>
    </div>
  );
};

export default QAPage;
