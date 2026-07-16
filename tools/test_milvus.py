#!/usr/bin/env python3
"""测试 Milvus 向量数据库"""
import random
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType

# 连接
print("[1/4] 连接 Milvus...")
connections.connect(host="localhost", port="19530")
print("  ✅ 连接成功")

# 创建测试集合
print("[2/4] 创建测试集合...")
fields = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
    FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=512),
    FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=128),
]
schema = CollectionSchema(fields)
col = Collection("test_collection", schema)

# 插入数据
print("[3/4] 插入测试数据...")
data = [
    ["hello world", "milvus test", "vector database"],
    [[random.random() for _ in range(128)] for _ in range(3)],
]
col.insert(data)
col.flush()
print(f"  ✅ 插入成功，共 {col.num_entities} 条")

# 查询
print("[4/4] 测试向量查询...")
col.create_index("vector", {"index_type": "IVF_FLAT", "metric_type": "L2", "params": {"nlist": 16}})
col.load()
results = col.search(
    data=[[random.random() for _ in range(128)]],
    anns_field="vector",
    param={"metric_type": "L2", "params": {"nlist": 16}},
    limit=3,
    output_fields=["text"],
)
print(f"  ✅ 查询成功，返回 {len(results[0])} 条结果")

# 清理
col.drop()
connections.disconnect("default")
print("\n🎉 Milvus 全部正常！")
