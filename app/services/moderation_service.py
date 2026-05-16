"""
AI内容审核服务
使用DeepSeek API对用户发布的内容进行自动审核
"""
import json
import threading
from typing import List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from flask import current_app

from app.services.ai_service import get_ai_service
from app.models.moderation_log import ModerationLog


@dataclass
class ModerationResult:
    """审核结果"""
    action: str  # 'approve', 'hold', 'reject'
    confidence: float  # 0.0 - 1.0
    reasons: List[str]
    categories: List[str]  # 'spam', 'inappropriate', 'sensitive', 'provocative'
    
    def to_dict(self) -> dict:
        return asdict(self)


class ModerationService:
    """AI内容审核服务"""
    
    def __init__(self):
        self.config = self._load_moderation_config()
    
    def _load_moderation_config(self) -> dict:
        """加载审核配置"""
        json_config = current_app.config.get('JSON_CONFIG', {})
        default_config = {
            'enabled': False,
            'sensitivity': 'medium',
            'auto_reject_threshold': 0.9,
            'hold_threshold': 0.6,
            'check_spam': True,
            'check_inappropriate': True,
            'check_sensitive': False,
            'check_provocative': False,  # 新增：引战内容检测
        }
        return {**default_config, **json_config.get('ai_moderation', {})}
    
    def is_enabled(self) -> bool:
        """检查审核是否启用"""
        return self.config.get('enabled', False)
    
    def moderate_content(self, content: str, content_type: str = 'post',
                        title: str = '', author_id: int = None) -> ModerationResult:
        """
        审核内容
        
        Args:
            content: 要审核的内容
            content_type: 内容类型 ('post', 'comment')
            title: 标题（可选）
            author_id: 作者ID（可选）
            
        Returns:
            ModerationResult: 审核结果
        """
        if not self.is_enabled():
            return ModerationResult(
                action='approve',
                confidence=1.0,
                reasons=['审核功能未启用'],
                categories=[]
            )
        
        try:
            # 调用AI进行审核
            ai_result = self._call_ai_moderation(content, title)
            
            # 根据阈值决定动作
            action = self._determine_action(ai_result['confidence'])
            
            result = ModerationResult(
                action=action,
                confidence=ai_result['confidence'],
                reasons=ai_result['reasons'],
                categories=ai_result['categories']
            )
            
            return result
            
        except Exception as e:
            current_app.logger.error(f'Moderation error: {str(e)}')
            # 服务不可用时，允许内容通过但记录警告
            return ModerationResult(
                action='approve',
                confidence=0.0,
                reasons=[f'审核服务暂时不可用: {str(e)}'],
                categories=[]
            )
    
    def moderate_content_async(self, content: str, content_type: str, content_id: int,
                               title: str = '', author_id: int = None):
        """
        异步审核内容
        优先使用Celery，不可用时回退到线程

        Args:
            content: 要审核的内容
            content_type: 内容类型
            content_id: 内容ID
            title: 标题
            author_id: 作者ID
        """
        try:
            from app.tasks.moderation_tasks import moderate_content_task
            moderate_content_task(content, content_type, content_id, title, author_id)
        except Exception:
            app = current_app._get_current_object()

            def _do_moderation():
                with app.app_context():
                    try:
                        result = self.moderate_content(content, content_type, title, author_id)
                        self.log_moderation(
                            content_type=content_type,
                            content_id=content_id,
                            content_preview=content[:200] if content else '',
                            result=result,
                            author_id=author_id
                        )
                        self._process_moderation_result(content_type, content_id, result, author_id)
                    except Exception as e:
                        current_app.logger.error(f'Async moderation error: {str(e)}')
                        self._set_content_pending(content_type, content_id)

            thread = threading.Thread(target=_do_moderation)
            thread.daemon = True
            thread.start()
    
    def _process_moderation_result(self, content_type: str, content_id: int,
                                   result: ModerationResult, author_id: int = None):
        """处理审核结果"""
        if result.action == 'approve':
            self._update_content_status(content_type, content_id, 'published')
            # 审核通过后添加到知识库
            if content_type == 'post':
                self._add_post_to_knowledge(content_id)
            elif content_type == 'comment':
                # 评论审核通过后更新帖子回复数
                self._update_post_reply_count(content_id)
        elif result.action == 'reject':
            self._update_content_status(content_type, content_id, 'rejected')
            # 发送拒绝通知
            if author_id:
                self._send_rejection_notification(author_id, content_type, content_id, result)
        # hold状态保持pending，等待人工审核
    
    def _update_post_reply_count(self, comment_id: int):
        """评论审核通过后更新帖子回复数"""
        try:
            from app.models.comment import Comment
            from app.models.post import Post
            
            comment = Comment.query.get(comment_id)
            if comment:
                post = Post.query.get(comment.post_id)
                if post:
                    post.increment_reply()
        except Exception as e:
            current_app.logger.error(f'Failed to update post reply count: {str(e)}')
    
    def _add_post_to_knowledge(self, post_id: int):
        """审核通过后添加帖子到知识库"""
        try:
            from app.models.post import Post
            from app.services.knowledge_service import add_post_to_knowledge_async
            
            post = Post.query.get(post_id)
            if post:
                add_post_to_knowledge_async(
                    post_id=post.id,
                    title=post.title,
                    content=post.content,
                    board_name=post.board.name if post.board else None,
                    author_name=post.author.username if post.author else None
                )
        except Exception as e:
            current_app.logger.error(f'Failed to add post to knowledge: {str(e)}')
    
    def _send_rejection_notification(self, author_id: int, content_type: str,
                                     content_id: int, result: ModerationResult):
        """发送拒绝通知给作者"""
        try:
            from app.services.message_service import get_message_service
            
            content_type_name = '帖子' if content_type == 'post' else '评论'
            reasons = '；'.join(result.reasons) if result.reasons else '内容不符合社区规范'
            
            content = f'''您发布的{content_type_name}未能通过审核。

**拒绝原因：**
{reasons}

**AI置信度：** {int(result.confidence * 100)}%

如果您认为这是误判，请联系管理员申诉。

感谢您的理解与配合。'''
            
            message_service = get_message_service()
            message_service.send_moderation_notification(
                recipient_id=author_id,
                content=content,
                subject=f'您的{content_type_name}未通过审核',
                content_type=content_type,
                content_id=content_id
            )
        except Exception as e:
            current_app.logger.error(f'Send rejection notification error: {str(e)}')
    
    def _set_content_pending(self, content_type: str, content_id: int):
        """设置内容为待审核状态"""
        self._update_content_status(content_type, content_id, 'pending')
    
    def _call_ai_moderation(self, content: str, title: str = '') -> dict:
        """调用AI进行内容审核"""
        ai_service = get_ai_service('moderation')
        
        # 构建审核规则描述
        rules = []
        categories_list = ['spam', 'inappropriate', 'sensitive']
        
        if self.config.get('check_spam'):
            rules.append('垃圾内容/广告')
        if self.config.get('check_inappropriate'):
            rules.append('不当言论/攻击性内容')
        if self.config.get('check_sensitive'):
            rules.append('敏感话题')
        if self.config.get('check_provocative'):
            rules.append('引战内容/挑衅言论')
            categories_list.append('provocative')
        
        # 添加谐音检测类别
        categories_list.append('homophone')
        
        sensitivity_desc = {
            'low': '宽松（只标记明显违规）',
            'medium': '中等（标记可疑内容）',
            'high': '严格（标记任何可能违规）'
        }
        
        prompt = f'''你是一位专业的中文社区内容审核员，请仔细审核以下用户发布的内容。

## 审核维度
{', '.join(rules)}

## 审核敏感度
{sensitivity_desc.get(self.config.get('sensitivity', 'medium'))}

## 重点检测：谐音规避
请特别注意检测用户使用谐音、同音字、形近字来规避审核的行为，包括但不限于：

1. **脏话谐音**：如"卧槽→我草/握草"、"傻逼→沙比/煞笔/sb"、"妈的→麻的/MD"、"操→艹/草/曹"、"屎→史/屎"、"滚→衮"等
2. **敏感词谐音**：如"死→4/si/斯"、"杀→沙/煞"、"毒→独/读"等
3. **人身攻击谐音**：如"智障→zz/支障"、"脑残→nc/脑c"、"废物→fw/肺物"、"垃圾→lj/辣鸡"等
4. **拼音缩写**：如"nmsl"、"cnm"、"sb"、"tm"、"wc"、"mdzz"等常见脏话缩写
5. **符号替换**：如"f*ck"、"s.b"、"傻*"等用符号替代关键字
6. **数字谐音**：如"250"、"38"、"2B"等带有侮辱性的数字组合
7. **emoji/表情规避**：用表情符号拼凑成脏话或侮辱性内容
8. **故意错别字**：如"弱智→若智"、"白痴→白吃"等

## 审核原则
- 结合上下文语境判断，避免误伤正常用词
- 对于明显恶意使用谐音规避的内容，应提高违规置信度
- 技术讨论中的正常缩写（如API、SDK）不应被误判

'''
        if title:
            prompt += f'## 待审核标题\n{title}\n\n'
        prompt += f'''## 待审核内容
{content}

## 输出格式
请以JSON格式返回审核结果：
{{
    "confidence": 0.0-1.0之间的数字，表示内容违规的可能性,
    "categories": {json.dumps(categories_list)}中触发的类别列表（homophone表示检测到谐音规避）,
    "reasons": ["具体原因1", "具体原因2"]，如检测到谐音请说明原词和谐音词
}}

## 置信度参考
- 0.0-0.3：内容完全正常，无违规
- 0.4-0.5：存在轻微可疑内容，可能是误判
- 0.6-0.7：较明显的违规嫌疑，建议人工复核
- 0.8-1.0：明显违规，包括使用谐音规避的恶意内容

只返回JSON，不要其他内容。'''

        try:
            response = ai_service.generate_simple(prompt)
            
            # 解析JSON响应
            # 尝试提取JSON部分
            response = response.strip()
            if response.startswith('```'):
                lines = response.split('\n')
                response = '\n'.join(lines[1:-1])
            
            result = json.loads(response)
            
            return {
                'confidence': float(result.get('confidence', 0.5)),
                'categories': result.get('categories', []),
                'reasons': result.get('reasons', ['AI审核完成'])
            }
            
        except json.JSONDecodeError:
            current_app.logger.warning(f'Failed to parse AI moderation response: {response}')
            return {
                'confidence': 0.5,
                'categories': [],
                'reasons': ['AI响应解析失败，建议人工审核']
            }
        except Exception as e:
            raise e
    
    def _determine_action(self, confidence: float) -> str:
        """根据置信度决定动作"""
        auto_reject = self.config.get('auto_reject_threshold', 0.9)
        hold = self.config.get('hold_threshold', 0.6)
        
        if confidence >= auto_reject:
            return 'reject'
        elif confidence >= hold:
            return 'hold'
        else:
            return 'approve'
    
    def log_moderation(self, content_type: str, content_id: int, 
                       content_preview: str, result: ModerationResult,
                       author_id: int = None) -> ModerationLog:
        """记录审核日志 - 修复：同时设置final_action"""
        # 对于自动通过和自动拒绝，直接设置final_action
        final_action = None
        if result.action == 'approve':
            final_action = 'approve'
        elif result.action == 'reject':
            final_action = 'reject'
        # hold状态的final_action保持为None，等待人工审核
        
        return ModerationLog.create(
            content_type=content_type,
            content_id=content_id,
            content_preview=content_preview,
            ai_action=result.action,
            ai_confidence=result.confidence,
            ai_reasons=result.reasons,
            ai_categories=result.categories,
            author_id=author_id,
            final_action=final_action
        )
    
    def get_statistics(self, date: datetime = None) -> dict:
        """
        获取审核统计数据
        
        Args:
            date: 统计日期，默认为今天
            
        Returns:
            dict: 统计数据
        """
        from app.extensions import db
        
        if date is None:
            date = datetime.utcnow()
        
        # 获取当天开始时间
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        # 今日通过数量（包括AI自动通过和人工通过）
        approved_today = ModerationLog.query.filter(
            ModerationLog.final_action == 'approve',
            db.or_(
                # AI自动通过（created_at在今天）
                db.and_(
                    ModerationLog.ai_action == 'approve',
                    ModerationLog.created_at >= day_start,
                    ModerationLog.created_at < day_end
                ),
                # 人工通过（reviewed_at在今天）
                db.and_(
                    ModerationLog.reviewed_at >= day_start,
                    ModerationLog.reviewed_at < day_end
                )
            )
        ).count()
        
        # 今日拒绝数量（包括AI自动拒绝和人工拒绝）
        rejected_today = ModerationLog.query.filter(
            ModerationLog.final_action == 'reject',
            db.or_(
                # AI自动拒绝（created_at在今天）
                db.and_(
                    ModerationLog.ai_action == 'reject',
                    ModerationLog.created_at >= day_start,
                    ModerationLog.created_at < day_end
                ),
                # 人工拒绝（reviewed_at在今天）
                db.and_(
                    ModerationLog.reviewed_at >= day_start,
                    ModerationLog.reviewed_at < day_end
                )
            )
        ).count()
        
        # 待审核数量
        pending_count = ModerationLog.query.filter(
            ModerationLog.ai_action == 'hold',
            ModerationLog.final_action == None
        ).count()
        
        # 今日总审核数
        total_today = ModerationLog.query.filter(
            ModerationLog.created_at >= day_start,
            ModerationLog.created_at < day_end
        ).count()
        
        return {
            'approved_today': approved_today,
            'rejected_today': rejected_today,
            'pending_count': pending_count,
            'total_today': total_today
        }
    
    def get_pending_queue(self, page: int = 1, per_page: int = 20) -> Tuple[List[dict], int]:
        """获取待审核队列"""
        items, total = ModerationLog.get_pending(page, per_page)
        return [item.to_dict(include_author=True) for item in items], total
    
    def get_rejected_content(self, page: int = 1, per_page: int = 20) -> Tuple[List[dict], int]:
        """获取被拒绝的内容"""
        query = ModerationLog.query.filter(
            ModerationLog.final_action == 'reject'
        ).order_by(ModerationLog.created_at.desc())
        
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        return [item.to_dict(include_author=True) for item in pagination.items], pagination.total
    
    def approve_content(self, log_id: int, moderator_id: int, note: str = '') -> bool:
        """批准内容"""
        log = ModerationLog.query.get(log_id)
        if not log:
            return False
        
        success = log.approve(moderator_id, note)
        
        if success:
            # 更新原内容状态
            self._update_content_status(log.content_type, log.content_id, 'published')
        
        return success
    
    def reject_content(self, log_id: int, moderator_id: int, note: str = '') -> bool:
        """拒绝内容"""
        log = ModerationLog.query.get(log_id)
        if not log:
            return False
        
        success = log.reject(moderator_id, note)
        
        if success:
            # 更新原内容状态
            self._update_content_status(log.content_type, log.content_id, 'rejected')
            
            # 发送拒绝通知
            if log.author_id:
                result = ModerationResult(
                    action='reject',
                    confidence=log.ai_confidence,
                    reasons=log.ai_reasons or [note] if note else ['人工审核未通过'],
                    categories=log.ai_categories or []
                )
                self._send_rejection_notification(log.author_id, log.content_type, log.content_id, result)
        
        return success
    
    def _update_content_status(self, content_type: str, content_id: int, status: str):
        """更新原内容状态"""
        try:
            if content_type == 'post':
                from app.models.post import Post
                post = Post.query.get(content_id)
                if post:
                    post.status = status
                    from app.extensions import db
                    db.session.commit()
            elif content_type == 'comment':
                from app.models.comment import Comment
                comment = Comment.query.get(content_id)
                if comment:
                    comment.status = status
                    from app.extensions import db
                    db.session.commit()
        except Exception as e:
            current_app.logger.error(f'Failed to update content status: {str(e)}')


def get_moderation_service() -> ModerationService:
    """获取审核服务实例"""
    return ModerationService()
