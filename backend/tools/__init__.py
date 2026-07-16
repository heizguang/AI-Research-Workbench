"""
工具注册入口 — 将所有内置工具注册到全局 ToolRegistry
"""
from core.tool_registry import registry, Tool

from .web_search import WebSearchTool
from .file_ops import ReadFileTool, WriteFileTool
from .code_runner import RunCodeTool
from .report_gen import GenerateReportTool, ModifyReportTool
from .ppt_gen import GeneratePPTTool
from .ask_user import AskUserTool


def register_all_tools():
    """注册所有内置工具"""
    # web_search: 属于 search_only, report, ppt, code, qa 分组
    ws = WebSearchTool()
    registry.register(Tool(
        name=ws.name, description=ws.description, parameters=ws.parameters,
        execute=ws.execute, timeout=ws.timeout, group="search_only"
    ))

    # read_file: 属于 search_only, report, ppt, code, qa 分组
    rf = ReadFileTool()
    registry.register(Tool(
        name=rf.name, description=rf.description, parameters=rf.parameters,
        execute=rf.execute, timeout=rf.timeout, group="search_only"
    ))

    # write_file: 属于 report, code 分组
    wf = WriteFileTool()
    registry.register(Tool(
        name=wf.name, description=wf.description, parameters=wf.parameters,
        execute=wf.execute, timeout=wf.timeout, group="report"
    ))

    # run_code: 属于 code 分组
    rc = RunCodeTool()
    registry.register(Tool(
        name=rc.name, description=rc.description, parameters=rc.parameters,
        execute=rc.execute, timeout=rc.timeout, group="code"
    ))

    # generate_report: 属于 report, ppt 分组
    gr = GenerateReportTool()
    registry.register(Tool(
        name=gr.name, description=gr.description, parameters=gr.parameters,
        execute=gr.execute, timeout=gr.timeout, group="report"
    ))

    # modify_report: 属于 report 分组
    mr = ModifyReportTool()
    registry.register(Tool(
        name=mr.name, description=mr.description, parameters=mr.parameters,
        execute=mr.execute, timeout=mr.timeout, group="report"
    ))

    # generate_ppt: 属于 ppt 分组
    gp = GeneratePPTTool()
    registry.register(Tool(
        name=gp.name, description=gp.description, parameters=gp.parameters,
        execute=gp.execute, timeout=gp.timeout, group="ppt"
    ))

    # ask_user: 属于 full 分组
    au = AskUserTool()
    registry.register(Tool(
        name=au.name, description=au.description, parameters=au.parameters,
        execute=au.execute, timeout=au.timeout, group="full"
    ))