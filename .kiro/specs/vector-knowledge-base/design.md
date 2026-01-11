# Design Document: Vector Knowledge Base

## Overview

本设计文档描述了向量化知识库系统的技术架构和实现方案。系统将现有的基于关键词搜索的知识库升级为基于向量语义搜索的系统，通过调用 SiliconFlow 的 Embedding API 实现文本向量化，使用余弦相似度进行语义检索，从而显著提升论坛助手的问答质量。

### Key Design Decisions

1. **向量存储方案**: 使用 SQLite 存储向量（JSON 序列化），适合中小规模数据，无需额外依赖
2. **Embedding 模型选择**: 默认使用 `BAAI/bge-large-zh-v1.5`，支持中文语义理解，向量维度 1024
3. **相似度计算**: 在 Python 层使用 NumPy 计算余弦相似度，简单高效
4. **异步处理**: 帖子向量化采用异步处理，不阻塞用户操作

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Application Layer                         │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ AI Controller│  │Post Controller│ │ Admin Controller      │  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │
│         │                │                      │                │
├─────────┴────────────────┴──────────────────────┴────────────────┤
│                        Service Layer                             │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ Knowledge Service│  │ Embedding Service│  │ AI Service     │  │
│  │ (向量检索管理)   │  │ (SiliconFlow API)│  │ (对话生成)     │  │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘  │
│           │                    │                     │           │
│           └────────────────────┼─────────────────────┘           │
│                                │                                 │
├────────────────────────────────┴─────────────────────────────────┤
│                        Data Layer                                │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    PostKnowledge Model                       ││
│  │  - id, post_id, title, content                              ││
│  │  - embedding (JSON serialized vector)                       ││
│  │  - board_name, author_name, created_at, updated_at          ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    External Services                             │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────┐│
│  │              SiliconFlow Embedding API                       ││
│  │  POST https://api.siliconflow.cn/v1/embeddings              ││
│  │  Model: BAAI/bge-large-zh-v1.5                              ││
│  │  Output: 1024-dimensional vector                            ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. EmbeddingService (新增)

负责调用 SiliconFlow API 进行文本向量化。

```python
class EmbeddingService:
    """向量化服务 - 调用 SiliconFlow Embedding API"""
    
    def __init__(self, config: dict = None):
        """
        初始化向量化服务
        
        Args:
            config: 配置字典，包含 api_base, api_key, model, dimensions
        """
        pass
    
    def embed_text(self, text: str) -> list[float] | None:
        """
        将单个文本转换为向量
        
        Args:
            text: 输入文本
            
        Returns:
            向量列表，失败返回 None
        """
        pass
    
    def embed_texts(self, texts: list[str]) -> list[list[float] | None]:
        """
        批量将文本转换为向量
        
        Args:
            texts: 输入文本列表
            
        Returns:
            向量列表的列表，单个失败项为 None
        """
        pass
```

### 2. KnowledgeService (重构)

重构现有知识库服务，集成向量化功能。

```python
# 主要接口变更

def add_post_to_knowledge_async(post_id, title, content, board_name, author_name):
    """异步添加帖子到知识库（包含向量化）"""
    pass

def add_post_to_knowledge_sync(post_id, title, content, board_name, author_name) -> dict | None:
    """同步添加帖子到知识库（包含向量化）"""
    pass

def get_relevant_knowledge(query: str, limit: int = 5, threshold: float = 0.5) -> str:
    """
    获取与查询语义相关的知识（向量检索）
    
    Args:
        query: 搜索查询
        limit: 返回数量限制
        threshold: 相似度阈值（0-1）
        
    Returns:
        格式化的知识上下文字符串
    """
    pass

def search_similar_knowledge(query: str, limit: int = 5, threshold: float = 0.5) -> list[tuple]:
    """
    向量相似度搜索
    
    Args:
        query: 搜索查询
        limit: 返回数量
        threshold: 相似度阈值
        
    Returns:
        [(PostKnowledge, similarity_score), ...] 按相似度降序
    """
    pass

def revectorize_entry(post_id: int) -> bool:
    """重新向量化指定条目"""
    pass

def bulk_revectorize(batch_size: int = 50) -> dict:
    """批量重新向量化所有条目"""
    pass
```

