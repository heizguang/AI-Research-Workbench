// 报告生成模式
export type ReportMode = 'ai' | 'document' | 'search';

// 报告格式
export type ReportFormat = 'markdown' | 'word' | 'pdf';

// PPT样式
export type PPTStyle = 'professional' | 'creative' | 'minimal';

// PPT画布格式
export type CanvasFormat = 'ppt169' | 'ppt43' | 'xiaohongshu' | 'wechat' | 'moments' | 'story' | 'banner' | 'a4';

// PPT图片风格
export type ImageStyle = 'realistic' | 'cartoon' | 'abstract';

// PPT配置
export interface PPTConfig {
  template: string;
  style: PPTStyle;
  canvasFormat: CanvasFormat;
  imageGeneration: boolean;
  imageStyle: ImageStyle;
  colorScheme: 'blue' | 'green' | 'red' | 'custom';
  customColors?: {
    primary: string;
    secondary: string;
    accent: string;
  };
}

// 报告章节
export interface ReportSection {
  title: string;
  content: string;
}

// 报告数据
export interface Report {
  topic: string;
  mode: ReportMode;
  format: ReportFormat;
  content: string;
  sections: ReportSection[];
  created_at: string;
}

// 搜索结果
export interface SearchResult {
  title: string;
  url: string;
  snippet: string;
}

// 搜索响应
export interface SearchResponse {
  query: string;
  results: SearchResult[];
  summary: string;
  total: number;
}

// 问答历史
export interface QAHistoryItem {
  id: string;
  session_id: string;
  report_topic?: string;
  report_content?: string;
  messages: Array<{ role: string; content: string }>;
  timestamp: string;
}

// 对话消息
export interface ConversationMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  metadata: Record<string, any>;
}

// 记忆项
export interface MemoryItem {
  id: string;
  content: string;
  timestamp: string;
  importance: number;
}

// PPT幻灯片
export interface Slide {
  slide_number: number;
  title: string;
  content: string[];
  notes: string;
  layout: string;
}

// PPT数据
export interface PPTData {
  pptx_path: string;
  template: string;
  style: PPTStyle;
  download_url?: string;
}

// API响应
export interface APIResponse<T = any> {
  success: boolean;
  data?: T;
  message?: string;
  error?: string;
}

// 文件上传响应
export interface FileUploadResponse {
  file_path: string;
  file_name: string;
  file_size: number;
  file_type: string;
  upload_time: string;
}

// 历史记录响应
export interface HistoryResponse {
  conversations: ConversationMessage[];
  qa_history: QAHistoryItem[];
  total: number;
}

// 搜索时间范围
export interface DateRange {
  start?: string;  // YYYY-MM-DD
  end?: string;    // YYYY-MM-DD
}

// 生成报告请求
export interface GenerateReportRequest {
  topic: string;
  mode: ReportMode;
  format: ReportFormat;
  file_path?: string;
  include_search: boolean;
  additional_requirements?: string;
  date_range?: DateRange;
}

// 修改报告请求
export interface ModifyReportRequest {
  report: string;
  modifications: string;
  format: ReportFormat;
  search_context?: string;
}

// 问答请求
export interface AskQuestionRequest {
  question: string;
  report: string;
  session_id?: string;
  conversation_id?: string;
  messages?: Array<{ role: string; content: string }>;
}

// 样式配置类型
export type VisualProfile = 'corporate_clear' | 'editorial_ink' | 'swiss_modernist' | 'product_launch';
export type CommunicationProfile = 'business_report' | 'technical_explainer' | 'research_review' | 'keynote_story';
export type DensityProfile = 'dense_reference' | 'balanced_brief' | 'low_density_stage';
export type DeliveryContext = 'self-contained_reading_deck' | 'speaker-led_stage_deck' | 'hybrid_review_deck' | 'reference_or_appendix_deck';

// 生成PPT请求
export interface GeneratePPTRequest {
  report_content: string;
  template: string;
  style: PPTStyle;
  options?: {
    canvas_format?: CanvasFormat;
    image_generation?: boolean;
    image_style?: ImageStyle;
    color_scheme?: string;
    custom_colors?: {
      primary: string;
      secondary: string;
      accent: string;
    };
    // 样式配置
    visual_profile?: VisualProfile;
    communication_profile?: CommunicationProfile;
    density_profile?: DensityProfile;
    delivery_context?: DeliveryContext;
  };
}

// 搜索请求
export interface SearchRequest {
  query: string;
  max_results: number;
}

// 分析文档请求
export interface AnalyzeDocumentRequest {
  file_path: string;
  file_type: string;
  action: 'analyze' | 'extract' | 'summarize';
}

// ===== Agent Loop 类型 =====

export interface AgentLoopRunRequest {
  goal: string;
  tools?: string[];
  tool_group?: string;
  max_loops?: number;
  model?: 'smart' | 'fast';
  context_strategy?: string;
}

export interface AgentLoopRunResponse {
  task_id: string;
  status: string;
  stream_url: string;
}

export interface LoopEvent {
  loop: number;
  type: string; // "think_chunk" | "think" | "tool_call" | "observe" | "done" | "error"
  stage?: string; // 流水线阶段（文件报告流程）：解析文档 / 搜索补充 / 生成报告
  content?: string;
  tool?: string;
  tool_call_id?: string;
  tool_input?: Record<string, any>;
  tool_output?: string;
  result?: string;
  status?: string;
  tokens?: number;
  timestamp?: string;
}

export interface AgentLoopTrace {
  trace_id: string;
  goal: string;
  status: string;
  total_loops: number;
  total_tokens: number;
  started_at?: string;
  finished_at?: string;
  steps: LoopEvent[];
  token_budget?: Record<string, any>;
}

export interface ToolInfo {
  name: string;
  description: string;
  enabled: boolean;
  timeout: number;
  group: string;
}

export interface AskUserReply {
  tool_call_id: string;
  answer: string;
}
