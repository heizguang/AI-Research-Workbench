"""
记忆系统模块
实现短期记忆（对话上下文）和长期记忆（向量存储）
支持Milvus和FAISS两种向量数据库
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime
import json
import os
from pathlib import Path
import hashlib
import logging
import warnings

logger = logging.getLogger(__name__)

# 抑制PyMilvus弃用警告
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pymilvus")
warnings.filterwarnings("ignore", message=".*PyMilvusDeprecationWarning.*")
warnings.filterwarnings("ignore", message=".*ORM-style.*")


class MemoryItem(BaseModel):
    """记忆项"""
    id: str
    content: str
    metadata: Dict[str, Any]
    timestamp: datetime
    importance: float = 0.5  # 重要性分数 0-1


class ConversationMemory:
    """对话记忆（短期记忆）"""

    def __init__(self, max_history: int = 50):
        self.max_history = max_history
        self.history: List[Dict[str, Any]] = []

    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        """添加消息到历史"""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        self.history.append(message)

        # 保持历史长度
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取历史消息"""
        if limit:
            return self.history[-limit:]
        return self.history

    def get_context_window(self, window_size: int = 10) -> List[Dict[str, Any]]:
        """获取上下文窗口"""
        return self.history[-window_size:]

    def clear(self):
        """清空历史"""
        self.history = []

    def to_dict(self) -> Dict[str, Any]:
        """导出为字典"""
        return {
            "history": self.history,
            "max_history": self.max_history
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationMemory':
        """从字典创建"""
        memory = cls(max_history=data.get("max_history", 50))
        memory.history = data.get("history", [])
        return memory


class VectorStoreBase:
    """向量存储基类"""

    def add(self, id: str, content: str, metadata: Dict[str, Any]) -> str:
        raise NotImplementedError

    def search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def delete(self, id: str):
        raise NotImplementedError

    def get_all(self) -> List[Dict[str, Any]]:
        raise NotImplementedError


def _local_embedding(text: str, dim: int = 384) -> List[float]:
    """
    本地文本嵌入（基于字符 n-gram + 哈希投影）
    相比纯 MD5 随机向量，此方法能让相似文本产生相似向量
    """
    import numpy as np
    import re

    # 清洗并分词（中文按字符，英文按单词）
    text = text.lower().strip()
    # 提取中文字符和英文单词
    tokens = re.findall(r'[一-鿿]|[a-z]+', text)

    # 生成字符 bigram 特征
    bigrams = set()
    for i in range(len(tokens) - 1):
        bigrams.add(tokens[i] + tokens[i + 1])
    # 也加入 unigram
    for t in tokens:
        bigrams.add(t)

    if not bigrams:
        return [0.0] * dim

    # 使用哈希投影将特征映射到固定维度
    vec = np.zeros(dim, dtype=np.float32)
    for gram in bigrams:
        h = int(hashlib.md5(gram.encode('utf-8')).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h // dim) % 2 == 0 else -1.0
        vec[idx] += sign

    # L2 归一化
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm

    return vec.tolist()


class MilvusStore(VectorStoreBase):
    """Milvus向量存储"""

    def __init__(self, collection_name: str = "memory", host: str = "localhost", port: str = "19530"):
        from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility

        self.collection_name = collection_name

        # 连接Milvus
        connections.connect(host=host, port=port)

        # 定义集合Schema
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=384)
        ]
        schema = CollectionSchema(fields, description="Memory storage")

        # 创建或获取集合
        if utility.has_collection(collection_name):
            self.collection = Collection(collection_name)
        else:
            self.collection = Collection(collection_name, schema)
            # 创建索引
            index_params = {
                "metric_type": "L2",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 1024}
            }
            self.collection.create_index("embedding", index_params)

        self.collection.load()
        self.dim = 384

    def _get_embedding(self, text: str) -> List[float]:
        """获取文本嵌入向量（基于字符 n-gram 哈希投影，相似文本产生相似向量）"""
        return _local_embedding(text, self.dim)

    def add(self, id: str, content: str, metadata: Dict[str, Any]) -> str:
        """添加记忆"""
        from pymilvus import Collection

        embedding = self._get_embedding(content)

        data = [
            [id],
            [content],
            [json.dumps(metadata, ensure_ascii=False)],
            [embedding]
        ]

        self.collection.insert(data)
        self.collection.flush()

        return id

    def search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """搜索记忆"""
        embedding = self._get_embedding(query)

        search_params = {
            "metric_type": "L2",
            "params": {"nprobe": 10}
        }

        results = self.collection.search(
            data=[embedding],
            anns_field="embedding",
            param=search_params,
            limit=n_results,
            output_fields=["content", "metadata"]
        )

        memories = []
        for hits in results:
            for hit in hits:
                memories.append({
                    "id": hit.id,
                    "content": hit.entity.get("content"),
                    "metadata": json.loads(hit.entity.get("metadata", "{}")),
                    "score": hit.score
                })

        return memories

    def delete(self, id: str):
        """删除记忆"""
        self.collection.delete(f'id == "{id}"')

    def get_all(self) -> List[Dict[str, Any]]:
        """获取所有记忆"""
        results = self.collection.query(
            expr="id != ''",
            output_fields=["id", "content", "metadata"]
        )

        memories = []
        for result in results:
            memories.append({
                "id": result["id"],
                "content": result["content"],
                "metadata": json.loads(result.get("metadata", "{}"))
            })

        return memories


