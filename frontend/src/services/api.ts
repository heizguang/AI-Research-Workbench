import axios from 'axios';
import {
  GeneratePPTRequest,
  APIResponse,
  PPTData,
  HistoryResponse,
  FileUploadResponse,
} from '../types';

// 获取后端基础地址（兼容本地开发 + GitHub Codespaces）
export const getBackendBase = (): string => {
  const { hostname } = window.location;
  // Codespaces: https://xxx-3081.app.github.dev → https://xxx-8081.app.github.dev
  if (hostname.endsWith('.app.github.dev')) {
    const backendHost = hostname.replace(/-3081\./, '-8081.');
    return `https://${backendHost}`;
  }
  return `http://${hostname}:8081`;
};

const api = axios.create({
  baseURL: `${getBackendBase()}/api`,
  timeout: 300000,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

const pollTaskStatus = async <T>(
  taskId: string,
  statusEndpoint: string,
  maxAttempts: number = 60,
  intervalMs: number = 3000,
): Promise<APIResponse<T>> => {
  let attempts = 0;

  while (attempts < maxAttempts) {
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
    attempts++;

    try {
      const statusResponse = await axios.get(
        `${getBackendBase()}/api${statusEndpoint}/${taskId}`,
        { withCredentials: true, headers: { 'Content-Type': 'application/json' } },
      ) as any;

      const status = statusResponse.data?.data?.status;
      if (status === 'completed') {
        return {
          success: true,
          data: statusResponse.data.data.result,
          message: '任务完成',
        };
      }
      if (status === 'failed') {
        return {
          success: false,
          error: statusResponse.data.error || '任务失败',
        };
      }
    } catch (error) {
      console.error('轮询任务状态失败', error);
    }
  }

  return {
    success: false,
    error: '任务超时，请重试',
  };
};

api.interceptors.request.use(
  (config) => config,
  (error) => Promise.reject(error),
);

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response) {
      console.error('API Error:', error.response.status, error.response.data);
    } else {
      console.error('API Error:', error.message);
    }
    return Promise.reject(error);
  },
);

export const reportAPI = {
  export: async (content: string, format: string, filename?: string): Promise<APIResponse<{ file_path: string; filename: string }>> => {
    return api.post('/reports/export', { content, format, filename });
  },

  download: (filename: string): string => {
    return `${getBackendBase()}/api/reports/download/${filename}`;
  },

  save: async (topic: string, content: string, format: string = 'markdown', mode: string = 'ai'): Promise<APIResponse<{ report_id: string }>> => {
    return api.post('/reports/save', { topic, content, format, mode });
  },

  list: async (limit: number = 50, offset: number = 0): Promise<APIResponse<any[]>> => {
    return api.get('/reports/list', { params: { limit, offset } });
  },

  get: async (reportId: string): Promise<APIResponse<any>> => {
    return api.get(`/reports/${reportId}`);
  },

  delete: async (reportId: string): Promise<APIResponse<void>> => {
    return api.delete(`/reports/${reportId}`);
  },
};

export const pptAPI = {
  getTemplates: async (): Promise<APIResponse<{ decks: Record<string, any>; layouts: Record<string, any>; brands: Record<string, any> }>> => {
    return api.get('/ppt/templates');
  },

  listGenerated: async (): Promise<APIResponse<{ files: Array<{ filename: string; size: number; created_at: string; download_url: string }>; total: number }>> => {
    return api.get('/ppt/list');
  },

  generateAndWait: async (
    request: GeneratePPTRequest,
    onProgress?: (status: string) => void,
  ): Promise<APIResponse<PPTData>> => {
    const submitResponse = await api.post('/ppt/generate', request) as any;
    if (!submitResponse.success) {
      return submitResponse;
    }
    if (onProgress) {
      onProgress('任务已提交，正在生成 PPT...');
    }
    return pollTaskStatus(submitResponse.data.task_id, '/ppt/task', 200, 3000);
  },

  getPreview: async (pptxName: string): Promise<APIResponse<{ pages: Array<{ filename: string; url: string }>; total: number }>> => {
    return api.get(`/ppt/preview/${pptxName}`);
  },

  download: (filename: string): string => {
    return `${getBackendBase()}/api/ppt/download/${filename}`;
  },
};

export const documentAPI = {
  upload: async (file: File): Promise<APIResponse<FileUploadResponse>> => {
    const formData = new FormData();
    formData.append('file', file);

    return api.post('/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },
};

export const historyAPI = {
  getHistory: async (limit?: number): Promise<APIResponse<HistoryResponse>> => {
    return api.get('/history', { params: { limit } });
  },
  saveQAHistory: async (data: {
    question: string;
    answer: string;
    report_content?: string;
    session_id?: string;
  }) => {
    return api.post('/history/save-qa', data);
  },
};

export const memoryAPI = {
  search: async (query: string, nResults?: number): Promise<APIResponse<any[]>> => {
    return api.get('/memory/search', { params: { query, n_results: nResults } });
  },

  save: async (): Promise<APIResponse<void>> => {
    return api.post('/memory/save');
  },
};

export const logAPI = {
  getLogs: async (
    lines: number = 200,
    logType: string = 'backend',
  ): Promise<APIResponse<{ lines: string[]; file: string; total_lines: number; showing: number }>> => {
    return api.get('/logs', { params: { lines, log_type: logType } });
  },
};

export const healthAPI = {
  check: async (): Promise<{ status: string }> => {
    return api.get('/health');
  },
};

export const agentLoopAPI = {
  run: async (request: {
    goal: string;
    tools?: string[];
    tool_group?: string;
    max_loops?: number;
    model?: 'smart' | 'fast';
    context_strategy?: string;
    file_path?: string;
    include_search?: boolean;
    topic?: string;
  }) => {
    return api.post('/agent-loop/run', request);
  },

  stream: (
    taskId: string,
    onStep?: (event: any) => void,
    onDone?: (data: any) => void,
    onError?: (error: string) => void,
  ): AbortController => {
    const controller = new AbortController();
    const baseUrl = getBackendBase();

    (async () => {
      try {
        const response = await fetch(`${baseUrl}/api/agent-loop/${taskId}/stream`, {
          signal: controller.signal,
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
        });

        if (!response.ok) {
          onError?.(`HTTP ${response.status}`);
          return;
        }

        const reader = response.body?.getReader();
        if (!reader) {
          onError?.('无法读取流');
          return;
        }

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                onStep?.(data);
              } catch (parseErr) {
                console.warn('SSE parse error:', parseErr);
              }
            }
          }
        }

        onDone?.({ status: 'completed' });
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          onError?.(err.message || '流式请求失败');
        }
      }
    })();

    return controller;
  },

  interrupt: async (taskId: string) => {
    return api.post(`/agent-loop/${taskId}/interrupt`);
  },

  reply: async (taskId: string, toolCallId: string, answer: string) => {
    return api.post(`/agent-loop/${taskId}/reply`, {
      tool_call_id: toolCallId,
      answer,
    });
  },

  getTrace: async (taskId: string) => {
    return api.get(`/agent-loop/${taskId}/trace`);
  },

  listTraces: async () => {
    return api.get('/agent-loop/traces');
  },

  getTools: async () => {
    return api.get('/agent-loop/tools');
  },

  toggleTool: async (toolName: string) => {
    return api.post(`/agent-loop/tools/${toolName}/toggle`);
  },
};

export default api;
