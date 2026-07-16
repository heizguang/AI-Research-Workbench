"""
数据模型定义
定义API请求和响应的数据结构
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class ReportMode(str, Enum):
    """报告生成模式"""
    AI = "ai"           # 兼容旧值，等同 auto
    DOCUMENT = "document"  # 文档分析模式
    SEARCH = "search"    # 兼容旧值，等同 auto


class ReportFormat(str, Enum):
    """报告格式"""
    MARKDOWN = "markdown"
    WORD = "word"
    PDF = "pdf"


class PPTStyle(str, Enum):
    """PPT样式"""
    PROFESSIONAL = "professional"
    CREATIVE = "creative"
    MINIMAL = "minimal"


# 请求模型

class DateRange(BaseModel):
    """搜索时间范围"""
    start: Optional[str] = Field(None, description="开始日期 YYYY-MM-DD")
    end: Optional[str] = Field(None, description="结束日期 YYYY-MM-DD")


class GenerateReportRequest(BaseModel):
    """生成报告请求"""
    topic: str = Field(..., min_length=1, max_length=500, description="报告主题")
    mode: ReportMode = Field(default=ReportMode.AI, description="生成模式")
    format: ReportFormat = Field(default=ReportFormat.MARKDOWN, description="输出格式")
    file_path: Optional[str] = Field(None, description="上传的文件路径")
    include_search: bool = Field(default=False, description="是否包含网络搜索")
    additional_requirements: Optional[str] = Field(None, description="额外要求")
    date_range: Optional[DateRange] = Field(None, description="搜索时间范围")


class ModifyReportRequest(BaseModel):
    """修改报告请求"""
    report: str = Field(..., description="原始报告内容")
    modifications: str = Field(..., description="修改意见")
    format: ReportFormat = Field(default=ReportFormat.MARKDOWN, description="输出格式")
    search_context: Optional[str] = Field(default=None, description="原始搜索结果上下文，用于基于事实修改")


class AskQuestionRequest(BaseModel):
    """问答请求"""
    question: str = Field(..., description="用户问题")
    report: str = Field(..., description="报告内容")
    session_id: Optional[str] = Field(None, description="会话ID，同一报告的多轮问答共享")
    conversation_id: Optional[str] = Field(None, description="对话ID")
    messages: Optional[List[Dict[str, str]]] = Field(None, description="对话历史，用于多轮上下文")


class PPTOptions(BaseModel):
    """PPT 生成选项"""
    canvas_format: Optional[str] = Field(default="ppt169", description="画布格式: ppt169/ppt43/xhs/story")
    image_generation: bool = Field(default=False, description="是否生成 AI 图片")
    image_style: Optional[str] = Field(default=None, description="图片风格")
    color_scheme: Optional[str] = Field(default=None, description="颜色方案: custom 等")
    custom_colors: Optional[Dict[str, str]] = Field(default=None, description="自定义颜色 {primary, secondary, accent}")
    # 样式配置
    visual_profile: Optional[str] = Field(default="corporate_clear", description="视觉风格: corporate_clear/editorial_ink/swiss_modernist/product_launch")
    communication_profile: Optional[str] = Field(default="business_report", description="内容类型: business_report/technical_explainer/research_review/keynote_story")
    density_profile: Optional[str] = Field(default="balanced_brief", description="信息密度: dense_reference/balanced_brief/low_density_stage")
    delivery_context: Optional[str] = Field(default="hybrid_review_deck", description="传播场景: self-contained_reading_deck/speaker-led_stage_deck/hybrid_review_deck/reference_or_appendix_deck")


class GeneratePPTRequest(BaseModel):
    """生成PPT请求"""
    report_content: str = Field(..., min_length=1, description="报告内容")
    template: str = Field(default="default", description="PPT模板")
    style: PPTStyle = Field(default=PPTStyle.PROFESSIONAL, description="PPT样式")
    options: Optional[PPTOptions] = Field(default=None, description="PPT 生成选项")


class SearchRequest(BaseModel):
    """搜索请求"""
    query: str = Field(..., min_length=1, max_length=500, description="搜索关键词")
    max_results: int = Field(default=15, description="最大结果数")


class AnalyzeDocumentRequest(BaseModel):
    """分析文档请求"""
    file_path: str = Field(..., description="文件路径")
    file_type: str = Field(..., description="文件类型")
    action: str = Field(default="analyze", description="操作类型: analyze, extract, summarize")


# 响应模型

class ReportSection(BaseModel):
    """报告章节"""
    title: str
    content: str


class ReportResponse(BaseModel):
    """报告响应"""
    topic: str
    mode: ReportMode
    format: ReportFormat
    content: str
    sections: List[ReportSection]
    created_at: datetime = Field(default_factory=datetime.now)


class SearchResult(BaseModel):
    """搜索结果"""
    title: str
    url: str
    snippet: str


class SearchResponse(BaseModel):
    """搜索响应"""
    query: str
    results: List[SearchResult]
    summary: str
    total: int


class DocumentAnalysisResponse(BaseModel):
    """文档分析响应"""
    file_path: str
    file_type: str
    content_length: int
    analysis: str


class SlideContent(BaseModel):
    """幻灯片内容"""
    slide_number: int
    title: str
    content: List[str]
    notes: str
    layout: str


class PPTResponse(BaseModel):
    """PPT响应"""
    outline: List[Dict[str, Any]]
    ppt_content: Dict[str, Any]
    template: str
    style: PPTStyle
    download_url: Optional[str] = None


class QAHistoryItem(BaseModel):
    """问答历史项（兼容新旧格式）"""
    id: str
    question: Optional[str] = None
    answer: Optional[str] = None
    timestamp: datetime
    report_topic: Optional[str] = None
    # 新格式字段
    session_id: Optional[str] = None
    report_content: Optional[str] = None
    messages: Optional[List[Dict[str, str]]] = None


class ConversationMessage(BaseModel):
    """对话消息"""
    role: str  # user, assistant
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = {}


class MemoryItem(BaseModel):
    """记忆项"""
    id: str
    content: str
    timestamp: datetime
    importance: float


class APIResponse(BaseModel):
    """通用API响应"""
    success: bool
    data: Optional[Any] = None
    message: Optional[str] = None
    error: Optional[str] = None


class HistoryResponse(BaseModel):
    """历史记录响应"""
    conversations: List[ConversationMessage]
    qa_history: List[QAHistoryItem]
    total: int


class FileUploadResponse(BaseModel):
    """文件上传响应"""
    file_path: str
    file_name: str
    file_size: int
    file_type: str
    upload_time: datetime = Field(default_factory=datetime.now)


# ===== Agent Loop 数据模型 =====

class AgentLoopRunRequest(BaseModel):
    """启动 Agent Loop 请求"""
    goal: str = Field(..., min_length=1, max_length=100000, description="用户目标")
    tools: Optional[List[str]] = Field(None, description="指定工具列表")
    tool_group: str = Field(default="full", description="工具分组")
    max_loops: int = Field(default=20, ge=1, le=50, description="最大循环轮次")
    model: str = Field(default="smart", description="模型: smart / fast")
    context_strategy: str = Field(default="sliding_window", description="上下文策略")
    file_path: Optional[str] = Field(None, description="上传文件路径，有值时走文件报告流程")
    include_search: Optional[bool] = Field(None, description="文件报告时是否补充搜索")
    topic: Optional[str] = Field(None, description="报告主题，文件报告流程使用")


class AgentLoopRunResponse(BaseModel):
    """Agent Loop 启动响应"""
    task_id: str
    status: str = "running"
    stream_url: str


class AskUserReply(BaseModel):
    """回复 ask_user 提问"""
    tool_call_id: str
    answer: str


class LoopTraceStep(BaseModel):
    """轨迹步骤"""
    loop: int = 0
    type: str = ""
    content: Optional[str] = None
    tool: Optional[str] = None
    tool_input: Optional[dict] = None
    tool_output: Optional[str] = None
    tokens: int = 0
    timestamp: Optional[str] = None


class AgentLoopTrace(BaseModel):
    """执行轨迹"""
    trace_id: str
    goal: str
    status: str = ""
    total_loops: int = 0
    total_tokens: int = 0
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    steps: List[dict] = []
    token_budget: Optional[dict] = None


class ToolInfo(BaseModel):
    """工具信息"""
    name: str
    description: str
    enabled: bool
    timeout: int
    group: str = "full"