class FAISSStore(VectorStoreBase):
    """FAISS向量存储"""

    def __init__(self, collection_name: str = "memory", persist_dir: str = "./data/memory"):
        import faiss
        import numpy as np

        self.collection_name = collection_name
        self.persist_dir = persist_dir
        self.dim = 384

        os.makedirs(persist_dir, exist_ok=True)

        # 初始化或加载索引
        index_path = os.path.join(persist_dir, f"{collection_name}.index")
        data_path = os.path.join(persist_dir, f"{collection_name}.json")

        if os.path.exists(index_path) and os.path.exists(data_path):
            self.index = faiss.read_index(index_path)
            with open(data_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        else:
            self.index = faiss.IndexFlatL2(self.dim)
            self.data = {}

    def _get_embedding(self, text: str) -> List[float]:
        """获取文本嵌入向量（基于字符 n-gram 哈希投影）"""
        return _local_embedding(text, self.dim)

    def _save(self):
        """保存索引和数据"""
        import faiss

        index_path = os.path.join(self.persist_dir, f"{self.collection_name}.index")
        data_path = os.path.join(self.persist_dir, f"{self.collection_name}.json")

        faiss.write_index(self.index, index_path)
        with open(data_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def add(self, id: str, content: str, metadata: Dict[str, Any]) -> str:
        """添加记忆"""
        import numpy as np

        embedding = np.array([self._get_embedding(content)], dtype='float32')

        self.index.add(embedding)
        self.data[str(self.index.ntotal - 1)] = {
            "id": id,
            "content": content,
            "metadata": metadata,
            "timestamp": datetime.now().isoformat()
        }

        self._save()
        return id

    def search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """搜索记忆"""
        import numpy as np

        if self.index.ntotal == 0:
            return []

        embedding = np.array([self._get_embedding(query)], dtype='float32')
        n_results = min(n_results, self.index.ntotal)

        distances, indices = self.index.search(embedding, n_results)

        memories = []
        for dist, idx in zip(distances[0], indices[0]):
            idx_str = str(idx)
            if idx_str in self.data:
                memory = self.data[idx_str].copy()
                memory["score"] = float(dist)
                memories.append(memory)

        return memories

    def delete(self, id: str):
        """删除记忆（标记删除）"""
        for idx, data in self.data.items():
            if data["id"] == id:
                del self.data[idx]
                break
        self._save()

    def get_all(self) -> List[Dict[str, Any]]:
        """获取所有记忆"""
        return list(self.data.values())


class FileStore(VectorStoreBase):
    """文件存储（降级方案）"""

    def __init__(self, collection_name: str = "memory", persist_dir: str = "./data/memory"):
        self.collection_name = collection_name
        self.persist_dir = persist_dir
        self.data_path = os.path.join(persist_dir, f"{collection_name}.json")

        os.makedirs(persist_dir, exist_ok=True)

        if os.path.exists(self.data_path):
            with open(self.data_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        else:
            self.data = {}

    def _save(self):
        """保存数据"""
        with open(self.data_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def add(self, id: str, content: str, metadata: Dict[str, Any]) -> str:
        """添加记忆"""
        self.data[id] = {
            "content": content,
            "metadata": metadata,
            "timestamp": datetime.now().isoformat()
        }
        self._save()
        return id

    def search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """搜索记忆（关键词匹配）"""
        results = []
        query_lower = query.lower()

        for id, item in self.data.items():
            content = item["content"].lower()
            if query_lower in content:
                results.append({
                    "id": id,
                    "content": item["content"],
                    "metadata": item.get("metadata", {}),
                    "score": 1.0
                })

        return results[:n_results]

    def delete(self, id: str):
        """删除记忆"""
        if id in self.data:
            del self.data[id]
            self._save()

    def get_all(self) -> List[Dict[str, Any]]:
        """获取所有记忆"""
        return [
            {"id": id, **item}
            for id, item in self.data.items()
        ]


class LongTermMemory:
    """长期记忆"""

    def __init__(self, collection_name: str = "memory", persist_dir: str = "./data/memory"):
        self.persist_dir = persist_dir
        os.makedirs(persist_dir, exist_ok=True)

        # 根据环境变量选择存储后端
        self.store_type = os.getenv("VECTOR_STORE", "file")

        if self.store_type == "milvus":
            milvus_host = os.getenv("MILVUS_HOST", "localhost")
            milvus_port = os.getenv("MILVUS_PORT", "19530")
            self.store = MilvusStore(collection_name, milvus_host, milvus_port)
        elif self.store_type == "faiss":
            self.store = FAISSStore(collection_name, persist_dir)
        else:
            self.store = FileStore(collection_name, persist_dir)

    def add_memory(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        importance: float = 0.5
    ) -> str:
        """添加记忆"""
        import uuid
        memory_id = str(uuid.uuid4())

        meta = metadata or {}
        meta.update({
            "timestamp": datetime.now().isoformat(),
            "importance": importance
        })

        return self.store.add(memory_id, content, meta)

    def search_memory(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: Optional[Dict] = None
    ) -> List[MemoryItem]:
        """搜索记忆"""
        results = self.store.search(query, n_results)

        memories = []
        for result in results:
            meta = result.get("metadata", {})
            memories.append(MemoryItem(
                id=result["id"],
                content=result["content"],
                metadata=meta,
                timestamp=datetime.fromisoformat(meta.get("timestamp", datetime.now().isoformat())),
                importance=meta.get("importance", 0.5)
            ))

        return memories

    def update_memory(self, memory_id: str, content: str, metadata: Optional[Dict] = None):
        """更新记忆"""
        self.store.delete(memory_id)
        self.store.add(memory_id, content, metadata or {})

    def delete_memory(self, memory_id: str):
        """删除记忆"""
        self.store.delete(memory_id)

    def get_all_memories(self) -> List[MemoryItem]:
        """获取所有记忆"""
        results = self.store.get_all()

        memories = []
        for result in results:
            meta = result.get("metadata", {})
            memories.append(MemoryItem(
                id=result["id"],
                content=result["content"],
                metadata=meta,
                timestamp=datetime.fromisoformat(meta.get("timestamp", datetime.now().isoformat())),
                importance=meta.get("importance", 0.5)
            ))

        return memories


class MemoryManager:
    """记忆管理器"""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.conversation_memory = ConversationMemory()
        self.long_term_memory = LongTermMemory(
            collection_name=f"user_{user_id}",
            persist_dir=f"./data/memory/{user_id}"
        )

    def add_conversation(self, role: str, content: str, metadata: Optional[Dict] = None):
        """添加对话记忆"""
        self.conversation_memory.add_message(role, content, metadata)

        # 重要内容也存入长期记忆
        if self._is_important(content):
            self.long_term_memory.add_memory(
                content=content,
                metadata={"type": "conversation", "role": role, **(metadata or {})},
                importance=0.8
            )

    def add_long_term_memory(
        self,
        content: str,
        metadata: Optional[Dict] = None,
        importance: float = 0.5
    ) -> str:
        """添加长期记忆"""
        return self.long_term_memory.add_memory(content, metadata, importance)

    def search_memory(
        self,
        query: str,
        n_results: int = 5,
        include_conversation: bool = True
    ) -> List[MemoryItem]:
        """搜索记忆"""
        results = self.long_term_memory.search_memory(query, n_results)

        if include_conversation:
            # 也搜索对话历史
            for msg in self.conversation_memory.get_history(limit=20):
                if query.lower() in msg['content'].lower():
                    results.append(MemoryItem(
                        id=f"conv_{msg['timestamp']}",
                        content=msg['content'],
                        metadata=msg.get('metadata', {}),
                        timestamp=datetime.fromisoformat(msg['timestamp']),
                        importance=0.3
                    ))

        # 按重要性和时间排序
        results.sort(key=lambda x: (x.importance, x.timestamp.timestamp()), reverse=True)
        return results[:n_results]

    def get_context_for_query(self, query: str, max_tokens: int = 2000) -> str:
        """获取查询的上下文"""
        # 搜索相关记忆
        memories = self.search_memory(query, n_results=5)

        # 获取最近对话
        recent_conversation = self.conversation_memory.get_context_window(window_size=5)

        # 组装上下文
        context_parts = []

        if memories:
            context_parts.append("相关历史记忆：")
            for mem in memories:
                context_parts.append(f"- {mem.content}")

        if recent_conversation:
            context_parts.append("\n最近对话：")
            for msg in recent_conversation:
                context_parts.append(f"{msg['role']}: {msg['content']}")

        context = "\n".join(context_parts)

        # 简单的token限制
        if len(context) > max_tokens * 4:
            context = context[:max_tokens * 4]

        return context

    def _is_important(self, content: str) -> bool:
        """判断内容是否重要"""
        important_keywords = ["报告", "总结", "分析", "结论", "建议", "重要", "关键"]
        return any(keyword in content for keyword in important_keywords)

    def save_state(self):
        """保存状态"""
        state = {
            "user_id": self.user_id,
            "conversation": self.conversation_memory.to_dict()
        }

        state_dir = f"./data/memory/{self.user_id}"
        os.makedirs(state_dir, exist_ok=True)

        with open(f"{state_dir}/state.json", "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def load_state(self):
        """加载状态"""
        state_file = f"./data/memory/{self.user_id}/state.json"
        if os.path.exists(state_file):
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
                self.conversation_memory = ConversationMemory.from_dict(
                    state.get("conversation", {})
                )


# 全局记忆管理器实例
_memory_managers: Dict[str, MemoryManager] = {}


def get_memory_manager(user_id: str) -> MemoryManager:
    """获取用户的记忆管理器"""
    if user_id not in _memory_managers:
        _memory_managers[user_id] = MemoryManager(user_id)
        _memory_managers[user_id].load_state()
    return _memory_managers[user_id]
