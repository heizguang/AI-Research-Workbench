import React, { useState } from 'react';
import { Card, Switch, Tag, Space, Select, Typography, Tooltip } from 'antd';
import {
  SearchOutlined, FileTextOutlined, CodeOutlined,
  QuestionCircleOutlined, SettingOutlined
} from '@ant-design/icons';
import { ToolInfo } from '../types';

const { Text, Title } = Typography;

const TOOL_GROUPS: Record<string, { label: string; description: string }> = {
  full: { label: '全部工具', description: '使用所有可用工具，适合复杂任务' },
  search_only: { label: '仅搜索', description: '只做调研，不生成产物' },
  report: { label: '报告生成', description: '搜索 + 文件 + 报告生成' },
  ppt: { label: 'PPT 制作', description: '搜索 + 报告 + PPT 生成' },
  code: { label: '代码分析', description: '搜索 + 代码执行 + 文件' },
  qa: { label: '问答', description: '搜索 + 文件（不需要生成文件）' },
};

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

interface ToolConfigPanelProps {
  tools: ToolInfo[];
  selectedGroup: string;
  onGroupChange: (group: string) => void;
  onToggleTool: (toolName: string) => void;
}

const ToolConfigPanel: React.FC<ToolConfigPanelProps> = ({
  tools,
  selectedGroup,
  onGroupChange,
  onToggleTool,
}) => {
  return (
    <Card
      size="small"
      title={
        <Space>
          <SettingOutlined />
          <span>工具配置</span>
        </Space>
      }
      style={{ marginBottom: 16 }}
    >
      {/* 工具分组选择 */}
      <div style={{ marginBottom: 16 }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
          预设分组
        </Text>
        <Select
          value={selectedGroup}
          onChange={onGroupChange}
          style={{ width: '100%' }}
          options={Object.entries(TOOL_GROUPS).map(([key, val]) => ({
            value: key,
            label: (
              <Tooltip title={val.description}>
                <span>{val.label}</span>
              </Tooltip>
            ),
          }))}
        />
      </div>

      {/* 工具开关列表 */}
      <div>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
          可用工具
        </Text>
        <Space direction="vertical" style={{ width: '100%' }} size={8}>
          {tools.map((tool) => (
            <div
              key={tool.name}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '4px 0',
              }}
            >
              <Space size={4}>
                <span style={{ fontSize: 14 }}>{toolIcons[tool.name] || '🔧'}</span>
                <Text style={{ fontSize: 13 }}>{tool.name}</Text>
                <Tag color={tool.enabled ? 'green' : 'default'} style={{ fontSize: 10, margin: 0 }}>
                  {tool.enabled ? '开启' : '关闭'}
                </Tag>
              </Space>
              <Switch
                size="small"
                checked={tool.enabled}
                onChange={() => onToggleTool(tool.name)}
              />
            </div>
          ))}
        </Space>
      </div>
    </Card>
  );
};

export default ToolConfigPanel;
