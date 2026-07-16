"""
报告存储服务
保存生成的报告到本地文件系统
"""

import os
import json
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
import aiofiles


class ReportStorage:
    """报告存储类"""

    def __init__(self, storage_dir: str = "./data/reports"):
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)

    async def save_report(
        self,
        topic: str,
        content: str,
        format: str = "markdown",
        mode: str = "ai",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """保存报告"""
        report_id = str(uuid.uuid4())
        filename = f"{report_id}.json"

        report_data = {
            "id": report_id,
            "topic": topic,
            "content": content,
            "format": format,
            "mode": mode,
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        file_path = os.path.join(self.storage_dir, filename)

        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(report_data, ensure_ascii=False, indent=2))

        return report_id

    async def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """获取报告"""
        filename = f"{report_id}.json"
        file_path = os.path.join(self.storage_dir, filename)

        if not os.path.exists(file_path):
            return None

        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            return json.loads(content)

    async def list_reports(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """列出所有报告"""
        reports = []
        files = []

        for filename in os.listdir(self.storage_dir):
            if filename.endswith('.json'):
                files.append(filename)

        # 按修改时间倒序排列
        files.sort(
            key=lambda f: os.path.getmtime(os.path.join(self.storage_dir, f)),
            reverse=True
        )

        # 分页
        files = files[offset:offset + limit]

        for filename in files:
            file_path = os.path.join(self.storage_dir, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 只返回摘要信息，不返回完整内容
                    reports.append({
                        "id": data.get("id"),
                        "topic": data.get("topic"),
                        "format": data.get("format"),
                        "mode": data.get("mode"),
                        "created_at": data.get("created_at"),
                        "content_preview": data.get("content", "")
                    })
            except Exception:
                continue

        return reports

    async def delete_report(self, report_id: str) -> bool:
        """删除报告"""
        filename = f"{report_id}.json"
        file_path = os.path.join(self.storage_dir, filename)

        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False

    async def update_report(
        self,
        report_id: str,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """更新报告"""
        report = await self.get_report(report_id)
        if not report:
            return False

        if content is not None:
            report["content"] = content
        if metadata is not None:
            report["metadata"].update(metadata)

        report["updated_at"] = datetime.now().isoformat()

        filename = f"{report_id}.json"
        file_path = os.path.join(self.storage_dir, filename)

        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(report, ensure_ascii=False, indent=2))

        return True


# 全局实例
report_storage = ReportStorage()
