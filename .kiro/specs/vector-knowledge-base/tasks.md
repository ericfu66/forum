# Implementation Plan: Vector Knowledge Base

## Overview

本实现计划将现有知识库系统重构为基于向量的语义搜索系统。实现顺序为：先创建基础服务（向量化服务、相似度计算），然后重构数据模型，接着更新知识库服务，最后集成到论坛助手。

## Tasks

- [x] 1. 创建向量化服务基础设施
  - [x] 1.1 创建 EmbeddingService 类
    - 在 `app/services/embedding_service.py` 创建新文件
    - 实现 `__init__` 方法，支持从配置读取 API 参数
    - 实现 `embed_text` 方法，调用 SiliconFlow API
    - 实现 `embed_texts` 方法，支持批量向量化
    - 实现错误处理和日志记录
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [ ]* 1.2 编写 EmbeddingService 单元测试
    - 测试配置加载
    - 测试单文本向量化（mock API）
    - 测试批量向量化（mock API）
    - 测试错误处理
    - _Requirements: 1.2, 1.3, 1.4_

  - [x] 1.3 创建 SimilarityCalculator 工具类
    - 在 `app/utils/similarity.py` 创建新文件
    - 实现 `cosine_similarity` 静态方法
    - 实现 `batch_cosine_similarity` 方法
    - 实现 `find_top_similar` 方法
    - _Requirements: 4.2_

  - [ ]* 1.4 编写 SimilarityCalculator 属性测试
    - **Property 4: Cosine Similarity Mathematical Correctness**
    - **Validates: Requirements 4.2**

- [x] 2. Checkpoint - 确保基础服务测试通过
  - 确保所有测试通过，如有问题请询问用户

- [x] 3. 重构 PostKnowledge 数据模型
  - [x] 3.1 更新 PostKnowledge 模型
    - 修改 `app/models/post_knowledge.py`
    - 添加 `embedding` 字段（Text 类型，存储 JSON）
    - 移除 `summary` 和 `is_summarized` 字段
    - 实现 `get_embedding_vector` 方法
    - 实现 `set_embedding_vector` 方法
    - 添加 `get_all_with_embeddings` 查询方法
    - 添加 `get_entries_without_embeddings` 查询方法
    - 更新 `to_dict` 和 `to_context` 方法
    - _Requirements: 2.1, 2.3, 2.4_

  - [x] 3.2 创建数据库迁移脚本
    - 在 `create_tables.py` 中添加迁移逻辑
    - 处理现有数据的字段变更
    - _Requirements: 2.1, 2.3_

  - [ ]* 3.3 编写 PostKnowledge 属性测试
    - **Property 1: Vector Embedding Round-Trip Consistency**
    - **Validates: Requirements 2.1**

- [x] 4. 重构 KnowledgeService
  - [x] 4.1 更新知识库服务核心功能
    - 修改 `app/services/knowledge_service.py`
    - 移除摘要生成相关代码
    - 在 `process_post_knowledge` 中集成向量化
    - 在 `add_post_to_knowledge_sync` 中集成向量化
    - 更新 `update_post_knowledge` 支持向量更新
    - _Requirements: 2.5, 3.1, 3.2_

  - [x] 4.2 实现向量相似度搜索
    - 实现 `search_similar_knowledge` 函数
    - 重构 `get_relevant_knowledge` 使用向量搜索
    - 实现关键词搜索回退逻辑
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 4.3 编写相似度搜索属性测试
    - **Property 3: Similarity Search Correctness**
    - **Validates: Requirements 4.2, 4.3, 4.4**

  - [x] 4.4 实现知识库管理功能
    - 实现 `revectorize_entry` 函数
    - 实现 `bulk_revectorize` 函数
    - 实现 `get_knowledge_stats` 函数
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ]* 4.5 编写知识库统计属性测试
    - **Property 6: Knowledge Statistics Accuracy**
    - **Validates: Requirements 6.2**

- [x] 5. Checkpoint - 确保知识库服务测试通过
  - 确保所有测试通过，如有问题请询问用户

- [x] 6. 集成论坛助手
  - [x] 6.1 更新 AI 控制器
    - 修改 `app/controllers/ai.py`
    - 更新 `send_message` 使用向量搜索
    - 添加知识库管理 API 端点（重新向量化、统计）
    - _Requirements: 5.1, 5.2, 6.1, 6.2_

  - [x] 6.2 实现上下文大小限制
    - 在 `get_relevant_knowledge` 中添加大小限制逻辑
    - 确保不超过配置的 token 限制
    - _Requirements: 5.5_

  - [ ]* 6.3 编写上下文限制属性测试
    - **Property 7: Context Size Limiting**
    - **Validates: Requirements 5.5**

- [x] 7. 配置管理
  - [x] 7.1 添加配置项
    - 更新 `.env.example` 添加 Embedding 配置示例
    - 更新 `app/config.py` 读取配置
    - 在 `app/services/config_service.py` 添加 embedding 配置获取函数
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [ ]* 7.2 编写配置参数属性测试
    - **Property 8: Search Parameter Configuration Effect**
    - **Validates: Requirements 7.4**

- [x] 8. 清理和文档
  - [x] 8.1 清理废弃代码
    - 移除 AIService 中的 `generate_summary` 方法
    - 移除知识库服务中的摘要相关代码
    - 更新相关导入和引用
    - _Requirements: 2.3_

  - [x] 8.2 ��新依赖
    - 在 `requirements.txt` 添加 numpy（如果未安装）
    - _Requirements: 4.2_

- [x] 9. Final Checkpoint - 确保所有测试通过
  - 运行完整测试套件
  - 确保所有测试通过，如有问题请询问用户

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- 建议先完成核心功能（1, 3, 4），再进行集成（6）和配置（7）
