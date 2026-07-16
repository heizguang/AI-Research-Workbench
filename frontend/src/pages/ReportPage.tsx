import React, { useState, useEffect, useRef } from 'react';
import {
  Card,
  Form,
  Input,
  Select,
  Button,
  Upload,
  Space,
  Typography,
  message,
  Spin,
  Divider,
  Row,
  Col,
  Modal,
  Tabs,
  Dropdown,
} from 'antd';
import {
  UploadOutlined,
  FileTextOutlined,
  DownloadOutlined,
  EditOutlined,
  QuestionCircleOutlined,
  FilePptOutlined,
  LayoutOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { reportAPI, documentAPI, pptAPI, agentLoopAPI, getBackendBase } from '../services/api';
import { ReportMode, ReportFormat, Report, PPTConfig, PPTStyle, CanvasFormat } from '../types';
import { useNavigate } from 'react-router-dom';
import { useResponsive } from '../hooks/useResponsive';

const { Title, Paragraph } = Typography;
const { TextArea } = Input;
const { Option } = Select;

const ReportPage: React.FC = () => {
  const { isMobile } = useResponsive();
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<Report | null>(null);
  const [progressStatus, setProgressStatus] = useState('');
  const [modifying, setModifying] = useState(false);
  const [showModify, setShowModify] = useState(false);
  const [editContent, setEditContent] = useState('');
  const [searchContext, setSearchContext] = useState('');
  const [pptLoading, setPptLoading] = useState(false);
  const [showPPTConfig, setShowPPTConfig] = useState(false);
  const [pptConfig, setPptConfig] = useState<PPTConfig>({
    template: 'default',
    style: 'professional',
    canvasFormat: 'ppt169',
    imageGeneration: false,
    imageStyle: 'realistic',
    colorScheme: 'blue',
  });
  const [templates, setTemplates] = useState<{
    layouts: Record<string, { summary?: string; canvas_format?: string; page_count?: number; primary_color?: string }>;
    brands: Record<string, { summary?: string; primary_color?: string }>;
  }>({ layouts: {}, brands: {} });

  // 已上传文件（用于展示与移除）
  const [uploadedFile, setUploadedFile] = useState<{ name: string; path: string } | null>(null);
  // 用户额外要求中含搜索关键词时，自动标记需要搜索
  const [searchKeywordsDetected, setSearchKeywordsDetected] = useState(false);

  // 监听额外要求输入，自动检测搜索关键词
  useEffect(() => {
    const requirements = form.getFieldValue('additional_requirements') || '';
    const hasSearchKeyword = /搜索|查找|最新|进展/.test(requirements);
    setSearchKeywordsDetected(hasSearchKeyword);
  }, [form]);

  // 加载动态模板列表
  useEffect(() => {
    const loadTemplates = async () => {
      try {
        const response = await pptAPI.getTemplates();
        if (response.success && response.data) {
          setTemplates({
            layouts: response.data.layouts || {},
            brands: response.data.brands || {},
          });
        }
      } catch (err) {
        console.error('加载模板失败:', err);
      }
    };
    loadTemplates();
  }, []);

  const handleGenerate = async (values: any) => {
    let includeSearch: boolean;
    if (values.file_path) {
      // 文件分支：直接基于文档生成，不做网络搜索
      includeSearch = false;
    } else {
      // 无文件：默认搜索
      includeSearch = true;
    }

    const requestData: any = {
      ...values,
      format: 'markdown',
      include_search: includeSearch,
    };
    delete requestData.file;
    await executeGenerate(requestData);
  };

  // SSE 控制器（用于中断）
  const abortControllerRef = useRef<AbortController | null>(null);

  // 统一执行生成逻辑（通过 Agent Loop 接口）
  const executeGenerate = async (requestData: any) => {
    setLoading(true);
    setReport(null);
    const reportContentRef = { current: '' as string };
    const reportSavedRef = { current: false };

    if (requestData.date_range && requestData.date_range.length === 2) {
      requestData.date_range = {
        start: requestData.date_range[0].format('YYYY-MM-DD'),
        end: requestData.date_range[1].format('YYYY-MM-DD'),
      };
    }

    // 构建 agent loop 目标描述
    const workflowHint = '\n\n工作流程：先搜索信息，然后生成报告。对生成的报告质量不满意可以再次搜索并重新生成。满意后使用 write_file 写入文件，写入完成后直接返回报告内容作为最终结果，不要再调用其他工具。';

    let goal: string;
    if (requestData.file_path) {
      // 有文件：走后端文件报告流程，goal 仅用于日志
      goal = `基于文件 ${requestData.file_path} 生成关于"${requestData.topic}"的报告。`;
    } else {
      // 无文件：走搜索流程
      goal = `请搜索并生成关于"${requestData.topic}"的详细报告。${requestData.additional_requirements ? '额外要求：' + requestData.additional_requirements : ''}${workflowHint}`;
    }

    try {
      // 启动 agent loop 任务
      const response = await agentLoopAPI.run({
        goal,
        tool_group: 'full',
        model: 'smart',
        max_loops: 6,
        // 文件报告流程专用字段
        file_path: requestData.file_path || undefined,
        include_search: requestData.include_search ?? undefined,
        topic: requestData.file_path ? requestData.topic : undefined,
      }) as any;

      if (!response.task_id) {
        setLoading(false);
        message.error('启动任务失败');
        return;
      }

      const taskId = response.task_id;
      setProgressStatus('任务已提交，正在处理...');

      // 建立 SSE 连接
      const controller = agentLoopAPI.stream(
        taskId,
        // onStep — 处理每个 agent loop 事件
        (event: any) => {
          if (event.type === 'start') {
            // 文件报告流水线：明确提示走"解析文档 → 生成报告"分支
            if (event.stage === '文件报告') {
              setProgressStatus('已识别文档，正在走「解析文档 → 生成报告」流程...');
            } else {
              setProgressStatus('任务已启动，正在分析需求...');
            }
          } else if (event.type === 'think_chunk') {
            // LLM 思考中 — 不频繁更新 UI，仅在首次时设置状态
            setProgressStatus((prev) => prev?.includes('思考中') ? prev : 'AI 正在思考分析...');
          } else if (event.type === 'tool_call') {
            // 文件报告流水线：按 stage 展示阶段进度（不走 loop 轮次逻辑）
            if (event.stage) {
              if (event.tool === 'read_file') {
                setProgressStatus(event.tool_output ? '文档解析完成，正在准备生成报告...' : '正在解析文档...');
              } else if (event.tool === 'web_search') {
                setProgressStatus(event.tool_output ? '补充信息搜索完成，正在生成报告...' : '正在搜索补充信息...');
              } else if (event.tool === 'generate_report') {
                if (event.tool_output) {
                  setProgressStatus('报告已生成，正在保存...');
                  reportContentRef.current = event.tool_output;
                  reportSavedRef.current = true;
                  setReport({
                    topic: requestData.topic,
                    content: event.tool_output,
                    mode: 'ai' as ReportMode,
                    format: 'markdown',
                    sections: [],
                    created_at: new Date().toISOString(),
                  });
                } else {
                  setProgressStatus('正在生成报告...');
                }
              }
              return;
            }
            if (event.tool === 'web_search') {
              if (event.tool_output) {
                // 搜索完成 → 提取搜索结果
                setProgressStatus('搜索完成，正在整理结果...');
                try {
                  const output = JSON.parse(event.tool_output);
                  if (output.results && Array.isArray(output.results)) {
                    const contextText = output.results
                      .map((r: any) => `${r.title || ''} - ${r.snippet || r.content || ''}`)
                      .join('\n');
                    setSearchContext(contextText);
                  }
                } catch {
                  setSearchContext(event.tool_output);
                }
              } else {
                // 搜索开始
                setProgressStatus('正在搜索相关信息...');
              }
            } else if (event.tool === 'generate_report') {
              if (event.tool_output) {
                // 报告生成完成 → 保存到历史
                setProgressStatus('报告已生成，正在保存...');
                const reportContent = event.tool_output;
                reportContentRef.current = reportContent;
                setReport({
                  topic: requestData.topic,
                  content: reportContent,
                  mode: 'ai' as ReportMode,
                  format: 'markdown',
                  sections: [],
                  created_at: new Date().toISOString(),
                });
                reportSavedRef.current = true;
                reportAPI.save(requestData.topic, reportContent, 'markdown', 'ai')
                  .then((res) => {
                    if (res.success) {
                      window.dispatchEvent(new CustomEvent('report-saved'));
                    }
                  })
                  .catch((err: any) => console.error('保存报告失败:', err));
              } else {
                // 报告生成开始
                setProgressStatus('正在生成报告...');
              }
            } else if (event.tool === 'write_file') {
              if (event.tool_input?.content) {
                setProgressStatus('报告内容已生成，正在保存...');
                const reportContent = event.tool_input.content;
                reportContentRef.current = reportContent;
                setReport({
                  topic: requestData.topic,
                  content: reportContent,
                  mode: 'ai' as ReportMode,
                  format: 'markdown',
                  sections: [],
                  created_at: new Date().toISOString(),
                });
              } else {
                setProgressStatus('正在写入文件...');
              }
            }
          } else if (event.type === 'observe') {
            // 工具执行完成 — 显示工具结果摘要
            const toolName = event.tool || '';
            if (toolName === 'web_search') {
              setProgressStatus('搜索完成，正在整理结果...');
            } else if (toolName === 'generate_report') {
              setProgressStatus('报告已生成，等待最终整理...');
            } else if (toolName === 'write_file') {
              setProgressStatus('报告已保存，等待最终整理...');
            } else if (toolName) {
              setProgressStatus(`${toolName} 执行完成，继续处理...`);
            }
          } else if (event.type === 'done') {
            // 任务完成 — 优先用 ref（write_file/generate_report 已捕获），兜底用 result
            const content = reportContentRef.current || event.result || '';
            if (content) {
              setReport({
                topic: requestData.topic,
                content,
                mode: 'ai' as ReportMode,
                format: 'markdown',
                sections: [],
                created_at: new Date().toISOString(),
              });
              // 如果 generate_report handler 已保存过，跳过重复保存
              if (!reportSavedRef.current) {
                reportAPI.save(requestData.topic, content, 'markdown', 'ai')
                  .then((res) => {
                    if (res.success) {
                      window.dispatchEvent(new CustomEvent('report-saved'));
                    } else {
                      message.error('报告保存失败');
                    }
                  })
                  .catch((err: any) => {
                    console.error('保存报告失败:', err);
                    message.error('报告保存失败');
                  });
              }
            }
            // 达到最大轮次时提示用户
            if (event.status === 'max_loops_reached') {
              message.warning('已达到处理轮次上限，返回当前结果');
            }
            setLoading(false);
            setProgressStatus('');
          } else if (event.type === 'error') {
            setLoading(false);
            setProgressStatus('');
            message.error(event.content || '报告生成失败');
          }
        },
        // onDone
        () => {
          setLoading((prev) => {
            if (prev) {
              setProgressStatus('');
              message.success('报告生成完成！');
            }
            return false;
          });
        },
        // onError
        (error: string) => {
          setLoading(false);
          setProgressStatus('');
          message.error(error || '流式连接出错');
        },
      );

      abortControllerRef.current = controller;
    } catch (err: any) {
      setLoading(false);
      setProgressStatus('');
      message.error(err.message || '启动任务失败');
    }
  };

  const handleModify = async (values: any) => {
    if (!report) return;

    setModifying(true);
    try {
      // 通过 Agent Loop 接口修改报告
      const goal = `请根据以下要求修改报告：\n${values.modifications}\n\n原报告内容：\n${report.content}`;

      const response = await agentLoopAPI.run({
        goal,
        tool_group: 'full',
        model: 'smart',
        max_loops: 10,
      }) as any;

      if (!response.task_id) {
        setModifying(false);
        message.error('启动修改任务失败');
        return;
      }

      const taskId = response.task_id;

      // 建立 SSE 连接，等待修改结果
      agentLoopAPI.stream(
        taskId,
        // onStep
        (event: any) => {
          if (event.type === 'done' && event.result) {
            setReport({
              ...report,
              content: event.result,
              sections: [],
            });
            setModifying(false);
            message.success('报告修改成功！');
            setShowModify(false);
          } else if (event.type === 'error') {
            setModifying(false);
            message.error(event.content || '报告修改失败');
          }
        },
        // onDone
        () => {
          setModifying(false);
        },
        // onError
        (error: string) => {
          setModifying(false);
          message.error(error || '报告修改失败');
        },
      );

      message.info('正在修改报告，请稍候...');
    } catch (error) {
      message.error('修改报告时出错，请重试');
      console.error(error);
      setModifying(false);
    }
  };

  const handleExport = async (format: ReportFormat) => {
    if (!report) return;

    try {
      const response = await reportAPI.export(report.content, format);

      if (response.success && response.data) {
        // 创建下载链接（使用完整的后端URL）
        const downloadUrl = reportAPI.download(response.data.filename);
        const backendUrl = getBackendBase();
        const link = document.createElement('a');
        link.href = downloadUrl.startsWith('http')
          ? downloadUrl
          : `${backendUrl}${downloadUrl}`;
        link.download = response.data.filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        message.success(`报告已导出为${format.toUpperCase()}格式`);
      } else {
        message.error(response.error || '导出失败');
      }
    } catch (error) {
      message.error('导出报告时出错，请重试');
      console.error(error);
    }
  };

  const handleGoToQA = () => {
    if (!report) return;
    navigate('/qa', { state: { reportContent: report.content, reportTopic: report.topic } });
  };

  const handleGeneratePPT = async () => {
    if (!report) return;

    setPptLoading(true);
    try {
      const response = await pptAPI.generateAndWait({
        report_content: report.content,
        template: pptConfig.template,
        style: 'professional',
        options: {
          canvas_format: pptConfig.canvasFormat,
          color_scheme: pptConfig.colorScheme,
          custom_colors: pptConfig.customColors,
        },
      });

      if (response.success && response.data) {
        // 创建下载链接
        const filename = response.data.pptx_path.split('/').pop() || response.data.pptx_path;
        const downloadUrl = pptAPI.download(filename);
        const backendUrl = getBackendBase();
        const link = document.createElement('a');
        link.href = downloadUrl.startsWith('http')
          ? downloadUrl
          : `${backendUrl}${downloadUrl}`;
        link.download = `presentation_${pptConfig.template}_${pptConfig.style}.pptx`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        message.success('PPT 生成成功！');
        setShowPPTConfig(false);
      } else {
        message.error(response.error || 'PPT 生成失败');
      }
    } catch (error) {
      message.error('生成 PPT 时出错，请重试');
      console.error(error);
    } finally {
      setPptLoading(false);
    }
  };

  const handleUpload = async (file: any) => {
    try {
      const response = await documentAPI.upload(file);

      if (response.success && response.data) {
        form.setFieldsValue({ file_path: response.data.file_path });
        setUploadedFile({ name: file.name, path: response.data.file_path });
        message.success('文件上传成功');
      } else {
        message.error('文件上传失败');
      }
    } catch (error) {
      message.error('上传文件时出错，请重试');
      console.error(error);
    }

    return false; // 阻止默认上传行为
  };

  // 移除已上传文件：清空 file_path，回到无文件分支
  const handleRemoveFile = () => {
    form.setFieldsValue({ file_path: undefined });
    setUploadedFile(null);
  };

  return (
    <div style={{ padding: isMobile ? '12px 0' : '24px 0' }}>
      <Title level={isMobile ? 3 : 2}>
        <FileTextOutlined style={{ marginRight: 12 }} />
        报告生成
      </Title>
      <Paragraph style={{ marginBottom: isMobile ? 12 : 24 }}>
        选择生成模式，输入主题或上传文档，AI将为您生成高质量的报告
      </Paragraph>

      <Row gutter={isMobile ? 12 : 24}>
        <Col xs={24} md={10}>
          <Card title="生成设置" style={{ marginBottom: isMobile ? 12 : 0 }}>
            <Form
              form={form}
              layout="vertical"
              onFinish={handleGenerate}
            >
              <Form.Item
                name="topic"
                label="报告主题"
                rules={[{ required: true, message: '请输入报告主题' }]}
              >
                <Input placeholder="请输入报告主题" />
              </Form.Item>

              <Form.Item
                name="file"
                label="上传文档（可选）"
              >
                <Upload
                  beforeUpload={handleUpload}
                  maxCount={1}
                  accept=".pdf,.docx,.doc,.txt,.md"
                  showUploadList={false}
                >
                  <Button icon={<UploadOutlined />}>选择文件</Button>
                </Upload>
              </Form.Item>

              {uploadedFile && (
                <div
                  style={{
                    marginTop: -12,
                    marginBottom: 12,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '6px 10px',
                    background: '#f6ffed',
                    border: '1px solid #b7eb8f',
                    borderRadius: 4,
                    fontSize: 13,
                  }}
                >
                  <FileTextOutlined style={{ color: '#52c41a' }} />
                  <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {uploadedFile.name}
                  </span>
                  <a style={{ color: '#ff4d4f' }} onClick={handleRemoveFile}>
                    移除
                  </a>
                </div>
              )}

              {/* 隐藏字段：保存已上传文档的服务端路径，供提交时识别文件报告分支 */}
              <Form.Item name="file_path" hidden>
                <Input />
              </Form.Item>



              <Form.Item
                name="additional_requirements"
                label="额外要求（可选）"
              >
                <TextArea
                  rows={3}
                  placeholder="请输入对报告的额外要求，如：重点关注XX方面、使用XX风格等"
                />
              </Form.Item>

              <Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  loading={loading}
                  block
                  size="large"
                >
                  生成报告
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </Col>

        <Col xs={24} md={14}>
          <Card
            title="生成结果"
            extra={
              report && (
                <Space wrap={isMobile}>
                  <Button
                    icon={<EditOutlined />}
                    onClick={() => {
                      setEditContent(report?.content || '');
                      setShowModify(true);
                    }}
                    size={isMobile ? 'small' : 'middle'}
                  >
                    {isMobile ? '' : '修改报告'}
                  </Button>
                  <Dropdown
                    menu={{
                      items: [
                        { key: 'markdown', label: 'Markdown (.md)' },
                        { key: 'word', label: 'Word (.docx)' },
                        { key: 'pdf', label: 'PDF (.pdf)' },
                      ],
                      onClick: ({ key }) => handleExport(key as ReportFormat),
                    }}
                  >
                    <Button icon={<DownloadOutlined />} size={isMobile ? 'small' : 'middle'}>
                      {isMobile ? '' : '导出报告 ▾'}
                    </Button>
                  </Dropdown>
                  <Button
                    icon={<FilePptOutlined />}
                    onClick={() => setShowPPTConfig(true)}
                    size={isMobile ? 'small' : 'middle'}
                  >
                    {isMobile ? '' : '生成 PPT'}
                  </Button>
                  <Button
                    type="primary"
                    icon={<QuestionCircleOutlined />}
                    onClick={handleGoToQA}
                    size={isMobile ? 'small' : 'middle'}
                  >
                    {isMobile ? '' : '智能问答'}
                  </Button>
                </Space>
              )
            }
            style={{ height: 'calc(100vh - 200px)' }}
            bodyStyle={{ height: 'calc(100vh - 280px)', overflowY: 'auto' }}
          >
            {loading ? (
              <div style={{ textAlign: 'center', padding: '48px 0' }}>
                <Spin size="large" />
                <Paragraph style={{ marginTop: 16, fontSize: 16, color: '#666' }}>
                  {progressStatus || '正在生成报告，请稍候...'}
                </Paragraph>
                <Paragraph style={{ marginTop: 8, fontSize: 13, color: '#999' }}>
                  首次生成可能需要 1-3 分钟，请耐心等待
                </Paragraph>
              </div>
            ) : report ? (
              <div>
                <div className="report-content">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{report.content}</ReactMarkdown>
                </div>
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '48px 0', color: '#999' }}>
                <FileTextOutlined style={{ fontSize: 64, marginBottom: 16 }} />
                <Paragraph>请在左侧设置生成参数，然后点击"生成报告"按钮</Paragraph>
              </div>
            )}
          </Card>
        </Col>
      </Row>

      {/* 修改报告弹窗 */}
      <Modal
        title="修改报告"
        open={showModify}
        onCancel={() => setShowModify(false)}
        footer={null}
        width={900}
        destroyOnClose
      >
        <Tabs
          defaultActiveKey="edit"
          items={[
            {
              key: 'edit',
              label: '直接编辑',
              children: (
                <>
                  <TextArea
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    rows={20}
                    style={{ fontFamily: 'monospace', fontSize: 13 }}
                    placeholder="在此直接编辑报告内容..."
                  />
                  <div style={{ marginTop: 12, textAlign: 'right' }}>
                    <Button onClick={() => setShowModify(false)} style={{ marginRight: 8 }}>
                      取消
                    </Button>
                    <Button
                      type="primary"
                      onClick={() => {
                        if (report) {
                          setReport({ ...report, content: editContent });
                          setShowModify(false);
                          message.success('报告已更新');
                        }
                      }}
                    >
                      保存修改
                    </Button>
                  </div>
                </>
              ),
            },
            {
              key: 'ai',
              label: 'AI 修改',
              children: (
                <Form layout="vertical" onFinish={handleModify}>
                  <Form.Item
                    name="modifications"
                    label="修改意见"
                    rules={[{ required: true, message: '请输入修改意见' }]}
                  >
                    <TextArea
                      rows={4}
                      placeholder="请描述您希望如何修改报告，例如：&#10;- 补充XX方面的内容&#10;- 调整XX部分的结构&#10;- 增加XX数据支持"
                    />
                  </Form.Item>
                  <Form.Item>
                    <Button
                      type="primary"
                      htmlType="submit"
                      loading={modifying}
                    >
                      提交修改
                    </Button>
                  </Form.Item>
                </Form>
              ),
            },
          ]}
        />
      </Modal>

      {/* PPT 配置模态框 */}
      <Modal
        title="PPT 配置"
        open={showPPTConfig}
        onCancel={() => setShowPPTConfig(false)}
        footer={[
          <Button key="cancel" onClick={() => setShowPPTConfig(false)}>
            取消
          </Button>,
          <Button
            key="generate"
            type="primary"
            loading={pptLoading}
            onClick={handleGeneratePPT}
          >
            生成 PPT
          </Button>,
        ]}
        width={600}
      >
        <Form layout="vertical">
          <Form.Item label="模板">
            <Tabs
              size="small"
              items={[
                {
                  key: 'layouts',
                  label: <span><LayoutOutlined /> 布局模板</span>,
                  children: (
                    <Select
                      style={{ width: '100%' }}
                      value={pptConfig.template}
                      onChange={(value) => setPptConfig({ ...pptConfig, template: value })}
                      placeholder="选择布局模板"
                      optionLabelProp="label"
                    >
                      <Select.Option value="default" label="默认（自由设计）">默认（自由设计）</Select.Option>
                      {Object.entries(templates.layouts).map(([key, val]) => (
                        <Select.Option key={key} value={key} label={key}>
                          <div>
                            <div style={{ fontWeight: 500 }}>{key}</div>
                            <div style={{ fontSize: 12, color: '#999' }}>{val.summary || ''}</div>
                          </div>
                        </Select.Option>
                      ))}
                    </Select>
                  ),
                },
                {
                  key: 'brands',
                  label: <span><ThunderboltOutlined /> 品牌模板</span>,
                  children: (
                    <Select
                      style={{ width: '100%' }}
                      value={pptConfig.template}
                      onChange={(value) => setPptConfig({ ...pptConfig, template: value })}
                      placeholder="选择品牌模板"
                      optionLabelProp="label"
                    >
                      {Object.entries(templates.brands).map(([key, val]) => (
                        <Select.Option key={key} value={key} label={key}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            {val.primary_color && (
                              <span style={{
                                display: 'inline-block', width: 12, height: 12,
                                borderRadius: '50%', background: val.primary_color,
                              }} />
                            )}
                            <div>
                              <div style={{ fontWeight: 500 }}>{key}</div>
                              <div style={{ fontSize: 12, color: '#999' }}>{val.summary || ''}</div>
                            </div>
                          </div>
                        </Select.Option>
                      ))}
                    </Select>
                  ),
                },
              ]}
            />
          </Form.Item>

          <Form.Item label="画布格式">
            <Select
              value={pptConfig.canvasFormat}
              onChange={(value: CanvasFormat) => setPptConfig({ ...pptConfig, canvasFormat: value })}
            >
              <Select.Option value="ppt169">16:9 宽屏</Select.Option>
              <Select.Option value="ppt43">4:3 标准</Select.Option>
              <Select.Option value="xiaohongshu">小红书 (3:4)</Select.Option>
              <Select.Option value="wechat">微信文章头图</Select.Option>
              <Select.Option value="moments">朋友圈 (1:1)</Select.Option>
              <Select.Option value="story">竖屏 (9:16)</Select.Option>
              <Select.Option value="a4">A4 打印</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item label="配色方案">
            <Select
              value={pptConfig.colorScheme}
              onChange={(value) => setPptConfig({ ...pptConfig, colorScheme: value })}
            >
              <Select.Option value="blue">蓝色系</Select.Option>
              <Select.Option value="green">绿色系</Select.Option>
              <Select.Option value="red">红色系</Select.Option>
              <Select.Option value="custom">自定义</Select.Option>
            </Select>
          </Form.Item>

          {pptConfig.colorScheme === 'custom' && (
            <Row gutter={16}>
              <Col span={8}>
                <Form.Item label="主色调">
                  <Input
                    type="color"
                    value={pptConfig.customColors?.primary || '#00529B'}
                    onChange={(e) =>
                      setPptConfig({
                        ...pptConfig,
                        customColors: {
                          ...pptConfig.customColors,
                          primary: e.target.value,
                          secondary: pptConfig.customColors?.secondary || '#0078D7',
                          accent: pptConfig.customColors?.accent || '#FF9800',
                        },
                      })
                    }
                  />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="副色调">
                  <Input
                    type="color"
                    value={pptConfig.customColors?.secondary || '#0078D7'}
                    onChange={(e) =>
                      setPptConfig({
                        ...pptConfig,
                        customColors: {
                          ...pptConfig.customColors,
                          primary: pptConfig.customColors?.primary || '#00529B',
                          secondary: e.target.value,
                          accent: pptConfig.customColors?.accent || '#FF9800',
                        },
                      })
                    }
                  />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="强调色">
                  <Input
                    type="color"
                    value={pptConfig.customColors?.accent || '#FF9800'}
                    onChange={(e) =>
                      setPptConfig({
                        ...pptConfig,
                        customColors: {
                          ...pptConfig.customColors,
                          primary: pptConfig.customColors?.primary || '#00529B',
                          secondary: pptConfig.customColors?.secondary || '#0078D7',
                          accent: e.target.value,
                        },
                      })
                    }
                  />
                </Form.Item>
              </Col>
            </Row>
          )}
        </Form>
      </Modal>
    </div>
  );
};

export default ReportPage;
