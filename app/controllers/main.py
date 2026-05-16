"""
主页路由控制器
"""
import logging
from datetime import datetime
from flask import Blueprint, render_template, request, url_for
from app.models.board import Board
from app.models.post import Post

logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """首页 - 显示所有版块和最新帖子"""
    boards = Board.find_all(active_only=True)

    # 获取置顶帖子
    pinned_posts = Post.query.filter_by(is_pinned=True, status='published').all()

    # 获取最新帖子（跨版块）
    recent_posts = Post.query.filter_by(is_pinned=False, status='published')\
        .order_by(Post.created_at.desc()).limit(20).all()

    return render_template('main/index.html',
                          boards=[b.to_dict() for b in boards],
                          pinned_posts=[p.to_dict(include_author=True, include_board=True) for p in pinned_posts],
                          recent_posts=[p.to_dict(include_author=True, include_board=True) for p in recent_posts],
                          now=datetime.now())


@main_bp.route('/search')
def search():
    """搜索页面 - 支持语义搜索和关键词搜索"""
    query = request.args.get('q', '').strip()
    page = int(request.args.get('page', 1))
    per_page = 20
    mode = request.args.get('mode', 'semantic')  # semantic | keyword

    results = []
    total = 0
    search_mode_used = mode

    if query:
        if mode == 'semantic':
            results, total, search_mode_used = _semantic_search(query, page, per_page)
        if search_mode_used == 'keyword' or (mode == 'semantic' and total == 0):
            # 关键词搜索作为兜底
            results, total = _keyword_search(query, page, per_page)
            search_mode_used = 'keyword'

    return render_template('main/search.html',
                          query=query,
                          results=results,
                          page=page,
                          total=total,
                          mode=search_mode_used)


def _semantic_search(query, page, per_page):
    """语义搜索 - 使用向量相似度"""
    try:
        from app.services.embedding_service import embed_text
        from app.services.knowledge_service import search_similar_posts

        query_embedding = embed_text(query)
        if not query_embedding:
            return [], 0, 'keyword'

        # 语义搜索获取更多结果，然后分页
        limit = page * per_page
        similar = search_similar_posts(query_embedding, limit=limit, threshold=0.3)

        if not similar:
            return [], 0, 'keyword'

        # 分页切片
        start = (page - 1) * per_page
        page_items = similar[start:start + per_page]

        results = []
        for post, score in page_items:
            d = post.to_dict(include_author=True, include_board=True)
            d['similarity_score'] = round(score, 3)
            results.append(d)

        return results, len(similar), 'semantic'
    except Exception as e:
        logger.warning(f'Semantic search failed, falling back to keyword: {e}')
        return [], 0, 'keyword'


def _keyword_search(query, page, per_page):
    """关键词搜索 - SQL LIKE"""
    search_query = f'%{query}%'
    posts_query = Post.query.filter(
        Post.status == 'published'
    ).filter(
        (Post.title.like(search_query)) | (Post.content.like(search_query))
    )

    total = posts_query.count()
    posts = posts_query.order_by(Post.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

    results = [p.to_dict(include_author=True, include_board=True) for p in posts]
    return results, total
