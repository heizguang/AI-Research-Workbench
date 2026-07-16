import React, { useState, useEffect } from 'react';
import { Modal, Input, Button, Space } from 'antd';
import { QuestionCircleOutlined } from '@ant-design/icons';

interface AskUserModalProps {
  visible: boolean;
  question: string;
  toolCallId: string;
  taskId: string;
  onReply: (toolCallId: string, answer: string) => void;
  onSkip: (toolCallId: string) => void;
  onClose: () => void;
}

const AskUserModal: React.FC<AskUserModalProps> = ({
  visible,
  question,
  toolCallId,
  taskId,
  onReply,
  onSkip,
  onClose,
}) => {
  const [answer, setAnswer] = useState('');

  useEffect(() => {
    if (visible) {
      setAnswer('');
    }
  }, [visible, toolCallId]);

  const handleSend = () => {
    if (answer.trim()) {
      onReply(toolCallId, answer.trim());
      onClose();
    }
  };

  const handleSkip = () => {
    onSkip(toolCallId);
    onClose();
  };

  return (
    <Modal
      title={
        <Space>
          <QuestionCircleOutlined style={{ color: '#1890ff' }} />
          <span>Agent 想问你</span>
        </Space>
      }
      open={visible}
      onCancel={onClose}
      footer={null}
      width={480}
      centered
      maskClosable={false}
    >
      <div style={{ marginBottom: 16 }}>
        <div style={{
          padding: '12px 16px',
          background: '#f6f8fa',
          borderRadius: 8,
          fontSize: 14,
          lineHeight: 1.6,
        }}>
          {question}
        </div>
      </div>

      <Input.TextArea
        value={answer}
        onChange={(e) => setAnswer(e.target.value)}
        placeholder="输入你的回复..."
        rows={3}
        autoFocus
        onPressEnter={(e) => {
          if (!e.shiftKey) {
            e.preventDefault();
            handleSend();
          }
        }}
      />

      <div style={{ marginTop: 16, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        <Button onClick={handleSkip}>跳过</Button>
        <Button type="primary" onClick={handleSend} disabled={!answer.trim()}>
          发送
        </Button>
      </div>
    </Modal>
  );
};

export default AskUserModal;
