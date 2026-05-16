"""
AI功能路由控制器
处理AI对话、AI写稿、AI吐槽等功能
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response, stream_with_context, current_app
from flask_login import login_required, current_user
from app.services.ai_service import get_ai_service
from app.services.ai_factory import AIServiceFactory
from app.services.knowledge_service import get_relevant_knowledge, add_post_to_knowledge_sync
from app.models.ai_dialog import AIDialog
from app.models.post import Post
from app.models.comment import Comment
from app.models.board import Board
from app.models.ai_daily import AIDailyContent
from app.utils.ai_trigger import trigger_ai_roast_manual
from app.extensions import db
import time
import random
from datetime import datetime, date

ai_bp = Blueprint('ai', __name__)


# ============ AI对话功能 ============

@ai_bp.route('/chat')
@login_required
def chat():
    """AI对话页面"""
    # 获取用户的对话列表
    dialogs, _ = AIDialog.find_by_user(current_user.id, page=1, per_page=20)

    return render_template('ai/chat.html',
                          dialogs=[d.to_dict() for d in dialogs])


@ai_bp.route('/api/dialogs', methods=['POST'])
@login_required
def create_dialog():
    """创建新对话"""
    title = request.json.get('title', '新对话')

    dialog = AIDialog.create(
        user_id=current_user.id,
        title=title
    )

    return jsonify({'success': True, 'dialog': dialog.to_dict()})


@ai_bp.route('/api/dialogs/<int:dialog_id>', methods=['GET'])
@login_required
def get_dialog(dialog_id):
    """获取对话详情"""
    dialog = AIDialog.query.get(dialog_id)

    if not dialog or dialog.user_id != current_user.id:
        return jsonify({'success': False, 'message': '对话不存在'}), 404

    return jsonify({'success': True, 'dialog': dialog.to_dict()})


@ai_bp.route('/api/dialogs', methods=['GET'])
@login_required
def list_dialogs():
    """获取对话列表"""
    page = int(request.args.get('page', 1))
    dialogs, total = AIDialog.find_by_user(current_user.id, page=page, per_page=20)

    return jsonify({
        'success': True,
        'dialogs': [d.to_dict() for d in dialogs],
        'total': total
    })


@ai_bp.route('/api/dialogs/<int:dialog_id>/message', methods=['POST'])
@login_required
def send_message(dialog_id):
    """发送消息（流式响应，支持图片理解、联网搜索和表情包生成）"""
    from app.models.custom_assistant import CustomAssistant
    from app.services.vision_service import get_vision_service
    import re
    
    dialog = AIDialog.query.get(dialog_id)

    if not dialog or dialog.user_id != current_user.id:
        return jsonify({'success': False, 'message': '对话不存在'}), 404

    user_message = request.json.get('message', '').strip()
    system_prompt = request.json.get('system_prompt', '').strip()
    assistant_id = request.json.get('assistant_id')  # 自定义助手ID
    use_knowledge = request.json.get('use_knowledge', True)  # 默认启用知识库
    use_search = request.json.get('use_search', False)  # 是否启用联网搜索
    images = request.json.get('images', [])  # 图片列表（URL或base64）
    regenerate = request.json.get('regenerate', False)  # 是否为重新生成
    enable_sticker = request.json.get('use_sticker', False)  # 是否启用表情包功能（默认关闭）
    
    if not user_message:
        return jsonify({'success': False, 'message': '消息不能为空'}), 400

    # 如果指定了自定义助手，使用其system_prompt
    if assistant_id:
        assistant = CustomAssistant.find_by_id(assistant_id)
        if assistant and assistant.user_id == current_user.id and assistant.is_active:
            system_prompt = assistant.system_prompt

    # 表情包功能提示（添加到系统提示中）
    sticker_hint = ''
    if enable_sticker:
        sticker_hint = '''

【表情包功能】
你可以在回复中使用表情包来增加趣味性。当你想表达某种情绪或反应时，可以使用以下格式：
[sticker:表情描述]

例如：
- [sticker:开心的小猫咪]
- [sticker:惊讶的表情]
- [sticker:竖起大拇指点赞]

注意：
1. 表情包描述应简短（10-30字），描述你想要的表情或场景
2. 每条回复最多使用1-2个表情包，不要过度使用
3. 只在适合的场景使用，如表达情绪、庆祝、鼓励等
4. 表情包会被自动生成为可爱的卡通风格图片
'''

    # 检查速率限制 - 使用chat模块配置
    ai_service = get_ai_service('chat')
    allowed, message = ai_service.check_rate_limit(str(current_user.id))
    if not allowed:
        return jsonify({'success': False, 'message': message}), 429

    # 如果有图片，先进行视觉理解
    vision_context = ''
    if images and len(images) > 0:
        # 验证图片数量
        if len(images) > 4:
            return jsonify({'success': False, 'message': '最多支持4张图片'}), 400
        
        vision_service = get_vision_service()
        vision_result = vision_service.understand_multiple_images(
            images=images,
            prompt=f'请详细描述这些图片的内容，以便我能够回答用户的问题：{user_message}',
            detail='high'
        )
        
        if vision_result.success:
            vision_context = f'\n\n[图片理解结果]\n{vision_result.content}\n[图片理解结束]\n\n'
        else:
            # 视觉理解失败，但继续对话
            vision_context = f'\n\n[图片理解失败: {vision_result.message}]\n\n'

    # 如果是重新生成，删除最后一条AI消息
    if regenerate:
        dialog.remove_last_assistant_message()
    else:
        # 添加用户消息（包含图片标记）
        message_content = user_message
        if images:
            message_content = f'[用户上传了{len(images)}张图片]\n{user_message}'
        dialog.add_message('user', message_content)

    # 获取相关知识上下文
    knowledge_context = ''
    if use_knowledge:
        knowledge_context = get_relevant_knowledge(user_message)  # 使用配置文件中的默认参数

    # 合并上下文
    combined_context = ''
    if vision_context:
        combined_context += vision_context
    if knowledge_context:
        combined_context += knowledge_context

    # 合并系统提示（添加表情包功能提示）
    final_system_prompt = system_prompt if system_prompt else ''
    if sticker_hint:
        final_system_prompt = final_system_prompt + sticker_hint if final_system_prompt else sticker_hint.strip()

    # 生成流式响应函数
    def generate():
        try:
            start_time = time.time()
            full_response = ''

            # 如果启用搜索，使用支持Function Calling的方法
            if use_search:
                for chunk in ai_service.chat_with_tools(
                    user_message=user_message,
                    dialog_history=dialog.get_messages_for_api()[:-1],
                    system_prompt=final_system_prompt if final_system_prompt else None,
                    enable_search=True,
                    knowledge_context=combined_context
                ):
                    full_response += chunk
                    escaped_chunk = chunk.replace('\n', '\\n')
                    yield f"data: {escaped_chunk}\n\n"
            # 如果有上下文（视觉或知识库），使用增强对话
            elif combined_context:
                for chunk in ai_service.chat_with_knowledge(
                    user_message=user_message,
                    knowledge_context=combined_context,
                    dialog_history=dialog.get_messages_for_api()[:-1],  # 排除刚添加的用户消息
                    system_prompt=final_system_prompt if final_system_prompt else None
                ):
                    full_response += chunk
                    # 转义换行符，避免SSE解析问题
                    escaped_chunk = chunk.replace('\n', '\\n')
                    yield f"data: {escaped_chunk}\n\n"
            else:
                for chunk in ai_service.chat_stream(
                    dialog_history=dialog.get_messages_for_api(),
                    user_message=user_message,
                    system_prompt=final_system_prompt
                ):
                    full_response += chunk
                    # 转义换行符，避免SSE解析问题
                    escaped_chunk = chunk.replace('\n', '\\n')
                    yield f"data: {escaped_chunk}\n\n"

            # 处理表情包标记 - 在响应完成后生成表情包
            if enable_sticker:
                sticker_pattern = r'\[sticker:([^\]]+)\]'
                sticker_matches = re.findall(sticker_pattern, full_response)
                
                if sticker_matches:
                    from app.services.image_service import generate_sticker
                    
                    for sticker_desc in sticker_matches[:2]:  # 最多处理2个表情包
                        try:
                            success, sticker_url, error = generate_sticker(sticker_desc.strip(), current_user.id)
                            if success and sticker_url:
                                # 发送表情包URL给前端
                                sticker_data = f'[STICKER_URL:{sticker_url}]'
                                yield f"data: {sticker_data}\n\n"
                        except Exception as e:
                            current_app.logger.warning(f'Failed to generate sticker: {e}')

            # 添加AI回复到对话历史
            dialog.add_message('assistant', full_response)

            # 触发对话摘要（如果消息数超过阈值）
            try:
                if len(dialog.messages or []) > current_app.config.get('DIALOG_SUMMARY_THRESHOLD', 30):
                    dialog.summarize_dialog()
            except Exception as e:
                current_app.logger.warning(f'Dialog summarization failed: {e}')

            # 记录API调用
            response_time = (time.time() - start_time) * 1000
            # ai_service.log_api_call(...)  # 简化

            # 发送结束标记
            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: 错误: {str(e)}\n\n"
            yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


@ai_bp.route('/api/tags/suggest', methods=['POST'])
@login_required
def suggest_tags():
    """AI标签推荐"""
    title = request.json.get('title', '').strip()
    content = request.json.get('content', '').strip()

    if not title and not content:
        return jsonify({'success': False, 'message': '请输入标题或内容'}), 400

    from app.services.tag_service import generate_tags_ai
    tags = generate_tags_ai(title, content)

    return jsonify({'success': True, 'tags': tags})


@ai_bp.route('/api/dialogs/<int:dialog_id>/delete', methods=['POST'])
@login_required
def delete_dialog(dialog_id):
    """删除对话"""
    dialog = AIDialog.query.get(dialog_id)

    if not dialog or dialog.user_id != current_user.id:
        return jsonify({'success': False, 'message': '对话不存在'}), 404

    db.session.delete(dialog)
    db.session.commit()

    return jsonify({'success': True, 'message': '对话已删除'})


# ============ AI写稿功能 ============

@ai_bp.route('/write')
@login_required
def write():
    """AI写稿页面"""
    boards = Board.find_all(active_only=True)
    return render_template('ai/write.html', boards=[b.to_dict() for b in boards])


@ai_bp.route('/api/write/generate', methods=['POST'])
@login_required
def generate_article():
    """生成文章（非流式）"""
    from app.services.ai_service import validate_word_count
    
    topic = request.json.get('topic', '').strip()
    keywords = request.json.get('keywords', [])
    length = request.json.get('length', 'medium')
    style = request.json.get('style')  # 写作风格
    tone = request.json.get('tone')    # 写作语气
    word_count = request.json.get('word_count')  # 精确字数
    preset = request.json.get('preset')  # 写作类型预设
    fun_style = request.json.get('fun_style')  # 整活风格
    custom_prompt = request.json.get('custom_prompt')  # 自定义提示词

    if not topic:
        return jsonify({'success': False, 'message': '请输入写作要求'}), 400

    # 验证字数参数
    if word_count is not None:
        valid, msg = validate_word_count(word_count)
        if not valid:
            return jsonify({'success': False, 'message': msg}), 400
        word_count = int(word_count)

    # 检查速率限制 - 使用write模块配置
    ai_service = get_ai_service('write')
    allowed, message = ai_service.check_rate_limit(str(current_user.id))
    if not allowed:
        return jsonify({'success': False, 'message': message}), 429

    # 生成文章
    try:
        start_time = time.time()
        content = ai_service.generate_article(
            topic, keywords, length,
            style=style, tone=tone, word_count=word_count,
            preset=preset, fun_style=fun_style, custom_prompt=custom_prompt
        )
        
        # 生成标题
        title = ai_service.generate_title(content, topic)
        
        response_time = (time.time() - start_time) * 1000

        return jsonify({
            'success': True,
            'content': content,
            'title': title
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'生成失败: {str(e)}'
        }), 500


@ai_bp.route('/api/write/generate/stream', methods=['POST'])
@login_required
def generate_article_stream():
    """生成文章（流式响应）"""
    from app.services.ai_service import validate_word_count
    
    topic = request.json.get('topic', '').strip()
    keywords = request.json.get('keywords', [])
    length = request.json.get('length', 'medium')
    style = request.json.get('style')  # 写作风格
    tone = request.json.get('tone')    # 写作语气
    word_count = request.json.get('word_count')  # 精确字数
    preset = request.json.get('preset')  # 写作类型预设
    fun_style = request.json.get('fun_style')  # 整活风格
    custom_prompt = request.json.get('custom_prompt')  # 自定义提示词

    if not topic:
        return jsonify({'success': False, 'message': '请输入写作要求'}), 400

    # 验证字数参数
    if word_count is not None:
        valid, msg = validate_word_count(word_count)
        if not valid:
            return jsonify({'success': False, 'message': msg}), 400
        word_count = int(word_count)

    # 检查速率限制 - 使用write模块配置
    ai_service = get_ai_service('write')
    allowed, message = ai_service.check_rate_limit(str(current_user.id))
    if not allowed:
        return jsonify({'success': False, 'message': message}), 429

    # 生成流式响应
    def generate():
        try:
            full_content = ''
            for chunk in ai_service.generate_article_stream(
                topic, keywords, length,
                style=style, tone=tone, word_count=word_count,
                preset=preset, fun_style=fun_style, custom_prompt=custom_prompt
            ):
                full_content += chunk
                # SSE格式 - 转义换行符避免破坏SSE格式
                escaped_chunk = chunk.replace('\n', '\\n')
                yield f"data: {escaped_chunk}\n\n"
            
            # 文章生成完成后，生成标题
            try:
                title = ai_service.generate_title(full_content, topic)
                if title:
                    yield f"data: [TITLE]:{title}\n\n"
            except Exception as e:
                current_app.logger.error(f'Failed to generate title: {e}')
            
            # 发送结束标记
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: 错误: {str(e)}\n\n"
            yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


@ai_bp.route('/api/write/revise', methods=['POST'])
@login_required
def revise_article():
    """AI修改文章（流式响应）"""
    from app.services.ai_service import validate_word_count
    
    original_content = request.json.get('original_content', '').strip()
    revision_request = request.json.get('revision_request', '').strip()
    style = request.json.get('style')  # 写作风格
    tone = request.json.get('tone')    # 写作语气
    word_count = request.json.get('word_count')  # 精确字数

    if not original_content:
        return jsonify({'success': False, 'message': '原始内容不能为空'}), 400
    
    if not revision_request:
        return jsonify({'success': False, 'message': '请输入修改要求'}), 400

    # 验证字数参数
    if word_count is not None:
        valid, msg = validate_word_count(word_count)
        if not valid:
            return jsonify({'success': False, 'message': msg}), 400
        word_count = int(word_count)

    # 检查速率限制 - 使用write模块配置
    ai_service = get_ai_service('write')
    allowed, message = ai_service.check_rate_limit(str(current_user.id))
    if not allowed:
        return jsonify({'success': False, 'message': message}), 429

    # 生成流式响应
    def generate():
        try:
            for chunk in ai_service.revise_article_stream(
                original_content=original_content,
                revision_request=revision_request,
                style=style,
                tone=tone,
                word_count=word_count
            ):
                # SSE格式 - 转义换行符避免破坏SSE格式
                escaped_chunk = chunk.replace('\n', '\\n')
                yield f"data: {escaped_chunk}\n\n"
            # 发送结束标记
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: 错误: {str(e)}\n\n"
            yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


@ai_bp.route('/api/polish', methods=['POST'])
@login_required
def polish_content():
    """AI润色/改写文本（流式）"""
    content = request.json.get('content', '').strip()
    action = request.json.get('action', 'polish')

    if not content:
        return jsonify({'success': False, 'message': '内容不能为空'}), 400

    if action not in ('polish', 'expand', 'condense', 'restyle', 'correct'):
        return jsonify({'success': False, 'message': '不支持的操作类型'}), 400

    ai_service = get_ai_service('write')
    allowed, message = ai_service.check_rate_limit(str(current_user.id))
    if not allowed:
        return jsonify({'success': False, 'message': message}), 429

    def generate():
        try:
            for chunk in ai_service.polish_stream(content, action):
                escaped_chunk = chunk.replace('\n', '\\n')
                yield f"data: {escaped_chunk}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: 错误: {str(e)}\n\n"
            yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


@ai_bp.route('/api/write/save', methods=['POST'])
@login_required
def save_as_post():
    """将AI生成的文章保存为帖子"""
    title = request.json.get('title', '').strip()
    content = request.json.get('content', '').strip()
    board_id = request.json.get('board_id')

    if not title or not content or not board_id:
        return jsonify({'success': False, 'message': '请填写标题、内容并选择版块'}), 400

    # 创建帖子（标记为AI生成）
    post = Post.create(
        title=title,
        content=content,
        author_id=current_user.id,
        board_id=board_id,
        is_ai_generated=True
    )

    return jsonify({
        'success': True,
        'message': '保存成功',
        'post_id': post.id
    })


# ============ AI吐槽功能 ============

@ai_bp.route('/api/roast/trigger', methods=['POST'])
@login_required
def manual_roast():
    """手动触发AI吐槽"""
    post_id = request.json.get('post_id')

    if not post_id:
        return jsonify({'success': False, 'message': '帖子ID不能为空'}), 400

    # 检查速率限制 - 使用roast模块配置
    ai_service = get_ai_service('roast')
    allowed, message = ai_service.check_rate_limit(str(current_user.id))
    if not allowed:
        return jsonify({'success': False, 'message': message}), 429

    # 触发AI吐槽
    success = trigger_ai_roast_manual(post_id)

    if success:
        return jsonify({'success': True, 'message': 'AI吐槽已发送'})
    else:
        return jsonify({'success': False, 'message': '触发失败'}), 500


@ai_bp.route('/api/roast/probability', methods=['GET'])
@login_required
def get_roast_probability():
    """获取当前AI吐槽触发概率"""
    from flask import current_app

    probability = current_app.config.get('AI_ROAST_PROBABILITY', 0.1)

    return jsonify({
        'success': True,
        'probability': probability,
        'enabled': current_app.config.get('AI_ROAST_ENABLED', False)
    })


# ============ AI知识库管理 ============

@ai_bp.route('/api/knowledge/add', methods=['POST'])
@login_required
def add_to_knowledge():
    """手动将帖子添加到AI知识库"""
    post_id = request.json.get('post_id')

    if not post_id:
        return jsonify({'success': False, 'message': '帖子ID不能为空'}), 400

    post = Post.query.get(post_id)
    if not post:
        return jsonify({'success': False, 'message': '帖子不存在'}), 404

    # 检查权限（作者或管理员）
    if post.author_id != current_user.id and not current_user.is_admin():
        return jsonify({'success': False, 'message': '无权操作'}), 403

    # 获取版块信息
    board_name = post.board.name if post.board else None

    # 同步添加到知识库
    try:
        result = add_post_to_knowledge_sync(
            post_id=post.id,
            title=post.title,
            content=post.content,
            board_name=board_name,
            author_name=post.author.username
        )
        if result:
            return jsonify({
                'success': True, 
                'message': '已添加到AI知识库', 
                'has_embedding': result.get('has_embedding', False)
            })
        else:
            return jsonify({'success': False, 'message': '添加失败或已存在'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'添加失败: {str(e)}'}), 500


@ai_bp.route('/api/knowledge/check/<int:post_id>', methods=['GET'])
def check_knowledge(post_id):
    """检查帖子是否已在知识库中"""
    from app.models.post_knowledge import PostKnowledge
    knowledge = PostKnowledge.find_by_post_id(post_id)
    return jsonify({
        'success': True,
        'in_knowledge': knowledge is not None,
        'has_embedding': knowledge.embedding is not None if knowledge else False
    })


@ai_bp.route('/api/knowledge/stats', methods=['GET'])
@login_required
def get_knowledge_stats():
    """获取知识库统计信息"""
    from app.services.knowledge_service import get_knowledge_stats
    
    # 只有管理员可以查看统计
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': '无权访问'}), 403
    
    try:
        stats = get_knowledge_stats()
        return jsonify({'success': True, **stats})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取统计失败: {str(e)}'}), 500


@ai_bp.route('/api/knowledge/revectorize/<int:post_id>', methods=['POST'])
@login_required
def revectorize_knowledge(post_id):
    """重新向量化指定帖子的知识条目"""
    from app.services.knowledge_service import revectorize_entry
    
    # 只有管理员可以操作
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': '无权操作'}), 403
    
    try:
        success = revectorize_entry(post_id)
        if success:
            return jsonify({'success': True, 'message': '重新向量化成功'})
        else:
            return jsonify({'success': False, 'message': '重新向量化失败'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'操作失败: {str(e)}'}), 500


@ai_bp.route('/api/knowledge/bulk-revectorize', methods=['POST'])
@login_required
def bulk_revectorize_knowledge():
    """批量重新向量化所有知识条目"""
    from app.services.knowledge_service import bulk_revectorize
    
    # 只有管理员可以操作
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': '无权操作'}), 403
    
    batch_size = request.json.get('batch_size', 50) if request.json else 50
    
    try:
        result = bulk_revectorize(batch_size=batch_size)
        return jsonify({
            'success': True,
            'message': f'批量向量化完成',
            **result
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'操作失败: {str(e)}'}), 500


@ai_bp.route('/api/knowledge/<int:post_id>', methods=['DELETE'])
@login_required
def delete_post_knowledge_api(post_id):
    """单独删除帖子知识条目（不删除原帖）"""
    from app.services.knowledge_service import delete_post_knowledge
    
    # 只有管理员可以操作
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': '无权操作'}), 403
    
    try:
        delete_post_knowledge(post_id)
        return jsonify({'success': True, 'message': '知识条目已删除'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'}), 500


@ai_bp.route('/api/knowledge/list', methods=['GET'])
@login_required
def list_knowledge():
    """列举知识库内容（分页）"""
    from app.models.post_knowledge import PostKnowledge
    
    # 只有管理员可以查看
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': '无权访问'}), 403
    
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    has_embedding = request.args.get('has_embedding')  # 'true', 'false', or None
    
    # 构建查询
    query = PostKnowledge.query
    
    if has_embedding == 'true':
        query = query.filter(
            PostKnowledge.embedding.isnot(None),
            PostKnowledge.embedding != ''
        )
    elif has_embedding == 'false':
        query = query.filter(
            db.or_(
                PostKnowledge.embedding.is_(None),
                PostKnowledge.embedding == ''
            )
        )
    
    # 分页
    total = query.count()
    entries = query.order_by(PostKnowledge.created_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    
    return jsonify({
        'success': True,
        'entries': [e.to_dict() for e in entries],
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page
    })


@ai_bp.route('/api/knowledge/search-test', methods=['POST'])
@login_required
def test_knowledge_search():
    """测试知识库搜索（返回详细结果和相似度分数）"""
    from app.services.knowledge_service import search_similar_knowledge, get_relevant_knowledge
    from app.models.post_knowledge import PostKnowledge
    from app.services.embedding_service import get_knowledge_config
    
    # 只有管理员可以测试
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': '无权操作'}), 403
    
    data = request.json or {}
    query = data.get('query', '').strip()
    limit = int(data.get('limit', 5))
    threshold = float(data.get('threshold', 0.3))  # 测试时使用较低阈值
    
    if not query:
        return jsonify({'success': False, 'message': '查询内容不能为空'}), 400
    
    # 获取当前配置
    config = get_knowledge_config()
    
    # 执行向量搜索
    vector_results = []
    try:
        results = search_similar_knowledge(query, limit=limit, threshold=threshold)
        for knowledge, score in results:
            # 兼容 PostKnowledge 和 CustomKnowledge
            is_custom = hasattr(knowledge, 'source_type')
            vector_results.append({
                'id': knowledge.id,
                'post_id': getattr(knowledge, 'post_id', None),
                'title': knowledge.title,
                'content': knowledge.content[:200] + '...' if len(knowledge.content) > 200 else knowledge.content,
                'board_name': getattr(knowledge, 'board_name', None),
                'author_name': getattr(knowledge, 'author_name', None),
                'category': getattr(knowledge, 'category', None),
                'source_type': 'custom' if is_custom else 'post',
                'similarity_score': round(score, 4),
                'has_embedding': True
            })
    except Exception as e:
        return jsonify({
            'success': False, 
            'message': f'向量搜索失败: {str(e)}'
        }), 500
    
    # 执行关键词搜索（作为对比）
    keyword_results = []
    try:
        kw_entries = PostKnowledge.search(query, limit=limit)
        for knowledge in kw_entries:
            keyword_results.append({
                'id': knowledge.id,
                'post_id': knowledge.post_id,
                'title': knowledge.title,
                'content': knowledge.content[:200] + '...' if len(knowledge.content) > 200 else knowledge.content,
                'board_name': knowledge.board_name,
                'author_name': knowledge.author_name,
                'has_embedding': knowledge.embedding is not None
            })
    except Exception as e:
        keyword_results = []
    
    # 获取最终上下文（实际使用的结果）
    final_context = get_relevant_knowledge(query, limit=limit, threshold=threshold)
    
    return jsonify({
        'success': True,
        'query': query,
        'config': {
            'search_limit': config.get('search_limit'),
            'similarity_threshold': config.get('similarity_threshold'),
            'max_context_chars': config.get('max_context_chars'),
            'test_threshold': threshold
        },
        'vector_search': {
            'count': len(vector_results),
            'results': vector_results
        },
        'keyword_search': {
            'count': len(keyword_results),
            'results': keyword_results
        },
        'final_context': {
            'length': len(final_context),
            'preview': final_context[:500] + '...' if len(final_context) > 500 else final_context
        }
    })


# ============ 自定义知识库管理 ============

@ai_bp.route('/api/custom-knowledge/list', methods=['GET'])
@login_required
def list_custom_knowledge():
    """列举自定义知识库条目"""
    from app.models.custom_knowledge import CustomKnowledge
    
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': '无权访问'}), 403
    
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    category = request.args.get('category')
    
    query = CustomKnowledge.query.filter_by(is_active=True)
    if category:
        query = query.filter_by(category=category)
    
    total = query.count()
    entries = query.order_by(CustomKnowledge.created_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    
    return jsonify({
        'success': True,
        'entries': [e.to_dict() for e in entries],
        'total': total,
        'page': page,
        'per_page': per_page
    })


@ai_bp.route('/api/custom-knowledge/add', methods=['POST'])
@login_required
def add_custom_knowledge():
    """手动添加自定义知识"""
    from app.models.custom_knowledge import CustomKnowledge
    from app.services.embedding_service import embed_text
    
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': '无权操作'}), 403
    
    data = request.json or {}
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    category = data.get('category', '').strip()
    
    if not title or not content:
        return jsonify({'success': False, 'message': '标题和内容不能为空'}), 400
    
    # 向量化
    embedding = None
    try:
        text_for_embedding = f"{title}\n{content}"
        embedding = embed_text(text_for_embedding)
    except Exception as e:
        current_app.logger.error(f'Failed to embed custom knowledge: {e}')
    
    knowledge = CustomKnowledge.create(
        title=title,
        content=content,
        source_type='manual',
        category=category if category else None,
        created_by=current_user.id,
        embedding=embedding
    )
    
    return jsonify({
        'success': True,
        'message': '添加成功',
        'knowledge': knowledge.to_dict()
    })


@ai_bp.route('/api/custom-knowledge/upload', methods=['POST'])
@login_required
def upload_custom_knowledge():
    """上传文件到自定义知识库"""
    from app.models.custom_knowledge import CustomKnowledge
    from app.services.embedding_service import embed_text
    import os
    
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': '无权操作'}), 403
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '请选择文件'}), 400
    
    file = request.files['file']
    if not file.filename:
        return jsonify({'success': False, 'message': '请选择文件'}), 400
    
    # 检查文件类型
    allowed_extensions = {'txt', 'md', 'json'}
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in allowed_extensions:
        return jsonify({'success': False, 'message': f'不支持的文件类型，仅支持: {", ".join(allowed_extensions)}'}), 400
    
    # 读取文件内容
    try:
        content = file.read().decode('utf-8')
    except UnicodeDecodeError:
        return jsonify({'success': False, 'message': '文件编码错误，请使用UTF-8编码'}), 400
    
    if not content.strip():
        return jsonify({'success': False, 'message': '文件内容为空'}), 400
    
    # 限制文件大小（内容长度）
    max_content_length = 100000  # 约100KB文本
    if len(content) > max_content_length:
        return jsonify({'success': False, 'message': f'文件内容过大，最大支持{max_content_length}字符'}), 400
    
    title = request.form.get('title', '').strip() or file.filename
    category = request.form.get('category', '').strip()
    
    # 向量化
    embedding = None
    try:
        text_for_embedding = f"{title}\n{content}"
        embedding = embed_text(text_for_embedding)
    except Exception as e:
        current_app.logger.error(f'Failed to embed uploaded knowledge: {e}')
    
    knowledge = CustomKnowledge.create(
        title=title,
        content=content,
        source_type='file',
        source_name=file.filename,
        category=category if category else None,
        created_by=current_user.id,
        embedding=embedding
    )
    
    return jsonify({
        'success': True,
        'message': '上传成功',
        'knowledge': knowledge.to_dict()
    })


@ai_bp.route('/api/custom-knowledge/<int:knowledge_id>', methods=['DELETE'])
@login_required
def delete_custom_knowledge(knowledge_id):
    """删除自定义知识"""
    from app.models.custom_knowledge import CustomKnowledge
    
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': '无权操作'}), 403
    
    knowledge = CustomKnowledge.query.get(knowledge_id)
    if not knowledge:
        return jsonify({'success': False, 'message': '知识条目不存在'}), 404
    
    # 软删除
    knowledge.is_active = False
    db.session.commit()
    
    return jsonify({'success': True, 'message': '删除成功'})


@ai_bp.route('/api/custom-knowledge/<int:knowledge_id>/revectorize', methods=['POST'])
@login_required
def revectorize_custom_knowledge(knowledge_id):
    """重新向量化自定义知识"""
    from app.models.custom_knowledge import CustomKnowledge
    from app.services.embedding_service import embed_text
    
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': '无权操作'}), 403
    
    knowledge = CustomKnowledge.query.get(knowledge_id)
    if not knowledge:
        return jsonify({'success': False, 'message': '知识条目不存在'}), 404
    
    try:
        text_for_embedding = f"{knowledge.title}\n{knowledge.content}"
        embedding = embed_text(text_for_embedding)
        knowledge.set_embedding_vector(embedding)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '重新向量化成功',
            'has_embedding': embedding is not None
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'操作失败: {str(e)}'}), 500


@ai_bp.route('/api/custom-knowledge/stats', methods=['GET'])
@login_required
def get_custom_knowledge_stats():
    """获取自定义知识库统计"""
    from app.models.custom_knowledge import CustomKnowledge
    
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': '无权访问'}), 403
    
    stats = CustomKnowledge.get_stats()
    return jsonify({'success': True, **stats})


# ============ AI每日内容 ============

@ai_bp.route('/api/daily/quote', methods=['GET'])
def get_daily_quote():
    """获取每日论坛序言"""
    force_refresh = request.args.get('refresh', 'false') == 'true'

    # 尝试获取今日的序言
    today = date.today()
    daily = AIDailyContent.get_today('quote')

    if daily and not force_refresh:
        return jsonify({
            'success': True,
            'quote': daily.content,
            'generated_at': daily.created_at.isoformat()
        })

    # 生成新的序言 - 使用chat模块配置
    ai_service = get_ai_service('chat')

    prompts = [
        # 哲理风格
        "请生成一句富有哲理的每日序言，要求：不超过25字，关于求知与思考，直接输出不要引号",
        "写一句关于'知识海洋'的诗意短句，20字以内，直接输出",

        # 幽默轻松
        "用幽默的方式写一句关于学习的短句，不超过25字，轻松有趣，直接输出",
        "写一句自嘲风格的程序猿/技术人语录，25字以内，直接输出",

        # 励志向上
        "请写一句简洁有力的励志格言，不超过20字，直接输出",
        "写一句关于'突破自我'的鼓舞话语，20字以内，直接输出",

        # 好奇心与探索
        "用一句话激发好奇心，关于未知与探索，25字以内，直接输出",
        "写一句关于'提问的价值'的短句，20字以内，直接输出",

        # 思考与智慧
        "请写一句引人深思的智慧语录，关于思维与洞察，25字以内，直接输出",
        "写一句关于'多元视角'的思考性短句，20字以内，直接输出",

        # 创意与创新
        "请写一句关于'跳出思维框架'的创新语录，25字以内，直接输出",
        "写一句关于'灵感降临'的诗意描述，20字以内，直接输出",

        # 社区与连接
        "写一句关于'思想碰撞产生火花'的社区感短句，25字以内，直接输出",
        "请写一句关于'陌生人之间的智慧传递'的温暖话语，25字以内，直接输出",

        # 成长与变化
        "写一句关于'错误是成长的阶梯'的鼓励性短句，25字以内，直接输出",
        "请写一句关于'每天进步一点点'的朴实话语，20字以内，直接输出",

        # 极简风格
        "请写一句4-8字的极简箴言，有力而深刻，直接输出",
        "写一句5-10字的短小格言，意味深长，直接输出",

        # 提问式
        "用一个引人思考的问题作为今日序言，20字以内，直接输出",
        "用一个反问句激发思考，关于知识与认知，25字以内，直接输出",

        # 比喻式
        "用一个生动的比喻描述学习过程，25字以内，直接输出",
        "写一句用自然现象比喻思维的短句，20字以内，直接输出",

        # 古典/文艺风格
        "请写一句古风或文艺气息的箴言，关于求知，25字以内，直接输出",
        "用'山、海、星、月'等意象写一句诗意短句，20字以内，直接输出",

        # 现代风格
        "写一句现代感十足的白话箴言，轻松有力，20字以内，直接输出",
        "请用网络流行语风格写一句励志短句，25字以内，直接输出",
    ]

    try:
        quote = ai_service.generate_simple(random.choice(prompts))
        quote = quote.strip().strip('"\'""''')

        # 保存到数据库
        if daily:
            daily.content = quote
            daily.created_at = datetime.utcnow()
            db.session.commit()
        else:
            AIDailyContent.create('quote', quote)

        return jsonify({
            'success': True,
            'quote': quote,
            'generated_at': datetime.utcnow().isoformat()
        })
    except Exception as e:
        # 返回默认序言
        default_quotes = [
            "探索未知，分享所得，共同成长",
            "每一次讨论，都是思想的碰撞与升华",
            "知识因分享而更加珍贵",
            "今天的疑问，是明天的答案",
            "在交流中学习，在分享中进步"
        ]
        return jsonify({
            'success': True,
            'quote': random.choice(default_quotes),
            'generated_at': datetime.utcnow().isoformat(),
            'is_default': True
        })


@ai_bp.route('/api/daily/fortune', methods=['GET'])
def get_daily_fortune():
    """获取今日运势/幸运指数"""
    if not current_user.is_authenticated:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    force_refresh = request.args.get('refresh', 'false') == 'true'
    user_key = f'fortune_{current_user.id}'

    # 尝试获取今日的运势
    daily = AIDailyContent.get_today(user_key)

    if daily and not force_refresh:
        import json
        data = json.loads(daily.content)
        return jsonify({'success': True, **data})

    # 生成新的运势 - 使用chat模块配置
    ai_service = get_ai_service('chat')

    try:
        prompt = f'''为用户"{current_user.username}"生成今日论坛运势，以JSON格式返回：
{{
    "luck_score": 1-100的幸运值,
    "luck_level": "大吉/中吉/小吉/平/小凶"之一,
    "message": "一句20字以内的运势建议",
    "lucky_action": "今日宜做的事（如：发帖、回复、点赞）",
    "emoji": "一个代表运势的emoji"
}}
只返回JSON，不要其他内容'''

        result = ai_service.generate_simple(prompt)
        # 尝试解析JSON
        import json
        # 清理可能的markdown代码块
        result = result.strip()
        if result.startswith('```'):
            parts = result.split('\n', 1)
            result = parts[1] if len(parts) > 1 else ''
        if result.endswith('```'):
            parts = result.rsplit('```', 1)
            result = parts[0] if len(parts) > 1 else result
        result = result.strip()

        data = json.loads(result)

        # 保存到数据库
        if daily:
            daily.content = json.dumps(data, ensure_ascii=False)
            daily.created_at = datetime.utcnow()
            db.session.commit()
        else:
            AIDailyContent.create(user_key, json.dumps(data, ensure_ascii=False))

        return jsonify({'success': True, **data})
    except Exception as e:
        # 返回随机默认运势 - 增加多样性
        # 根据分数确定等级
        luck_score = random.randint(50, 100)

        if luck_score >= 90:
            level_pool = ['大吉', '超级大吉', '运势爆棚']
        elif luck_score >= 80:
            level_pool = ['中吉', '吉', '顺遂']
        elif luck_score >= 70:
            level_pool = ['小吉', '平稳上升', '运势不错']
        elif luck_score >= 60:
            level_pool = ['平', '平平无奇', '普通']
        else:
            level_pool = ['小凶', '需要小心', '低开高走']

        # 多样化的消息
        messages = [
            '今天适合在论坛多交流！',
            '你的帖子可能会火哦',
            '是时候分享你的见解了',
            '保持好奇心，好运自然来',
            '今天适合学习新技能',
            '帮助他人就是帮助自己',
            '每一次讨论都是成长',
            '灵感就在身边，多观察',
            '坚持输出，收获满满',
            '与志同道合的人交流吧',
            '你的观点很有价值',
            '保持耐心，答案会浮现',
            '尝试不同的视角',
            '今日宜深度思考',
            '适合整理思路和总结',
            '好运藏在细节里',
            '大胆表达你的想法',
            '遇到问题多提问',
            '分享带来好运',
            '保持开放的心态',
            '今天可能有意外的收获',
            '专注于你想学的东西',
            '与社区互动，能量满满',
            '你的经验会帮助到别人',
            '相信直觉，勇敢尝试',
        ]

        # 多样化的幸运行动
        actions = [
            '发帖分享观点',
            '回复有趣的帖子',
            '给他人点赞鼓励',
            '学习一项新技能',
            '阅读热门讨论',
            '整理收藏的内容',
            '帮助新手解答问题',
            '发起一个话题',
            '深入研究某个领域',
            '写下今日总结',
            '探索新的版块',
            '与大佬交流请教',
            '分享你的项目经验',
            '参与话题讨论',
            '提出一个好问题',
            '浏览精华帖子',
            '关注有趣的人',
            '练习写作表达',
            '整理学习笔记',
            '发现新知识',
        ]

        # 多样化的emoji
        emojis = [
            '🌟', '✨', '🍀', '🎯', '💫',
            '🌈', '🔥', '💎', '🎪', '🎨',
            '🚀', '⭐', '🌸', '🎭', '🎲',
            '🔮', '💡', '🎵', '🌺', '🎁',
            '🏆', '🎊', '🌻', '🎹', '🎬',
        ]

        import json
        default_data = {
            'luck_score': luck_score,
            'luck_level': random.choice(level_pool),
            'message': random.choice(messages),
            'lucky_action': random.choice(actions),
            'emoji': random.choice(emojis)
        }

        # 保存默认运势到数据库（确保刷新时有缓存）
        if daily:
            daily.content = json.dumps(default_data, ensure_ascii=False)
            daily.created_at = datetime.utcnow()
            db.session.commit()
        else:
            AIDailyContent.create(user_key, json.dumps(default_data, ensure_ascii=False))

        return jsonify({'success': True, **default_data, 'is_default': True})


@ai_bp.route('/api/daily/prompt', methods=['GET'])
def get_writing_prompt():
    """获取AI写作灵感/话题建议"""
    force_refresh = request.args.get('refresh', 'false') == 'true'

    daily = AIDailyContent.get_today('writing_prompt')

    if daily and not force_refresh:
        import json
        data = json.loads(daily.content)
        return jsonify({'success': True, **data})

    # 使用chat模块配置
    ai_service = get_ai_service('chat')

    try:
        prompt = '''生成3个有趣的论坛话题建议，以JSON格式返回：
{
    "prompts": [
        {"title": "话题标题", "description": "简短描述", "category": "技术/生活/创意/讨论"},
        ...
    ]
}
话题要有吸引力，能引发讨论。只返回JSON。'''

        result = ai_service.generate_simple(prompt)
        result = result.strip()
        if result.startswith('```'):
            parts = result.split('\n', 1)
            result = parts[1] if len(parts) > 1 else ''
        if result.endswith('```'):
            parts = result.rsplit('```', 1)
            result = parts[0] if len(parts) > 1 else result

        import json
        data = json.loads(result.strip())

        if daily:
            daily.content = json.dumps(data, ensure_ascii=False)
            daily.created_at = datetime.utcnow()
            db.session.commit()
        else:
            AIDailyContent.create('writing_prompt', json.dumps(data, ensure_ascii=False))

        return jsonify({'success': True, **data})
    except Exception as e:
        default_data = {
            'prompts': [
                {'title': '分享你最近学到的一个新技能', 'description': '可以是编程、设计或任何领域', 'category': '技术'},
                {'title': '如果AI能帮你完成一件事...', 'description': '畅想AI的无限可能', 'category': '讨论'},
                {'title': '推荐一本改变你思维的书', 'description': '分享阅读体验和感悟', 'category': '生活'}
            ]
        }
        return jsonify({'success': True, **default_data, 'is_default': True})


@ai_bp.route('/api/daily/greeting', methods=['GET'])
def get_ai_greeting():
    """获取AI个性化问候"""
    if not current_user.is_authenticated:
        greetings = ['欢迎来到AI论坛！', '探索、分享、成长', '今天也要元气满满！']
        return jsonify({'success': True, 'greeting': random.choice(greetings)})

    hour = datetime.now().hour
    if hour < 6:
        time_greeting = '夜深了'
    elif hour < 9:
        time_greeting = '早上好'
    elif hour < 12:
        time_greeting = '上午好'
    elif hour < 14:
        time_greeting = '中午好'
    elif hour < 18:
        time_greeting = '下午好'
    elif hour < 22:
        time_greeting = '晚上好'
    else:
        time_greeting = '夜深了'

    # 使用chat模块配置
    ai_service = get_ai_service('chat')

    try:
        prompt = f'''为论坛用户"{current_user.username}"生成一句{time_greeting}问候语，要求：
1. 亲切友好，不超过20字
2. 可以适当幽默
3. 直接输出问候语，不要引号'''

        greeting = ai_service.generate_simple(prompt)
        greeting = greeting.strip().strip('"\'""''')

        return jsonify({'success': True, 'greeting': greeting, 'time_greeting': time_greeting})
    except:
        return jsonify({
            'success': True,
            'greeting': f'{time_greeting}，{current_user.username}！欢迎回来~',
            'time_greeting': time_greeting
        })


# ============ 自定义助手管理 ============

@ai_bp.route('/api/assistants', methods=['GET'])
@login_required
def list_assistants():
    """获取用户的自定义助手列表"""
    from app.models.custom_assistant import CustomAssistant
    
    assistants = CustomAssistant.find_by_user(current_user.id)
    can_create = CustomAssistant.can_create(current_user.id)
    
    return jsonify({
        'success': True,
        'assistants': [a.to_dict() for a in assistants],
        'can_create': can_create,
        'max_count': CustomAssistant.MAX_ASSISTANTS_PER_USER
    })


@ai_bp.route('/api/assistants', methods=['POST'])
@login_required
def create_assistant():
    """创建自定义助手"""
    from app.models.custom_assistant import CustomAssistant
    
    data = request.json or {}
    name = data.get('name', '').strip()
    icon = data.get('icon', '🤖').strip()
    description = data.get('description', '').strip()
    system_prompt = data.get('system_prompt', '').strip()
    
    # 验证必填字段
    if not name:
        return jsonify({'success': False, 'message': '助手名称不能为空'}), 400
    if len(name) > 50:
        return jsonify({'success': False, 'message': '名称不能超过50字符'}), 400
    if not system_prompt:
        return jsonify({'success': False, 'message': '系统提示词不能为空'}), 400
    if len(system_prompt) > 2000:
        return jsonify({'success': False, 'message': '提示词不能超过2000字符'}), 400
    
    # 检查数量限制
    if not CustomAssistant.can_create(current_user.id):
        return jsonify({
            'success': False, 
            'message': f'最多创建{CustomAssistant.MAX_ASSISTANTS_PER_USER}个自定义助手'
        }), 400
    
    try:
        assistant = CustomAssistant.create(
            user_id=current_user.id,
            name=name,
            icon=icon,
            description=description,
            system_prompt=system_prompt
        )
        return jsonify({'success': True, 'assistant': assistant.to_dict()})
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'创建失败: {str(e)}'}), 500


@ai_bp.route('/api/assistants/<int:assistant_id>', methods=['GET'])
@login_required
def get_assistant(assistant_id):
    """获取助手详情"""
    from app.models.custom_assistant import CustomAssistant
    
    assistant = CustomAssistant.find_by_id(assistant_id)
    
    if not assistant:
        return jsonify({'success': False, 'message': '助手不存在'}), 404
    if assistant.user_id != current_user.id:
        return jsonify({'success': False, 'message': '无权访问此助手'}), 403
    
    return jsonify({'success': True, 'assistant': assistant.to_dict()})


@ai_bp.route('/api/assistants/<int:assistant_id>', methods=['PUT'])
@login_required
def update_assistant(assistant_id):
    """更新自定义助手"""
    from app.models.custom_assistant import CustomAssistant
    
    assistant = CustomAssistant.find_by_id(assistant_id)
    
    if not assistant:
        return jsonify({'success': False, 'message': '助手不存在'}), 404
    if assistant.user_id != current_user.id:
        return jsonify({'success': False, 'message': '无权操作此助手'}), 403
    
    data = request.json or {}
    name = data.get('name')
    icon = data.get('icon')
    description = data.get('description')
    system_prompt = data.get('system_prompt')
    is_active = data.get('is_active')
    
    # 验证字段
    if name is not None:
        name = name.strip()
        if not name:
            return jsonify({'success': False, 'message': '助手名称不能为空'}), 400
        if len(name) > 50:
            return jsonify({'success': False, 'message': '名称不能超过50字符'}), 400
    
    if system_prompt is not None:
        system_prompt = system_prompt.strip()
        if not system_prompt:
            return jsonify({'success': False, 'message': '系统提示词不能为空'}), 400
        if len(system_prompt) > 2000:
            return jsonify({'success': False, 'message': '提示词不能超过2000字符'}), 400
    
    try:
        assistant.update(
            name=name,
            icon=icon.strip() if icon else None,
            description=description.strip() if description else None,
            system_prompt=system_prompt,
            is_active=is_active
        )
        return jsonify({'success': True, 'assistant': assistant.to_dict()})
    except Exception as e:
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'}), 500


@ai_bp.route('/api/assistants/<int:assistant_id>', methods=['DELETE'])
@login_required
def delete_assistant(assistant_id):
    """删除自定义助手"""
    from app.models.custom_assistant import CustomAssistant
    
    assistant = CustomAssistant.find_by_id(assistant_id)
    
    if not assistant:
        return jsonify({'success': False, 'message': '助手不存在'}), 404
    if assistant.user_id != current_user.id:
        return jsonify({'success': False, 'message': '无权操作此助手'}), 403
    
    if assistant.delete():
        return jsonify({'success': True, 'message': '助手已删除'})
    else:
        return jsonify({'success': False, 'message': '删除失败'}), 500



# ============ AI图片生成功能 ============

@ai_bp.route('/image')
@login_required
def image():
    """AI图片生成页面"""
    from app.services.image_service import get_image_service, IMAGE_SIZES
    
    image_service = get_image_service()
    model_limits = image_service.get_model_limits()
    
    return render_template('ai/image.html',
                          default_model=image_service.default_model,
                          default_size=image_service.default_size,
                          default_steps=image_service.default_steps,
                          default_guidance=image_service.default_guidance,
                          model_limits=model_limits,
                          image_sizes=IMAGE_SIZES)


@ai_bp.route('/api/image/generate', methods=['POST'])
@login_required
def generate_image():
    """生成图片（支持参考图，支持双API自动切换）"""
    try:
        from app.services.image_service import get_image_service, generate_with_fallback
        from app.models.user_image import UserImage
        
        data = request.json or {}
        prompt = data.get('prompt', '').strip()
        negative_prompt = data.get('negative_prompt', '').strip()
        model = data.get('model')
        image_size = data.get('image_size')
        batch_size = data.get('batch_size', 1)
        seed = data.get('seed')
        num_inference_steps = data.get('num_inference_steps')
        guidance_scale = data.get('guidance_scale')
        reference_image = data.get('reference_image')  # 参考图（base64或URL）
        image_strength = data.get('image_strength', 0.65)  # 参考图强度
        use_fallback = data.get('use_fallback', False)  # 是否使用备用API
        
        if not prompt:
            return jsonify({'success': False, 'message': '提示词不能为空'}), 400
        
        # 检查每日生成限制（普通用户每日5张，管理员无限制）
        image_service = get_image_service()
        DAILY_LIMIT = image_service.daily_limit
        use_fallback_api = use_fallback
        
        if not current_user.is_admin():
            today_count = UserImage.count_today_generated(current_user.id)
            if today_count >= DAILY_LIMIT:
                # 主API次数用完，自动切换到备用API
                if image_service.fallback_api_key:
                    use_fallback_api = True
                else:
                    return jsonify({
                        'success': False, 
                        'message': f'今日生成次数已达上限（{DAILY_LIMIT}张），请明天再试'
                    }), 429
        
        # 生成图片
        if use_fallback_api and not reference_image:
            # 使用备用API（不支持参考图）
            result = generate_with_fallback(
                prompt=prompt,
                user_id=current_user.id,
                negative_prompt=negative_prompt,
                image_size=image_size or '1024x1024',
                use_fallback=True
            )
        else:
            # 使用主API
            result = image_service.generate_image(
                prompt=prompt,
                negative_prompt=negative_prompt if negative_prompt else None,
                model=model,
                image_size=image_size,
                batch_size=int(batch_size) if batch_size else 1,
                seed=int(seed) if seed else None,
                num_inference_steps=int(num_inference_steps) if num_inference_steps else None,
            guidance_scale=float(guidance_scale) if guidance_scale else None,
            reference_image=reference_image,
            image_strength=float(image_strength) if image_strength else 0.65
        )
        
        if result.success:
            # 自动下载并保存生成的图片到本地（避免外部URL过期）
            saved_images = []
            for img in result.images:
                if img.get('url'):
                    try:
                        # 下载并保存到本地
                        success, message, user_image = image_service.download_and_save(
                            image_url=img.get('url'),
                            user_id=current_user.id,
                            prompt=prompt,
                            negative_prompt=negative_prompt,
                            model=model or '',
                            image_size=image_size or '',
                            seed=img.get('seed') or result.seed
                        )
                        if success and user_image:
                            # 使用本地路径替换外部URL
                            saved_images.append({
                                'url': user_image.local_path,
                                'seed': img.get('seed') or result.seed
                            })
                        else:
                            # 下载失败，仍然返回原始URL（可能会过期）
                            current_app.logger.warning(f'Failed to save image locally: {message}')
                            saved_images.append(img)
                    except Exception as e:
                        current_app.logger.warning(f'Failed to save generated image: {e}')
                        saved_images.append(img)
            
            return jsonify({
                'success': True,
                'images': saved_images,
                'seed': result.seed,
                'inference_time': result.inference_time
            })
        else:
            return jsonify({
                'success': False,
                'message': result.message
            }), 400
    except Exception as e:
        current_app.logger.error(f'Image generation error: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'生成失败: {str(e)}'
        }), 500


@ai_bp.route('/api/image/gallery', methods=['GET'])
@login_required
def get_image_gallery():
    """获取用户图库"""
    from app.models.user_image import UserImage
    
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    image_type = request.args.get('type')  # 'generated' | 'uploaded' | None
    
    images, total = UserImage.find_by_user(
        user_id=current_user.id,
        page=page,
        per_page=per_page,
        image_type=image_type
    )
    
    return jsonify({
        'success': True,
        'images': [img.to_dict() for img in images],
        'total': total,
        'page': page,
        'per_page': per_page
    })


@ai_bp.route('/api/image/daily-limit', methods=['GET'])
@login_required
def get_image_daily_limit():
    """获取用户今日图片生成限制信息"""
    from app.models.user_image import UserImage
    from app.services.image_service import get_image_service
    
    image_service = get_image_service()
    DAILY_LIMIT = image_service.daily_limit
    is_admin = current_user.is_admin()
    today_count = UserImage.count_today_generated(current_user.id)
    has_fallback = bool(image_service.fallback_api_key)
    
    return jsonify({
        'success': True,
        'daily_limit': DAILY_LIMIT if not is_admin else -1,  # -1表示无限制
        'used_today': today_count,
        'remaining': max(0, DAILY_LIMIT - today_count) if not is_admin else -1,
        'is_admin': is_admin,
        'has_fallback': has_fallback,  # 是否有备用API
        'using_fallback': today_count >= DAILY_LIMIT and has_fallback  # 是否正在使用备用API
    })


@ai_bp.route('/api/image/generate-prompt', methods=['POST'])
@login_required
def generate_image_prompt():
    """AI生成/优化绘图提示词"""
    try:
        from app.services.image_service import generate_prompt_with_ai
        
        data = request.json or {}
        user_input = data.get('input', '').strip()
        style = data.get('style', '').strip()
        
        if not user_input:
            return jsonify({'success': False, 'message': '请输入描述'}), 400
        
        success, prompt, error = generate_prompt_with_ai(user_input, style)
        
        if success:
            return jsonify({
                'success': True,
                'prompt': prompt
            })
        else:
            return jsonify({
                'success': False,
                'message': error
            }), 400
    except Exception as e:
        current_app.logger.error(f'Generate prompt error: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'生成失败: {str(e)}'
        }), 500


@ai_bp.route('/api/image/sticker', methods=['POST'])
@login_required
def generate_sticker_image():
    """生成表情包图片"""
    from app.services.image_service import generate_sticker
    
    data = request.json or {}
    prompt = data.get('prompt', '').strip()
    
    if not prompt:
        return jsonify({'success': False, 'message': '请输入表情包描述'}), 400
    
    success, image_url, error = generate_sticker(prompt, current_user.id)
    
    if success:
        return jsonify({
            'success': True,
            'image_url': image_url
        })
    else:
        return jsonify({
            'success': False,
            'message': error
        }), 400


@ai_bp.route('/api/image/save', methods=['POST'])
@login_required
def save_image_to_gallery():
    """保存图片到图库"""
    from app.services.image_service import get_image_service
    
    data = request.json or {}
    image_url = data.get('image_url', '').strip()
    prompt = data.get('prompt', '').strip()
    negative_prompt = data.get('negative_prompt', '').strip()
    model = data.get('model', '').strip()
    image_size = data.get('image_size', '').strip()
    seed = data.get('seed')
    
    if not image_url:
        return jsonify({'success': False, 'message': '图片URL不能为空'}), 400
    
    image_service = get_image_service()
    success, message, user_image = image_service.save_to_gallery(
        user_id=current_user.id,
        image_url=image_url,
        prompt=prompt,
        negative_prompt=negative_prompt,
        model=model,
        image_size=image_size,
        seed=int(seed) if seed else None
    )
    
    if success:
        return jsonify({
            'success': True,
            'message': message,
            'image': user_image.to_dict() if user_image else None
        })
    else:
        return jsonify({
            'success': False,
            'message': message
        }), 400


@ai_bp.route('/api/image/<int:image_id>', methods=['DELETE'])
@login_required
def delete_image(image_id):
    """删除图库图片"""
    from app.models.user_image import UserImage
    import os
    
    image = UserImage.find_by_id(image_id)
    
    if not image:
        return jsonify({'success': False, 'message': '图片不存在'}), 404
    
    if image.user_id != current_user.id:
        return jsonify({'success': False, 'message': '无权删除此图片'}), 403
    
    # 删除本地文件
    if image.local_path:
        try:
            file_path = os.path.join(current_app.root_path, image.local_path.lstrip('/'))
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            current_app.logger.warning(f'Failed to delete image file: {e}')
    
    # 删除数据库记录
    if image.delete():
        return jsonify({'success': True, 'message': '图片已删除'})
    else:
        return jsonify({'success': False, 'message': '删除失败'}), 500


@ai_bp.route('/api/image/models', methods=['GET'])
@login_required
def get_image_models():
    """获取支持的图片生成模型和参数"""
    from app.services.image_service import get_image_service, IMAGE_SIZES, get_preset_models
    
    api_type = request.args.get('api', 'primary')  # 'primary' 或 'fallback'
    image_service = get_image_service()
    
    # 如果选择备用API，返回备用API的模型
    if api_type == 'fallback':
        fallback_model = image_service.fallback_model or 'Kwai-Kolors/Kolors'
        return jsonify({
            'success': True,
            'default_model': fallback_model,
            'default_size': '1024x1024',
            'default_steps': 20,
            'default_guidance': 7.5,
            'models': [
                {
                    'id': fallback_model,
                    'name': 'Kolors',
                    'provider': 'SiliconFlow',
                    'is_custom': False
                }
            ],
            'sizes_by_model': IMAGE_SIZES,
            'preset_models': []
        })
    
    # 获取所有可用模型
    available_models = image_service.get_available_models()
    
    return jsonify({
        'success': True,
        'default_model': image_service.default_model,
        'default_size': image_service.default_size,
        'default_steps': image_service.default_steps,
        'default_guidance': image_service.default_guidance,
        'models': available_models,
        'sizes_by_model': IMAGE_SIZES,
        'preset_models': get_preset_models()
    })


@ai_bp.route('/api/image/model-info/<path:model_id>', methods=['GET'])
@login_required
def get_image_model_info(model_id):
    """获取指定模型的详细信息"""
    from app.services.image_service import get_image_service
    
    image_service = get_image_service()
    model_config = image_service.get_model_config(model_id)
    limits = image_service.get_model_limits(model_id)
    
    return jsonify({
        'success': True,
        'model': model_id,
        'config': model_config,
        'limits': limits
    })


@ai_bp.route('/gallery')
@login_required
def gallery():
    """用户图库页面"""
    from app.models.user_image import UserImage
    
    images = UserImage.get_by_user(current_user.id, limit=100)
    
    return render_template('ai/gallery.html', images=[img.to_dict() for img in images])



# ============ AI视觉理解功能 ============

@ai_bp.route('/api/vision/understand', methods=['POST'])
@login_required
def understand_image():
    """图片理解"""
    from app.services.vision_service import get_vision_service
    
    data = request.json or {}
    images = data.get('images', [])  # 图片列表（URL或base64）
    prompt = data.get('prompt', '').strip()
    detail = data.get('detail', 'high')
    
    # 支持单张图片
    if 'image' in data and not images:
        images = [data.get('image')]
    
    if not images:
        return jsonify({'success': False, 'message': '请提供图片'}), 400
    
    if not prompt:
        prompt = '请描述这张图片的内容'
    
    # 检查速率限制
    ai_service = get_ai_service('chat')
    allowed, message = ai_service.check_rate_limit(str(current_user.id))
    if not allowed:
        return jsonify({'success': False, 'message': message}), 429
    
    vision_service = get_vision_service()
    result = vision_service.understand_multiple_images(
        images=images,
        prompt=prompt,
        detail=detail
    )
    
    if result.success:
        return jsonify({
            'success': True,
            'content': result.content,
            'tokens_used': result.tokens_used,
            'response_time': result.response_time
        })
    else:
        return jsonify({
            'success': False,
            'message': result.message
        }), 400


@ai_bp.route('/api/vision/estimate-tokens', methods=['POST'])
@login_required
def estimate_vision_tokens():
    """估算图片token消耗"""
    from app.services.vision_service import get_vision_service
    
    data = request.json or {}
    images = data.get('images', [])
    detail = data.get('detail', 'high')
    
    if 'image' in data and not images:
        images = [data.get('image')]
    
    if not images:
        return jsonify({'success': False, 'message': '请提供图片'}), 400
    
    vision_service = get_vision_service()
    estimated_tokens = vision_service.estimate_tokens(images, detail)
    
    return jsonify({
        'success': True,
        'estimated_tokens': estimated_tokens,
        'image_count': len(images),
        'detail': detail
    })



# ============ 用户设置 ============

@ai_bp.route('/api/user/settings', methods=['GET'])
@login_required
def get_user_settings():
    """获取用户设置"""
    from app.services.user_settings_service import get_user_settings as get_settings
    
    settings = get_settings(current_user.id)
    return jsonify({
        'success': True,
        'settings': settings
    })


@ai_bp.route('/api/user/settings', methods=['PUT'])
@login_required
def update_user_settings():
    """更新用户设置"""
    from app.services.user_settings_service import update_user_settings as update_settings
    
    data = request.json or {}
    
    # 只允许更新特定的设置项
    allowed_keys = ['thinking_visible', 'theme', 'ai_greeting_enabled']
    updates = {k: v for k, v in data.items() if k in allowed_keys}
    
    if not updates:
        return jsonify({'success': False, 'message': '没有有效的设置项'}), 400
    
    settings = update_settings(current_user.id, updates)
    return jsonify({
        'success': True,
        'settings': settings
    })


@ai_bp.route('/api/user/settings/thinking', methods=['GET'])
@login_required
def get_thinking_preference():
    """获取思维链显示偏好"""
    from app.services.user_settings_service import get_thinking_visible
    
    visible = get_thinking_visible(current_user.id)
    return jsonify({
        'success': True,
        'thinking_visible': visible
    })


@ai_bp.route('/api/user/settings/thinking', methods=['PUT'])
@login_required
def set_thinking_preference():
    """设置思维链显示偏好"""
    from app.services.user_settings_service import set_thinking_visible
    
    data = request.json or {}
    visible = data.get('thinking_visible', True)
    
    set_thinking_visible(current_user.id, bool(visible))
    return jsonify({
        'success': True,
        'thinking_visible': bool(visible)
    })


@ai_bp.route('/api/ai/parse-thinking', methods=['POST'])
@login_required
def parse_thinking_content():
    """解析思维链内容"""
    from app.utils.think_parser import ThinkModelParser
    
    data = request.json or {}
    content = data.get('content', '')
    
    if not content:
        return jsonify({'success': False, 'message': '内容不能为空'}), 400
    
    result = ThinkModelParser.parse(content)
    
    return jsonify({
        'success': True,
        'has_thinking': result.has_thinking,
        'thinking': result.thinking,
        'response': result.response,
        'pattern_type': result.pattern_type
    })



# ============ 个人中心AI功能 ============

@ai_bp.route('/api/profile/ai-analysis', methods=['POST'])
@login_required
def profile_ai_analysis():
    """AI个性分析"""
    from app.services.profile_ai_service import get_profile_ai_service
    
    force_refresh = request.json.get('refresh', False) if request.json else False
    
    service = get_profile_ai_service(current_user.id)
    result = service.analyze_personality(force_refresh=force_refresh)
    
    if result.get('success'):
        return jsonify(result)
    else:
        return jsonify(result), 400


@ai_bp.route('/api/profile/ai-bio', methods=['POST'])
@login_required
def profile_ai_bio():
    """AI生成简介"""
    from app.services.profile_ai_service import get_profile_ai_service
    
    force_refresh = request.json.get('refresh', False) if request.json else False
    
    service = get_profile_ai_service(current_user.id)
    result = service.generate_bio(force_refresh=force_refresh)
    
    if result.get('success'):
        return jsonify(result)
    else:
        return jsonify(result), 400


@ai_bp.route('/api/profile/ai-avatar-desc', methods=['POST'])
@login_required
def profile_ai_avatar_desc():
    """AI头像描述生成"""
    from app.services.profile_ai_service import get_profile_ai_service
    
    force_refresh = request.json.get('refresh', False) if request.json else False
    
    service = get_profile_ai_service(current_user.id)
    result = service.generate_avatar_description(force_refresh=force_refresh)
    
    if result.get('success'):
        return jsonify(result)
    else:
        return jsonify(result), 400


@ai_bp.route('/api/profile/ai-suggestions', methods=['GET'])
@login_required
def profile_ai_suggestions():
    """AI写作建议"""
    from app.services.profile_ai_service import get_profile_ai_service
    
    force_refresh = request.args.get('refresh', 'false') == 'true'
    
    service = get_profile_ai_service(current_user.id)
    result = service.get_writing_suggestions(force_refresh=force_refresh)
    
    return jsonify(result)


@ai_bp.route('/api/profile/ai-stats', methods=['GET'])
@login_required
def profile_ai_stats():
    """AI使用统计"""
    from app.services.profile_ai_service import get_profile_ai_service
    
    service = get_profile_ai_service(current_user.id)
    result = service.get_usage_stats()
    
    return jsonify(result)


# ============ 代码运行功能 ============

@ai_bp.route('/code')
@login_required
def code_runner_page():
    """代码运行器页面"""
    return render_template('ai/code.html')


@ai_bp.route('/api/code/run', methods=['POST'])
@login_required
def run_code():
    """运行Python代码"""
    from app.services.code_runner_service import get_code_runner_service
    
    data = request.json or {}
    code = data.get('code', '').strip()
    timeout = data.get('timeout', 30)
    stdin_input = data.get('stdin_input', None)  # 用户输入内容
    
    if not code:
        return jsonify({'success': False, 'message': '代码不能为空'}), 400
    
    # 限制超时时间
    timeout = min(max(int(timeout), 5), 60)
    
    # 检查速率限制
    ai_service = get_ai_service('chat')
    allowed, message = ai_service.check_rate_limit(str(current_user.id))
    if not allowed:
        return jsonify({'success': False, 'message': message}), 429
    
    runner = get_code_runner_service()
    result = runner.run_python(code, timeout=timeout, user_id=current_user.id, stdin_input=stdin_input)
    
    response = {
        'success': result['success'],
        'output': result.get('output', ''),
        'error': result.get('error', ''),
        'execution_time': result.get('execution_time', 0),
        'images': result.get('images', [])
    }
    
    # 如果需要用户输入
    if result.get('needs_input'):
        response['needs_input'] = True
        response['input_prompt'] = result.get('input_prompt', ['请输入'])
        response['message'] = result.get('message', '程序需要用户输入')
        response['is_interactive'] = result.get('is_interactive', False)
        response['input_count'] = result.get('input_count', 1)
    
    return jsonify(response)


@ai_bp.route('/api/code/install', methods=['POST'])
@login_required
def install_package():
    """安装Python包"""
    from app.services.code_runner_service import get_code_runner_service
    
    data = request.json or {}
    package_name = data.get('package', '').strip()
    
    if not package_name:
        return jsonify({'success': False, 'message': '包名不能为空'}), 400
    
    runner = get_code_runner_service()
    result = runner.install_package(package_name, user_id=current_user.id)
    
    return jsonify(result)


@ai_bp.route('/api/code/packages', methods=['GET'])
@login_required
def list_packages():
    """列出已安装的包"""
    from app.services.code_runner_service import get_code_runner_service
    
    runner = get_code_runner_service()
    packages = runner.list_installed_packages()
    allowed = runner.get_allowed_packages()
    
    return jsonify({
        'success': True,
        'installed': packages,
        'allowed': allowed
    })


@ai_bp.route('/api/code/check', methods=['POST'])
@login_required
def check_code_safety():
    """检查代码安全性"""
    from app.services.code_runner_service import get_code_runner_service
    
    data = request.json or {}
    code = data.get('code', '').strip()
    
    if not code:
        return jsonify({'success': False, 'message': '代码不能为空'}), 400
    
    runner = get_code_runner_service()
    is_safe, message = runner.check_code_safety(code)
    
    return jsonify({
        'success': True,
        'is_safe': is_safe,
        'message': message
    })
