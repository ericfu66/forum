"""
主页路由控制器
"""
from flask import Blueprint, render_template, request, url_for
from app.models.board import Board
from app.models.post import Post

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
                          recent_posts=[p.to_dict(include_author=True, include_board=True) for p in recent_posts])


@main_bp.route('/search')
def search():
    """搜索页面"""
    query = request.args.get('q', '')
    page = int(request.args.get('page', 1))
    per_page = 20

    results = []
    total = 0

    if query:
        # 帖子搜索
        search_query = f'%{query}%'
        posts_query = Post.query.filter(
            Post.status == 'published'
        ).filter(
            (Post.title.like(search_query)) | (Post.content.like(search_query))
        )

        total = posts_query.count()
        posts = posts_query.order_by(Post.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

        results = [p.to_dict(include_author=True, include_board=True) for p in posts]

    return render_template('main/search.html',
                          query=query,
                          results=results,
                          page=page,
                          total=total)