### 3. PostKnowledge Model (重构)

```python
class PostKnowledge(db.Model):
    """帖子知识库 - 支持向量存储"""
    __tablename__ = 'post_knowledge'

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False, unique=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    embedding = db.Column(db.Text)  # JSON 序列化的向量，可为空
    board_name = db.Column(db.String(50))
    author_name = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 移除的字段: summary, is_summarized
    
    def get_embedding_vector(self) -> list[float] | None:
        """获取向量（反序列化）"""
        pass
    
    def set_embedding_vector(self, vector: list[float]):
        """设置向量（序列化存储）"""
        pass
    
    @staticmethod
    def get_all_with_embeddings() -> list['PostKnowledge']:
        """获取所有有向量的条目"""
        pass
    
    @staticmethod
    def get_entries_without_embeddings() -> list['PostKnowledge']:
        """获取所有没有向量的条目"""
        pass
```

### 4. SimilarityCalculator (新增工具类)

```python
class SimilarityCalculator:
    """向量相似度计算工具"""
    
    @staticmethod
    def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
        """计算两个向量的余弦相似度"""
        pass
    
    @staticmethod
    def batch_cosine_similarity(query_vec: list[float], vectors: list[list[float]]) -> list[float]:
        """批量计算查询向量与多个向量的相似度"""
        pass
    
    @staticmethod
    def find_top_similar(query_vec: list[float], 
                         candidates: list[tuple[any, list[float]]], 
                         top_k: int = 5,
                         threshold: float = 0.0) -> list[tuple[any, float]]:
        """
        找出最相似的 top-k 个候选
        
        Args:
            query_vec: 查询向量
            candidates: [(item, vector), ...] 候选列表
            top_k: 返回数量
            threshold: 相似度阈值
            
        Returns:
            [(item, similarity), ...] 按相似度降序
        """
        pass
```

## Data Models

### PostKnowledge 表结构变更

```sql
-- 原表结构
CREATE TABLE post_knowledge (
    id INTEGER PRIMARY KEY,
    post_id INTEGER NOT NULL UNIQUE,
    title VARCHAR(200) NOT NULL,
    summary VARCHAR(100),           -- 移除
    content TEXT NOT NULL,
    board_name VARCHAR(50),
    author_name VARCHAR(50),
    is_summarized BOOLEAN,          -- 移除
    created_at DATETIME,
    updated_at DATETIME,
    FOREIGN KEY (post_id) REFERENCES posts(id)
);

-- 新表结构
CREATE TABLE post_knowledge (
    id INTEGER PRIMARY KEY,
    post_id INTEGER NOT NULL UNIQUE,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    embedding TEXT,                 -- 新增: JSON 序列化的向量
    board_name VARCHAR(50),
    author_name VARCHAR(50),
    created_at DATETIME,
    updated_at DATETIME,
    FOREIGN KEY (post_id) REFERENCES posts(id)
);
```

### 配置项

