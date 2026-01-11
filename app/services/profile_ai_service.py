"""
个人中心AI服务
提供AI个性分析、简介生成、头像描述等功能
"""
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from flask import current_app

from app.services.ai_service import get_ai_service
from app.models.post import Post
from app.models.api_log import APILog
from app.models.ai_daily import AIDailyContent
from app.extensions import db


# 缓存有效期（小时）
CACHE_HOURS = 24


class ProfileAIService:
    """个人中心AI服务"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.ai_service = get_ai_service('chat')
    
    def analyze_personality(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        AI个性分析 - 分析用户最近20篇帖子
        
        Args:
            force_refresh: 是否强制刷新（忽略缓存）
            
        Returns:
            Dict: 分析结果
        """
        cache_key = f'personality_{self.user_id}'
        
        # 检查缓存
        if not force_refresh:
            cached = self._get_cached(cache_key)
            if cached:
                return cached
        
        # 获取用户最近20篇帖子
        posts = Post.query.filter_by(author_id=self.user_id)\
            .order_by(Post.created_at.desc())\
            .limit(20)\
            .all()
        
        if not posts:
            return {
                'success': False,
                'message': '暂无足够的帖子进行分析',
                'post_count': 0
            }
        
        # 构建分析内容
        posts_content = '\n\n'.join([
            f'标题：{p.title}\n内容：{p.content[:500]}...' if len(p.content) > 500 else f'标题：{p.title}\n内容：{p.content}'
            for p in posts
        ])
        
        prompt = f'''请分析以下用户的{len(posts)}篇帖子，总结其写作风格和个性特点。

帖子内容：
{posts_content}

请以JSON格式返回分析结果：
{{
    "style_tags": ["标签1", "标签2", "标签3"],  // 3-5个写作风格标签
    "common_words": ["词1", "词2", "词3"],  // 3-5个常用词汇
    "active_topics": ["话题1", "话题2"],  // 2-3个活跃话题
    "personality": "一段50字以内的个性特点描述",
    "writing_level": "初级/中级/高级",  // 写作水平评估
    "suggestions": ["建议1", "建议2"]  // 1-2条写作建议
}}

只返回JSON，不要其他内容。'''

        try:
            result = self.ai_service.generate_simple(prompt)
            result = self._clean_json_response(result)
            data = json.loads(result)
            data['success'] = True
            data['post_count'] = len(posts)
            data['analyzed_at'] = datetime.utcnow().isoformat()
            
            # 缓存结果
            self._set_cached(cache_key, data)
            
            return data
        except json.JSONDecodeError:
            return {
                'success': False,
                'message': '分析结果解析失败',
                'raw_result': result[:500] if result else ''
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'分析失败: {str(e)}'
            }
    
    def generate_bio(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        AI生成个人简介 - 生成3种风格
        
        Args:
            force_refresh: 是否强制刷新
            
        Returns:
            Dict: 包含3种风格简介的结果
        """
        cache_key = f'bio_{self.user_id}'
        
        if not force_refresh:
            cached = self._get_cached(cache_key)
            if cached:
                return cached
        
        # 获取用户信息
        from app.models.user import User
        user = User.query.get(self.user_id)
        if not user:
            return {'success': False, 'message': '用户不存在'}
        
        # 获取用户最近帖子
        posts = Post.query.filter_by(author_id=self.user_id)\
            .order_by(Post.created_at.desc())\
            .limit(5)\
            .all()
        
        posts_summary = ''
        if posts:
            posts_summary = '最近发帖话题：' + '、'.join([p.title[:20] for p in posts])
        
        prompt = f'''为用户"{user.username}"生成3种风格的个人简介。

用户信息：
- 用户名：{user.username}
- 注册时间：{user.created_at.strftime('%Y年%m月') if user.created_at else '未知'}
- {posts_summary if posts_summary else '暂无发帖记录'}

请生成3种风格的简介，每个不超过100字符，以JSON格式返回：
{{
    "formal": "正式风格的简介",
    "humorous": "幽默风格的简介",
    "literary": "文艺风格的简介"
}}

只返回JSON，不要其他内容。'''

        try:
            result = self.ai_service.generate_simple(prompt)
            result = self._clean_json_response(result)
            data = json.loads(result)
            
            # 确保每个简介不超过100字符
            for key in ['formal', 'humorous', 'literary']:
                if key in data and len(data[key]) > 100:
                    data[key] = data[key][:97] + '...'
            
            data['success'] = True
            data['generated_at'] = datetime.utcnow().isoformat()
            
            self._set_cached(cache_key, data)
            return data
        except json.JSONDecodeError:
            return {'success': False, 'message': '生成结果解析失败'}
        except Exception as e:
            return {'success': False, 'message': f'生成失败: {str(e)}'}
    
    def generate_avatar_description(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        AI生成头像描述 - 生成3个创意描述
        
        Args:
            force_refresh: 是否强制刷新
            
        Returns:
            Dict: 包含3个描述选项的结果
        """
        cache_key = f'avatar_desc_{self.user_id}'
        
        if not force_refresh:
            cached = self._get_cached(cache_key)
            if cached:
                return cached
        
        from app.models.user import User
        user = User.query.get(self.user_id)
        if not user:
            return {'success': False, 'message': '用户不存在'}
        
        # 获取用户帖子主题
        posts = Post.query.filter_by(author_id=self.user_id)\
            .order_by(Post.created_at.desc())\
            .limit(10)\
            .all()
        
        topics = '、'.join([p.title[:15] for p in posts[:5]]) if posts else '暂无'
        
        prompt = f'''为用户"{user.username}"生成3个创意头像描述。

用户信息：
- 用户名：{user.username}
- 常讨论话题：{topics}

请生成3个有创意的头像描述，每个20-50字，以JSON格式返回：
{{
    "descriptions": [
        "描述1",
        "描述2",
        "描述3"
    ]
}}

描述要有创意、有个性，可以是：
- 基于用户名的联想
- 基于用户兴趣的描绘
- 有趣的自我介绍风格

只返回JSON，不要其他内容。'''

        try:
            result = self.ai_service.generate_simple(prompt)
            result = self._clean_json_response(result)
            data = json.loads(result)
            data['success'] = True
            data['generated_at'] = datetime.utcnow().isoformat()
            
            self._set_cached(cache_key, data)
            return data
        except json.JSONDecodeError:
            return {'success': False, 'message': '生成结果解析失败'}
        except Exception as e:
            return {'success': False, 'message': f'生成失败: {str(e)}'}
    
    def get_writing_suggestions(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        AI写作建议 - 基于用户最近帖子
        
        Args:
            force_refresh: 是否强制刷新
            
        Returns:
            Dict: 写作建议
        """
        cache_key = f'suggestions_{self.user_id}'
        
        if not force_refresh:
            cached = self._get_cached(cache_key)
            if cached:
                return cached
        
        posts = Post.query.filter_by(author_id=self.user_id)\
            .order_by(Post.created_at.desc())\
            .limit(5)\
            .all()
        
        if not posts:
            return {
                'success': True,
                'suggestions': [
                    '开始你的第一篇帖子吧！',
                    '分享你的想法和经验',
                    '参与社区讨论'
                ],
                'is_default': True
            }
        
        posts_content = '\n'.join([f'- {p.title}' for p in posts])
        
        prompt = f'''基于用户最近的帖子，给出3条写作建议。

最近帖子：
{posts_content}

请以JSON格式返回：
{{
    "suggestions": [
        "建议1",
        "建议2",
        "建议3"
    ],
    "recommended_topics": ["话题1", "话题2"]
}}

建议要具体、有帮助。只返回JSON。'''

        try:
            result = self.ai_service.generate_simple(prompt)
            result = self._clean_json_response(result)
            data = json.loads(result)
            data['success'] = True
            data['generated_at'] = datetime.utcnow().isoformat()
            
            self._set_cached(cache_key, data)
            return data
        except:
            return {
                'success': True,
                'suggestions': [
                    '尝试写更长的深度文章',
                    '多与其他用户互动',
                    '探索新的话题领域'
                ],
                'is_default': True
            }
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """
        获取AI使用统计
        
        Returns:
            Dict: 使用统计数据
        """
        # 统计总调用次数
        total_calls = APILog.query.filter_by(user_id=self.user_id).count()
        
        # 统计今日调用
        today = datetime.utcnow().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_calls = APILog.query.filter(
            APILog.user_id == self.user_id,
            APILog.created_at >= today_start
        ).count()
        
        # 统计本月调用
        month_start = today.replace(day=1)
        month_calls = APILog.query.filter(
            APILog.user_id == self.user_id,
            APILog.created_at >= datetime.combine(month_start, datetime.min.time())
        ).count()
        
        # 统计token消耗
        total_tokens = db.session.query(db.func.sum(APILog.tokens_used))\
            .filter(APILog.user_id == self.user_id)\
            .scalar() or 0
        
        return {
            'success': True,
            'total_calls': total_calls,
            'today_calls': today_calls,
            'month_calls': month_calls,
            'total_tokens': total_tokens,
            'stats_at': datetime.utcnow().isoformat()
        }
    
    def _get_cached(self, key: str) -> Optional[Dict[str, Any]]:
        """获取缓存的内容"""
        daily = AIDailyContent.query.filter_by(content_type=key).first()
        if daily:
            # 检查是否在24小时内
            if daily.created_at and (datetime.utcnow() - daily.created_at).total_seconds() < CACHE_HOURS * 3600:
                try:
                    return json.loads(daily.content)
                except:
                    pass
        return None
    
    def _set_cached(self, key: str, data: Dict[str, Any]) -> None:
        """设置缓存"""
        content = json.dumps(data, ensure_ascii=False)
        daily = AIDailyContent.query.filter_by(content_type=key).first()
        if daily:
            daily.content = content
            daily.created_at = datetime.utcnow()
        else:
            daily = AIDailyContent(content_type=key, content=content)
            db.session.add(daily)
        db.session.commit()
    
    def _clean_json_response(self, response: str) -> str:
        """清理JSON响应（移除markdown代码块等）"""
        response = response.strip()
        if response.startswith('```'):
            lines = response.split('\n')
            response = '\n'.join(lines[1:])
        if response.endswith('```'):
            response = response.rsplit('```', 1)[0]
        return response.strip()


def get_profile_ai_service(user_id: int) -> ProfileAIService:
    """获取个人中心AI服务实例"""
    return ProfileAIService(user_id)
