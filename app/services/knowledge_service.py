"""
知识库服务
处理帖子内容的向量化和知识库管理
"""
import threading
import logging
from typing import Optional, List, Tuple
from flask import current_app

from app.services.embedding_service import get_embedding_service, embed_text
from app.utils.similarity import SimilarityCalculator


logger = logging.getLogger(__name__)


def process_post_knowledge(app, post_id, title, content, board_name, author_name):
    """
    处理帖子知识入库（在后台线程中运行）
    包含向量化处理

    Args:
        app: Flask应用实例
        post_id: 帖子ID
        title: 帖子标题
        content: 帖子内容
        board_name: 版块名称
        author_name: 作者名称
    """
    with app.app_context():
        from app.models.post_knowledge import PostKnowledge

        try:
            # 检查是否已存在
            existing = PostKnowledge.find_by_post_id(post_id)
            if existing:
                return

            # 组合标题和内容进行向量化
            text_for_embedding = f"{title}\n{content}"
            embedding = None
            
            try:
                embedding = embed_text(text_for_embedding)
                if embedding:
                    logger.info(f'Generated embedding for post {post_id}')
                else:
                    logger.warning(f'Failed to generate embedding for post {post_id}, will retry later')
            except Exception as e:
                logger.error(f'Error generating embedding for post {post_id}: {e}')

            # 创建知识条目
            PostKnowledge.create(
                post_id=post_id,
                title=title,
                content=content,
                board_name=board_name,
                author_name=author_name,
                embedding=embedding
            )

            logger.info(f'Post knowledge created for post {post_id}')

        except Exception as e:
            logger.error(f'Error processing post knowledge for post {post_id}: {e}')


def add_post_to_knowledge_async(post_id, title, content, board_name, author_name):
    """
    异步添加帖子到知识库（包含向量化）

    Args:
        post_id: 帖子ID
        title: 帖子标题
        content: 帖子内容
        board_name: 版块名称
        author_name: 作者名称
    """
    from flask import current_app
    app = current_app._get_current_object()

    thread = threading.Thread(
        target=process_post_knowledge,
        args=(app, post_id, title, content, board_name, author_name)
    )
    thread.daemon = True
    thread.start()


def add_post_to_knowledge_sync(post_id, title, content, board_name, author_name) -> Optional[dict]:
    """
    同步添加帖子到知识库（包含向量化，用于手动添加）

    Args:
        post_id: 帖子ID
        title: 帖子标题
        content: 帖子内容
        board_name: 版块名称
        author_name: 作者名称

    Returns:
        dict: 包含添加结果的字典，如果已存在返回None
    """
    from app.models.post_knowledge import PostKnowledge

    # 检查是否已存在
    existing = PostKnowledge.find_by_post_id(post_id)
    if existing:
        return None

    # 组合标题和内容进行向量化
    text_for_embedding = f"{title}\n{content}"
    embedding = None
    has_embedding = False

    try:
        embedding = embed_text(text_for_embedding)
        has_embedding = embedding is not None
        if has_embedding:
            logger.info(f'Generated embedding for post {post_id}')
    except Exception as e:
        logger.error(f'Failed to generate embedding for post {post_id}: {e}')

    # 创建知识条目
    knowledge = PostKnowledge.create(
        post_id=post_id,
        title=title,
        content=content,
        board_name=board_name,
        author_name=author_name,
        embedding=embedding
    )

    logger.info(f'Post knowledge created for post {post_id}')

    return {
        'id': knowledge.id,
        'has_embedding': has_embedding,
    }


def search_similar_knowledge(
    query: str, 
    limit: int = 5, 
    threshold: float = 0.5
) -> List[Tuple['PostKnowledge', float]]:
    """
    向量相似度搜索（包含帖子知识和自定义知识）
    
    Args:
        query: 搜索查询
        limit: 返回数量
        threshold: 相似度阈值
        
    Returns:
        [(Knowledge, similarity_score), ...] 按相似度降序
    """
    from app.models.post_knowledge import PostKnowledge
    from app.models.custom_knowledge import CustomKnowledge
    
    if not query or not query.strip():
        return []
    
    # 向量化查询
    query_embedding = embed_text(query)
    if not query_embedding:
        logger.warning("Failed to embed query, falling back to keyword search")
        return []
    
    # 获取所有有向量的条目（帖子知识 + 自定义知识）
    post_entries = PostKnowledge.get_all_with_embeddings()
    custom_entries = CustomKnowledge.get_all_active_with_embeddings()
    
    if not post_entries and not custom_entries:
        return []
    
    # 构建候选列表
    candidates = []
    for entry in post_entries:
        vec = entry.get_embedding_vector()
        if vec:
            candidates.append((entry, vec))
    
    for entry in custom_entries:
        vec = entry.get_embedding_vector()
        if vec:
            candidates.append((entry, vec))
    
    if not candidates:
        return []
    
    # 使用相似度计算器找出最相似的条目
    results = SimilarityCalculator.find_top_similar(
        query_vec=query_embedding,
        candidates=candidates,
        top_k=limit,
        threshold=threshold
    )
    
    return results


