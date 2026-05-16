# 模型包
from app.extensions import db
from .user import User
from .post import Post
from .comment import Comment
from .board import Board
from .ai_dialog import AIDialog
from .like import Like
from .api_log import APILog
from .config_history import ConfigHistory
from .post_knowledge import PostKnowledge
from .ai_daily import AIDailyContent
from .moderation_log import ModerationLog
from .message import Message
from .custom_assistant import CustomAssistant
from .user_image import UserImage
from .user_settings import UserSettings
from .custom_knowledge import CustomKnowledge
from .novel_dialog import NovelDialog, NovelCharacter, NovelUserPreset, NovelPresetProfile

__all__ = ['db', 'User', 'Post', 'Comment', 'Board', 'AIDialog', 'Like', 'APILog', 'ConfigHistory', 'PostKnowledge', 'AIDailyContent', 'ModerationLog', 'Message', 'CustomAssistant', 'UserImage', 'UserSettings', 'CustomKnowledge', 'NovelDialog', 'NovelCharacter', 'NovelUserPreset', 'NovelPresetProfile']
