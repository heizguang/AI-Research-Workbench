import React, { useState, useEffect } from 'react';
import {
  Card,
  Form,
  Input,
  Button,
  Typography,
  message,
  Spin,
  List,
  Space,
  Empty,
} from 'antd';
import {
  FilePptOutlined,
  DownloadOutlined,
  PlayCircleOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import { pptAPI, getBackendBase } from '../services/api';
import { PPTData } from '../types';
import { useLocation } from 'react-router-dom';
import { useResponsive } from '../hooks/useResponsive';

const { Title, Paragraph } = Typography;
const { TextArea } = Input;

const PPTPage: React.FC = () => {
  const { isMobile } = useResponsive();
  const location = useLocation();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [pptData, setPptData] = useState<PPTData | null>(null);
  const [generatedFiles, setGeneratedFiles] = useState<Array<{ filename: string; size: number; created_at: string; download_url: string }>>([]);
  const [filesLoading, setFilesLoading] = useState(true);

  // 加载已生成的PPT列表
  const loadGeneratedFiles = () => {
    setFilesLoading(true);
    pptAPI.listGenerated().then((res) => {
      if (res.success && res.data) {
        setGeneratedFiles(res.data.files);
      }
    }).catch(console.error).finally(() => setFilesLoading(false));
  };

  useEffect(() => {
    loadGeneratedFiles();
  }, []);

  // 接收从历史页面传递过来的报告内容
  useEffect(() => {
    if (location.state?.reportContent) {
      form.setFieldsValue({ report_content: location.state.reportContent });
      message.success('已导入报告内容');
    }
  }, [location.state, form]);

  const handleGenerate = async (values: any) => {
    setLoading(true);
    try {
      const response = await pptAPI.generateAndWait({
        report_content: values.report_content,
        template: 'default',
        style: 'professional',
      });

      if (response.success && response.data) {
        setPptData(response.data);
        message.success('PPT生成成功！');
        loadGeneratedFiles();
      } else {
        message.error(response.error || 'PPT生成失败');
      }
    } catch (error) {
      message.error('生成PPT时出错，请重试');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = (downloadUrl: string, filename?: string) => {
    const backendUrl = getBackendBase();
    const link = document.createElement('a');
    link.href = downloadUrl.startsWith('http')
      ? downloadUrl
      : `${backendUrl}${downloadUrl}`;
    link.download = filename || 'presentation.pptx';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    message.success('PPT下载已开始');
  };

  return (
    <div style={{ padding: isMobile ? '12px 0' : '24px 0' }}>
      <Title level={isMobile ? 3 : 2}>
        <FilePptOutlined style={{ marginRight: 12 }} />
        PPT生成
      </Title>
      <Paragraph style={{ marginBottom: isMobile ? 12 : 24 }}>
        将报告内容转换为专业的汇报PPT
      </Paragraph>

      <div style={{ display: 'flex', flexDirection: isMobile ? 'column' : 'row', gap: isMobile ? 12 : 24 }}>
        {/* 左侧：输入区域 */}
        <Card title="报告内容" style={{ width: isMobile ? '100%' : 450 }}>
          <Form
            form={form}
            layout="vertical"
            onFinish={handleGenerate}
          >
            <Form.Item
              name="report_content"
              rules={[{ required: true, message: '请输入报告内容' }]}
            >
              <TextArea
                rows={15}
                placeholder="请粘贴或输入报告内容，AI将自动生成PPT..."
                style={{ resize: 'none' }}
              />
            </Form.Item>

            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                disabled={loading}
                block
                size="large"
                icon={<PlayCircleOutlined />}
              >
                生成PPT
              </Button>
            </Form.Item>
          </Form>
        </Card>

        {/* 右侧：预览 / 下载区域 */}
        <Card
          title="PPT预览"
          style={{ flex: 1 }}
          extra={
            pptData?.download_url && (
              <Button
                type="primary"
                icon={<DownloadOutlined />}
                onClick={() => handleDownload(pptData.download_url!)}
              >
                下载PPT
              </Button>
            )
          }
        >
          {loading ? (
            <div style={{ textAlign: 'center', padding: '48px 0' }}>
              <Spin size="large" />
              <Paragraph style={{ marginTop: 16 }}>正在生成PPT，约需1-2分钟...</Paragraph>
            </div>
          ) : pptData ? (
            <div style={{ textAlign: 'center', padding: '48px 0' }}>
              <FilePptOutlined style={{ fontSize: 64, color: '#1890ff', marginBottom: 16 }} />
              <Paragraph>PPT 已生成成功！</Paragraph>
              {pptData.download_url ? (
                <Button
                  type="primary"
                  icon={<DownloadOutlined />}
                  size="large"
                  onClick={() => handleDownload(
                    pptData.download_url!,
                    pptData.pptx_path?.split('/').pop()
                  )}
                >
                  下载 PPT
                </Button>
              ) : (
                <Paragraph type="secondary">请到下方「我的PPT」列表中下载</Paragraph>
              )}
            </div>
          ) : (
            <Empty
              description="请在左侧输入报告内容，然后点击生成PPT按钮"
              style={{ padding: '48px 0' }}
            />
          )}
        </Card>
      </div>

      {/* 已生成的PPT列表 */}
      <Card
        title={<><ClockCircleOutlined style={{ marginRight: 8 }} />我的PPT</>}
        style={{ marginTop: 24 }}
        extra={
          <Button size="small" onClick={loadGeneratedFiles} loading={filesLoading}>
            刷新
          </Button>
        }
      >
        {filesLoading ? (
          <Spin size="small" />
        ) : generatedFiles.length === 0 ? (
          <Empty description="暂无已生成的PPT" />
        ) : (
          <List
            dataSource={generatedFiles}
            renderItem={(item) => (
              <List.Item
                actions={[
                  <Button
                    type="link"
                    icon={<DownloadOutlined />}
                    onClick={() => handleDownload(item.download_url, item.filename)}
                  >
                    下载
                  </Button>,
                ]}
              >
                <List.Item.Meta
                  avatar={<FilePptOutlined style={{ fontSize: 24, color: '#1890ff' }} />}
                  title={item.filename}
                  description={
                    <Space size="middle">
                      <span>{(item.size / 1024).toFixed(1)} KB</span>
                      <span>{new Date(item.created_at).toLocaleString('zh-CN')}</span>
                    </Space>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Card>
    </div>
  );
};

export default PPTPage;