def get_relevant_knowledge(query: str, limit: int = None, threshold: float = None, 
                           max_context_chars: int = None) -> str:
    """
    获取与查询语义相关的知识（向量检索）

    Args:
        query: 搜索查询
        limit: 返回数量限制（默认从配置读取）
        threshold: 相似度阈值（0-1，默认从配置读取）
        max_context_chars: 最大上下文字符数（默认从配置读取）

    Returns:
        格式化的知识上下文字符串
    """
    from app.models.post_knowledge import PostKnowledge
    from app.services.embedding_service import get_knowledge_config
    import time
    
    start_time = time.time()
    
    # 从配置读取默认值
    config = get_knowledge_config()
    if limit is None:
        limit = config.get('search_limit', 5)
    if threshold is None:
        threshold = config.get('similarity_threshold', 0.5)
    if max_context_chars is None:
        max_context_chars = config.get('max_context_chars', 8000)
    
    logger.info(f"Knowledge search: query='{query[:50]}...', limit={limit}, threshold={threshold}")

    # 首先尝试向量搜索（带超时保护）
    results = []
    try:
        results = search_similar_knowledge(query, limit=limit, threshold=threshold)
        elapsed = time.time() - start_time
        logger.info(f"Vector search completed in {elapsed:.2f}s, found {len(results)} results")
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Vector search failed after {elapsed:.2f}s: {e}")
    
    if results:
        # 有向量搜索结果，按相似度顺序添加，直到达到字符限制
        logger.info(f"Vector search found {len(results)} results")
        context_parts = []
        current_length = 0
        
        for knowledge, score in results:
            # 兼容 PostKnowledge 和 CustomKnowledge
            entry_id = getattr(knowledge, 'post_id', None) or knowledge.id
            logger.debug(f"  - Entry {entry_id}: score={score:.4f}, title={knowledge.title[:30]}")
            context = knowledge.to_context()
            if current_length + len(context) <= max_context_chars:
                context_parts.append(context)
                current_length += len(context) + 2  # +2 for '\n\n' separator
            else:
                # 如果添加这个会超出限制，尝试截断内容
                remaining = max_context_chars - current_length
                if remaining > 200:  # 至少保留200字符才值得添加
                    truncated = context[:remaining - 3] + '...'
                    context_parts.append(truncated)
                break
        
        return '\n\n'.join(context_parts)
    
    logger.info("Vector search returned no results, falling back to keyword search")
    
    # 回退到关键词搜索
    keyword_results = PostKnowledge.search(query, limit=limit)
    
    if keyword_results:
        logger.info(f"Keyword search found {len(keyword_results)} results")
        context_parts = []
        current_length = 0
        
        for knowledge in keyword_results:
            context = knowledge.to_context()
            if current_length + len(context) <= max_context_chars:
                context_parts.append(context)
                current_length += len(context) + 2
            else:
                remaining = max_context_chars - current_length
                if remaining > 200:
                    truncated = context[:remaining - 3] + '...'
                    context_parts.append(truncated)
                break
        
        return '\n\n'.join(context_parts)
    
    logger.info("Keyword search returned no results, using optimized knowledge")
    
    # 如果都没有结果，使用优化后的知识库
    all_knowledge = PostKnowledge.get_optimized_knowledge(time_limit=50, like_limit=10)
    if all_knowledge:
        import random
        selected = random.sample(all_knowledge, min(3, len(all_knowledge)))
        context_parts = []
        current_length = 0
        
        for knowledge in selected:
            context = knowledge.to_context()
            if current_length + len(context) <= max_context_chars:
                context_parts.append(context)
                current_length += len(context) + 2
            else:
                break
        
        return '\n\n'.join(context_parts)

    return ''


