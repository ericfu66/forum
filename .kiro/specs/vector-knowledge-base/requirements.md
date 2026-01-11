# Requirements Document

## Introduction

本功能旨在重写论坛知识库系统，将现有的基于关键词搜索的知识库升级为基于向量化的语义搜索系统。通过调用 SiliconFlow 的向量化模型（Embedding API），实现更精准的语义匹配，同时去除知识库条数限制和摘要功能，简化系统架构。论坛助手将集成向量化检索能力，显著提升问答质量和响应性能。

## Glossary

- **Vector_Knowledge_System**: 向量化知识库系统，负责帖子内容的向量化存储和语义检索
- **Embedding_Service**: 向量化服务，调用 SiliconFlow API 将文本转换为向量
- **Post_Knowledge**: 帖子知识条目，包含帖子内容和对应的向量表示
- **Similarity_Search**: 相似度搜索，基于向量余弦相似度查找相关内容
- **Forum_Assistant**: 论坛助手，集成向量检索的 AI 对话功能
- **SiliconFlow_API**: SiliconFlow 提供的向量化模型 API 接口

## Requirements

### Requirement 1: 向量化服务集成

**User Story:** As a system administrator, I want to integrate SiliconFlow embedding API, so that the system can convert text content into vector representations.

#### Acceptance Criteria

1. THE Embedding_Service SHALL support configurable SiliconFlow API endpoint and API key
2. WHEN text content is provided, THE Embedding_Service SHALL return a vector representation
3. THE Embedding_Service SHALL support batch text vectorization for efficiency
4. IF the SiliconFlow API call fails, THEN THE Embedding_Service SHALL log the error and return a graceful failure response
5. THE Embedding_Service SHALL cache API configuration to avoid repeated config lookups

### Requirement 2: 知识库数据模型重构

**User Story:** As a developer, I want to redesign the knowledge base data model, so that it supports vector storage without entry limits.

#### Acceptance Criteria

1. THE Post_Knowledge model SHALL store vector embeddings as a serialized field
2. THE Post_Knowledge model SHALL NOT have any entry count limitations
3. THE Post_Knowledge model SHALL remove the summary field and is_summarized flag
4. THE Post_Knowledge model SHALL retain post_id, title, content, board_name, author_name, and timestamps
5. WHEN a Post_Knowledge entry is created, THE Vector_Knowledge_System SHALL automatically generate and store the vector embedding

### Requirement 3: 向量化知识入库

**User Story:** As a forum user, I want my posts to be automatically vectorized and stored in the knowledge base, so that they can be semantically searched.

#### Acceptance Criteria

1. WHEN a new post is published, THE Vector_Knowledge_System SHALL asynchronously vectorize and store the content
2. WHEN a post is updated, THE Vector_Knowledge_System SHALL update the corresponding vector embedding
3. WHEN a post is deleted, THE Vector_Knowledge_System SHALL remove the corresponding knowledge entry
4. THE Vector_Knowledge_System SHALL combine title and content for vectorization to capture full semantic meaning
5. IF vectorization fails, THEN THE Vector_Knowledge_System SHALL store the entry without vector and retry later

### Requirement 4: 语义相似度搜索

**User Story:** As a forum assistant user, I want to search knowledge base using semantic similarity, so that I can find relevant content even with different wording.

#### Acceptance Criteria

1. WHEN a search query is provided, THE Similarity_Search SHALL vectorize the query using Embedding_Service
2. THE Similarity_Search SHALL compute cosine similarity between query vector and stored vectors
3. THE Similarity_Search SHALL return top-N most similar entries sorted by similarity score
4. THE Similarity_Search SHALL support configurable similarity threshold to filter low-relevance results
5. WHEN no vectors are available, THE Similarity_Search SHALL fall back to keyword-based search

### Requirement 5: 论坛助手向量检索集成

**User Story:** As a forum user, I want the AI assistant to use vector search for finding relevant knowledge, so that I get more accurate and contextual responses.

#### Acceptance Criteria

1. WHEN a user sends a message to Forum_Assistant, THE Forum_Assistant SHALL use Similarity_Search to find relevant knowledge
2. THE Forum_Assistant SHALL include top relevant knowledge entries in the AI context
3. THE Forum_Assistant SHALL display a relevance indicator when knowledge is used
4. WHEN vector search returns no results, THE Forum_Assistant SHALL proceed without knowledge context
5. THE Forum_Assistant SHALL limit knowledge context size to avoid exceeding token limits

### Requirement 6: 知识库管理功能

**User Story:** As an administrator, I want to manage the vector knowledge base, so that I can maintain data quality and system performance.

#### Acceptance Criteria

1. THE Vector_Knowledge_System SHALL provide an API to manually trigger re-vectorization of entries
2. THE Vector_Knowledge_System SHALL provide statistics on vectorized vs non-vectorized entries
3. WHEN manually adding a post to knowledge base, THE Vector_Knowledge_System SHALL immediately vectorize it
4. THE Vector_Knowledge_System SHALL support bulk re-vectorization for migration purposes

### Requirement 7: 配置管理

**User Story:** As a system administrator, I want to configure embedding service parameters, so that I can optimize performance and costs.

#### Acceptance Criteria

1. THE Vector_Knowledge_System SHALL read SiliconFlow API configuration from environment variables or config file
2. THE Vector_Knowledge_System SHALL support configurable embedding model selection
3. THE Vector_Knowledge_System SHALL support configurable vector dimension
4. THE Vector_Knowledge_System SHALL support configurable similarity search parameters (top-N, threshold)