```python
# .env 或 config.json 中的配置
EMBEDDING_API_BASE = "https://api.siliconflow.cn/v1"
EMBEDDING_API_KEY = "sk-xxx"
EMBEDDING_MODEL = "BAAI/bge-large-zh-v1.5"
EMBEDDING_DIMENSIONS = 1024  # 向量维度

# 搜索配置
KNOWLEDGE_SEARCH_LIMIT = 5       # 默认返回数量
KNOWLEDGE_SIMILARITY_THRESHOLD = 0.5  # 相似度阈值
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*



### Property 1: Vector Embedding Round-Trip Consistency

*For any* valid PostKnowledge entry with an embedding vector, serializing the vector to JSON and deserializing it back SHALL produce a vector that is numerically equivalent to the original (within floating-point precision).

**Validates: Requirements 2.1**

### Property 2: Embedding Service Produces Valid Vectors

*For any* non-empty text input (single or batch), the Embedding_Service SHALL return a vector (or list of vectors) where each vector has exactly the configured dimension (default 1024) and all elements are valid floating-point numbers.

**Validates: Requirements 1.2, 1.3**

### Property 3: Similarity Search Correctness

*For any* query vector and set of candidate vectors with known similarities, the Similarity_Search SHALL:
- Return results sorted by descending similarity score
- Exclude all results below the configured threshold
- Return at most top-N results as configured

**Validates: Requirements 4.2, 4.3, 4.4**

### Property 4: Cosine Similarity Mathematical Correctness

*For any* two non-zero vectors of the same dimension, the computed cosine similarity SHALL be in the range [-1, 1], and for identical vectors SHALL equal 1.0.

**Validates: Requirements 4.2**

### Property 5: Knowledge Entry Lifecycle Consistency

*For any* post that is updated or deleted:
- When updated: the corresponding PostKnowledge embedding SHALL be regenerated
- When deleted: the corresponding PostKnowledge entry SHALL be removed

**Validates: Requirements 3.2, 3.3**

### Property 6: Knowledge Statistics Accuracy

*For any* state of the knowledge base, the statistics API SHALL return counts where:
- vectorized_count + non_vectorized_count = total_count
- vectorized_count equals the actual count of entries with non-null embeddings

**Validates: Requirements 6.2**

### Property 7: Context Size Limiting

*For any* set of relevant knowledge entries, the formatted context string SHALL not exceed the configured maximum token/character limit.

**Validates: Requirements 5.5**

### Property 8: Search Parameter Configuration Effect

*For any* similarity search with different top-N and threshold configurations, the results SHALL respect both constraints: returning at most N results, all with similarity >= threshold.

**Validates: Requirements 7.4**

## Error Handling

### Embedding Service Errors

| Error Type | Handling Strategy |
|------------|-------------------|
| API Connection Failure | Log error, return None, allow retry |
| API Rate Limit | Log warning, implement exponential backoff |
| Invalid API Key | Log error, raise configuration exception |
| Timeout | Log warning, return None after 30s timeout |
| Invalid Response | Log error with response details, return None |

### Knowledge Service Errors

| Error Type | Handling Strategy |
|------------|-------------------|
| Vectorization Failure | Store entry without embedding, mark for retry |
| Database Error | Rollback transaction, log error, raise exception |
| Search with No Vectors | Fall back to keyword search |
| Empty Query | Return empty results |

### Graceful Degradation

1. **No Embedding Available**: System continues to work with keyword search
2. **Partial Vectorization**: Search uses available vectors, supplements with keyword matches
3. **API Unavailable**: New entries stored without vectors, background job retries later

## Testing Strategy

### Unit Tests

Unit tests verify specific examples and edge cases:

1. **EmbeddingService Tests**
   - Test configuration loading from env/config
   - Test single text embedding (mock API)
   - Test batch text embedding (mock API)
   - Test error handling for API failures
   - Test timeout handling

2. **PostKnowledge Model Tests**
   - Test vector serialization/deserialization
   - Test CRUD operations
   - Test query methods (get_all_with_embeddings, etc.)

3. **SimilarityCalculator Tests**
   - Test cosine similarity with known vectors
   - Test batch similarity calculation
   - Test edge cases (zero vectors, identical vectors)

4. **KnowledgeService Tests**
   - Test add_post_to_knowledge with vectorization
   - Test search_similar_knowledge
   - Test fallback to keyword search
   - Test bulk re-vectorization

### Property-Based Tests

Property-based tests verify universal properties across many generated inputs:

1. **Vector Round-Trip Property**
   - Generate random vectors
   - Serialize and deserialize
   - Verify numerical equivalence

2. **Cosine Similarity Properties**
   - Generate random vector pairs
   - Verify similarity in [-1, 1]
   - Verify identical vectors have similarity 1.0
   - Verify symmetry: sim(a,b) == sim(b,a)

3. **Search Result Ordering Property**
   - Generate random query and candidate vectors
   - Verify results sorted by descending similarity
   - Verify threshold filtering

4. **Statistics Consistency Property**
   - Generate random knowledge base state
   - Verify count invariants

### Testing Framework

- **Unit Tests**: pytest with pytest-mock for mocking
- **Property Tests**: hypothesis for property-based testing
- **Minimum Iterations**: 100 per property test
- **Test Annotation Format**: `# Feature: vector-knowledge-base, Property N: description`

### Integration Tests

1. End-to-end test: Create post → Verify knowledge entry with embedding
2. Search integration: Add multiple posts → Search → Verify relevant results
3. Forum assistant integration: Send message → Verify knowledge context used