def update_post_knowledge(post_id, title, content):
    """
    更新帖子知识（同步，包含重新向量化）

    Args:
        post_id: 帖子ID
        title: 帖子标题
        content: 帖子内容
    """
    from app.models.post_knowledge import PostKnowledge
    from app.extensions import db

    knowledge = PostKnowledge.find_by_post_id(post_id)
    if not knowledge:
        return

    knowledge.title = title
    knowledge.content = content

    # 重新向量化
    text_for_embedding = f"{title}\n{content}"
    try:
        embedding = embed_text(text_for_embedding)
        knowledge.set_embedding_vector(embedding)
        if embedding:
            logger.info(f'Updated embedding for post {post_id}')
    except Exception as e:
        logger.error(f'Failed to update embedding for post {post_id}: {e}')

    db.session.commit()


def delete_post_knowledge(post_id):
    """
    删除帖子知识

    Args:
        post_id: 帖子ID
    """
    from app.models.post_knowledge import PostKnowledge
    from app.extensions import db

    knowledge = PostKnowledge.find_by_post_id(post_id)
    if knowledge:
        db.session.delete(knowledge)
        db.session.commit()


def revectorize_entry(post_id: int) -> bool:
    """
    重新向量化指定条目
    
    Args:
        post_id: 帖子ID
        
    Returns:
        是否成功
    """
    from app.models.post_knowledge import PostKnowledge
    from app.extensions import db
    
    knowledge = PostKnowledge.find_by_post_id(post_id)
    if not knowledge:
        return False
    
    text_for_embedding = f"{knowledge.title}\n{knowledge.content}"
    try:
        embedding = embed_text(text_for_embedding)
        knowledge.set_embedding_vector(embedding)
        db.session.commit()
        
        if embedding:
            logger.info(f'Revectorized post {post_id}')
            return True
        else:
            logger.warning(f'Failed to revectorize post {post_id}')
            return False
    except Exception as e:
        logger.error(f'Error revectorizing post {post_id}: {e}')
        db.session.rollback()
        return False


def bulk_revectorize(batch_size: int = 50) -> dict:
    """
    批量重新向量化所有条目
    
    Args:
        batch_size: 每批处理数量
        
    Returns:
        包含处理结果的字典
    """
    from app.models.post_knowledge import PostKnowledge
    from app.services.embedding_service import get_embedding_service
    from app.extensions import db
    
    # 获取所有条目
    all_entries = PostKnowledge.query.all()
    total = len(all_entries)
    success_count = 0
    failed_count = 0
    
    embedding_service = get_embedding_service()
    
    # 分批处理
    for i in range(0, total, batch_size):
        batch = all_entries[i:i + batch_size]
        
        # 准备批量向量化的文本
        texts = [f"{entry.title}\n{entry.content}" for entry in batch]
        
        try:
            embeddings = embedding_service.embed_texts(texts)
            
            for entry, embedding in zip(batch, embeddings):
                if embedding:
                    entry.set_embedding_vector(embedding)
                    success_count += 1
                else:
                    failed_count += 1
            
            db.session.commit()
            logger.info(f'Batch {i // batch_size + 1}: processed {len(batch)} entries')
            
        except Exception as e:
            logger.error(f'Error in batch {i // batch_size + 1}: {e}')
            db.session.rollback()
            failed_count += len(batch)
    
    return {
        'total': total,
        'success': success_count,
        'failed': failed_count,
    }


def get_knowledge_stats() -> dict:
    """
    获取知识库统计信息
    
    Returns:
        包含统计信息的字典
    """
    from app.models.post_knowledge import PostKnowledge
    return PostKnowledge.get_stats()


def list_knowledge_entries(page: int = 1, per_page: int = 20, 
                           has_embedding: bool = None) -> Tuple[List['PostKnowledge'], int]:
    """
    列出知识库条目（分页）
    
    Args:
        page: 页码
        per_page: 每页数量
        has_embedding: 是否有向量（None表示全部）
        
    Returns:
        (条目列表, 总数)
    """
    from app.models.post_knowledge import PostKnowledge
    
    query = PostKnowledge.query
    
    if has_embedding is True:
        query = query.filter(
            PostKnowledge.embedding.isnot(None),
            PostKnowledge.embedding != ''
        )
    elif has_embedding is False:
        from app.extensions import db
        query = query.filter(
            db.or_(
                PostKnowledge.embedding.is_(None),
                PostKnowledge.embedding == ''
            )
        )
    
    total = query.count()
    entries = query.order_by(PostKnowledge.created_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    
    return entries, total
