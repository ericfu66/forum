"""
配置热重载服务
支持运行时修改.env配置并自动重载
"""
import os
import re
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from flask import current_app
from dotenv import load_dotenv
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict


# AI模块配置默认值
AI_MODULE_DEFAULTS = {
    'use_global': True,
    'api_base': '',
    'api_key': '',
    'model': '',
    'max_tokens': 2000,
    'temperature': 0.7
}

# AI全局配置默认值
AI_GLOBAL_DEFAULTS = {
    'api_base': 'https://api.openai.com/v1',
    'api_key': '',
    'model': 'gpt-4',
    'max_tokens': 2000,
    'temperature': 0.7
}

# 各模块特定默认值
AI_MODULE_SPECIFIC_DEFAULTS = {
    'moderation': {
        'use_global': True,
        'api_base': '',
        'api_key': '',
        'model': '',
        'max_tokens': 1000,
        'temperature': 0.3
    },
    'chat': {
        'use_global': True,
        'api_base': '',
        'api_key': '',
        'model': '',
        'max_tokens': 4000,
        'temperature': 0.7
    },
    'write': {
        'use_global': True,
        'api_base': '',
        'api_key': '',
        'model': '',
        'max_tokens': 8000,
        'temperature': 0.8
    },
    'roast': {
        'use_global': True,
        'api_base': '',
        'api_key': '',
        'model': '',
        'max_tokens': 500,
        'temperature': 0.9
    },
    'image': {
        'use_global': False,
        'api_base': 'https://api.siliconflow.cn/v1',
        'api_key': '',
        'model': 'Kwai-Kolors/Kolors',
        'default_size': '1024x1024',
        'num_inference_steps': 20,
        'guidance_scale': 7.5
    },
    'vision': {
        'use_global': False,
        'api_base': 'https://api.siliconflow.cn/v1',
        'api_key': '',
        'model': 'Qwen/Qwen2-VL-72B-Instruct',
        'default_detail': 'high'
    }
}

# 配置项Schema定义
CONFIG_SCHEMA = {
    'site': {
        'title': '站点配置',
        'icon': '🏠',
        'source': 'json',
        'section': 'site',
        'fields': {
            'name': {'type': 'text', 'label': '站点名称', 'required': True, 'default': '卢湾高级中学AI论坛'},
            'description': {'type': 'text', 'label': '站点描述', 'default': ''},
            'keywords': {'type': 'text', 'label': '关键词（逗号分隔）', 'default': ''},
            'logo': {'type': 'text', 'label': 'Logo路径', 'default': '/static/images/logo.png'},
        }
    },
    'pagination': {
        'title': '分页配置',
        'icon': '📄',
        'source': 'json',
        'section': 'pagination',
        'fields': {
            'posts_per_page': {'type': 'number', 'label': '每页帖子数', 'min': 5, 'max': 100, 'default': 20},
            'comments_per_page': {'type': 'number', 'label': '每页评论数', 'min': 10, 'max': 200, 'default': 50},
            'users_per_page': {'type': 'number', 'label': '每页用户数', 'min': 10, 'max': 100, 'default': 30},
        }
    },
    'features': {
        'title': '功能开关',
        'icon': '⚙️',
        'source': 'json',
        'section': 'features',
        'fields': {
            'registration_open': {'type': 'boolean', 'label': '开放注册', 'default': True},
            'guest_posting': {'type': 'boolean', 'label': '游客发帖', 'default': False},
            'ai_features_enabled': {'type': 'boolean', 'label': 'AI功能总开关', 'default': True},
            'ai_novel_enabled': {'type': 'boolean', 'label': 'AI小说功能', 'default': True},
        }
    },
    'ai_global': {
        'title': 'AI全局配置 (OpenAI协议)',
        'icon': '🤖',
        'source': 'json',
        'section': 'ai_global',
        'fields': {
            'api_base': {'type': 'text', 'label': 'API地址', 'required': True, 'default': 'https://api.openai.com/v1'},
            'api_key': {'type': 'password', 'label': 'API密钥', 'required': True, 'default': ''},
            'model': {'type': 'text', 'label': '模型名称', 'required': True, 'default': 'gpt-4'},
            'max_tokens': {'type': 'number', 'label': '最大Token数', 'min': 100, 'max': 32000, 'default': 2000},
            'temperature': {'type': 'number', 'label': '温度参数', 'min': 0, 'max': 2, 'step': 0.1, 'default': 0.7},
        }
    },
    'ai_modules': {
        'title': 'AI模块配置',
        'icon': '🔧',
        'source': 'json',
        'section': 'ai_modules',
        'is_module_config': True,
        'modules': {
            'moderation': {
                'title': 'AI审核',
                'icon': '🛡️',
                'fields': {
                    'use_global': {'type': 'boolean', 'label': '使用全局配置', 'default': True},
                    'api_base': {'type': 'text', 'label': 'API地址', 'default': ''},
                    'api_key': {'type': 'password', 'label': 'API密钥', 'default': ''},
                    'model': {'type': 'text', 'label': '模型名称', 'default': ''},
                    'max_tokens': {'type': 'number', 'label': '最大Token数', 'min': 100, 'max': 32000, 'default': 1000},
                    'temperature': {'type': 'number', 'label': '温度参数', 'min': 0, 'max': 2, 'step': 0.1, 'default': 0.3},
                }
            },
            'chat': {
                'title': 'AI对话',
                'icon': '💬',
                'fields': {
                    'use_global': {'type': 'boolean', 'label': '使用全局配置', 'default': True},
                    'api_base': {'type': 'text', 'label': 'API地址', 'default': ''},
                    'api_key': {'type': 'password', 'label': 'API密钥', 'default': ''},
                    'model': {'type': 'text', 'label': '模型名称', 'default': ''},
                    'max_tokens': {'type': 'number', 'label': '最大Token数', 'min': 100, 'max': 32000, 'default': 4000},
                    'temperature': {'type': 'number', 'label': '温度参数', 'min': 0, 'max': 2, 'step': 0.1, 'default': 0.7},
                }
            },
            'write': {
                'title': 'AI写稿',
                'icon': '✍️',
                'fields': {
                    'use_global': {'type': 'boolean', 'label': '使用全局配置', 'default': True},
                    'api_base': {'type': 'text', 'label': 'API地址', 'default': ''},
                    'api_key': {'type': 'password', 'label': 'API密钥', 'default': ''},
                    'model': {'type': 'text', 'label': '模型名称', 'default': ''},
                    'max_tokens': {'type': 'number', 'label': '最大Token数', 'min': 100, 'max': 32000, 'default': 8000},
                    'temperature': {'type': 'number', 'label': '温度参数', 'min': 0, 'max': 2, 'step': 0.1, 'default': 0.8},
                }
            },
            'roast': {
                'title': 'AI吐槽',
                'icon': '🎭',
                'fields': {
                    'use_global': {'type': 'boolean', 'label': '使用全局配置', 'default': True},
                    'api_base': {'type': 'text', 'label': 'API地址', 'default': ''},
                    'api_key': {'type': 'password', 'label': 'API密钥', 'default': ''},
                    'model': {'type': 'text', 'label': '模型名称', 'default': ''},
                    'max_tokens': {'type': 'number', 'label': '最大Token数', 'min': 100, 'max': 32000, 'default': 500},
                    'temperature': {'type': 'number', 'label': '温度参数', 'min': 0, 'max': 2, 'step': 0.1, 'default': 0.9},
                }
            },
            'image': {
                'title': '图片生成',
                'icon': '🎨',
                'fields': {
                    'use_global': {'type': 'boolean', 'label': '使用全局配置', 'default': False},
                    'api_base': {'type': 'text', 'label': '主API地址', 'default': 'https://api.siliconflow.cn/v1'},
                    'api_key': {'type': 'password', 'label': '主API密钥', 'default': ''},
                    'model': {'type': 'text', 'label': '主API模型', 'default': 'Kwai-Kolors/Kolors'},
                    'available_models': {'type': 'textarea', 'label': '可用模型列表（每行一个模型ID）', 'default': 'Kwai-Kolors/Kolors\nstabilityai/stable-diffusion-3-5-large\nblack-forest-labs/FLUX.1-schnell'},
                    'default_size': {'type': 'text', 'label': '默认尺寸', 'default': '1024x1024'},
                    'num_inference_steps': {'type': 'number', 'label': '推理步数', 'min': 1, 'max': 100, 'default': 20},
                    'guidance_scale': {'type': 'number', 'label': '引导系数', 'min': 0, 'max': 20, 'step': 0.5, 'default': 7.5},
                    'fallback_api_base': {'type': 'text', 'label': '备用API地址', 'default': 'https://api.siliconflow.cn/v1'},
                    'fallback_api_key': {'type': 'password', 'label': '备用API密钥', 'default': ''},
                    'fallback_model': {'type': 'text', 'label': '备用API模型', 'default': 'Kwai-Kolors/Kolors'},
                    'daily_limit': {'type': 'number', 'label': '普通用户每日限制', 'min': 1, 'max': 100, 'default': 5},
                }
            },
            'vision': {
                'title': '视觉理解',
                'icon': '👁️',
                'fields': {
                    'use_global': {'type': 'boolean', 'label': '使用全局配置', 'default': False},
                    'api_base': {'type': 'text', 'label': 'API地址', 'default': 'https://api.siliconflow.cn/v1'},
                    'api_key': {'type': 'password', 'label': 'API密钥', 'default': ''},
                    'model': {'type': 'text', 'label': '模型名称', 'default': 'Qwen/Qwen2-VL-72B-Instruct'},
                    'default_detail': {
                        'type': 'select', 'label': '默认精度', 'default': 'high',
                        'options': [
                            {'value': 'low', 'label': '低 (快速)'},
                            {'value': 'high', 'label': '高 (详细)'},
                            {'value': 'auto', 'label': '自动'}
                        ]
                    },
                }
            },
        }
    },
    'ai_features': {
        'title': 'AI功能配置',
        'icon': '✨',
        'source': 'env',
        'category': 'ai_features',
        'fields': {
            'AI_ROAST_ENABLED': {'type': 'boolean', 'label': '启用AI吐槽', 'default': True},
            'AI_ROAST_PROBABILITY': {'type': 'number', 'label': '吐槽概率', 'min': 0, 'max': 1, 'step': 0.01, 'default': 0.1},
            'AI_CHAT_ENABLED': {'type': 'boolean', 'label': '启用AI对话', 'default': True},
            'AI_WRITE_ENABLED': {'type': 'boolean', 'label': '启用AI写稿', 'default': True},
            'AI_IMAGE_ENABLED': {'type': 'boolean', 'label': '启用AI绘图', 'default': True},
            'AI_RATE_LIMIT_PER_HOUR': {'type': 'number', 'label': '每小时调用限制', 'min': 1, 'max': 100, 'default': 20},
            'AI_RATE_LIMIT_PER_DAY': {'type': 'number', 'label': '每日调用限制', 'min': 10, 'max': 1000, 'default': 100},
        }
    },
    'ai_moderation': {
        'title': 'AI内容审核',
        'icon': '🛡️',
        'source': 'json',
        'section': 'ai_moderation',
        'fields': {
            'enabled': {'type': 'boolean', 'label': '启用AI审核', 'default': False},
            'sensitivity': {
                'type': 'select', 'label': '审核敏感度', 'default': 'medium',
                'options': [
                    {'value': 'low', 'label': '宽松'},
                    {'value': 'medium', 'label': '中等'},
                    {'value': 'high', 'label': '严格'}
                ]
            },
            'auto_reject_threshold': {'type': 'number', 'label': '自动拒绝阈值', 'min': 0.5, 'max': 1.0, 'step': 0.05, 'default': 0.9},
            'hold_threshold': {'type': 'number', 'label': '人工审核阈值', 'min': 0.3, 'max': 0.9, 'step': 0.05, 'default': 0.6},
            'check_spam': {'type': 'boolean', 'label': '检测垃圾内容', 'default': True},
            'check_inappropriate': {'type': 'boolean', 'label': '检测不当内容', 'default': True},
            'check_sensitive': {'type': 'boolean', 'label': '检测敏感话题', 'default': False},
            'check_provocative': {'type': 'boolean', 'label': '检测引战内容', 'default': False},
        }
    },
    'search': {
        'title': '联网搜索配置',
        'icon': '🔍',
        'source': 'json',
        'section': 'search',
        'fields': {
            'enabled': {'type': 'boolean', 'label': '启用联网搜索', 'default': True},
            'tavily_api_key': {'type': 'password', 'label': 'Tavily API密钥', 'default': ''},
            'max_results': {'type': 'number', 'label': '最大搜索结果数', 'min': 1, 'max': 10, 'default': 5},
            'search_depth': {
                'type': 'select', 'label': '搜索深度',
                'default': 'basic',
                'options': [
                    {'value': 'basic', 'label': '基础 (更快)'},
                    {'value': 'advanced', 'label': '深度 (更全面)'}
                ]
            },
        }
    },
    'petals': {
        'title': '落英特效',
        'icon': '🌸',
        'source': 'json',
        'section': 'petals',
        'fields': {
            'enabled': {'type': 'boolean', 'label': '启用特效', 'default': True},
            'count': {'type': 'number', 'label': '花瓣数量', 'min': 5, 'max': 50, 'default': 12},
            'min_duration': {'type': 'number', 'label': '最小下落时间(秒)', 'min': 5, 'max': 30, 'default': 10},
            'max_duration': {'type': 'number', 'label': '最大下落时间(秒)', 'min': 10, 'max': 60, 'default': 18},
            'theme': {
                'type': 'select', 'label': '主题',
                'default': 'sakura',
                'options': [
                    {'value': 'sakura', 'label': '🌸 樱花'},
                    {'value': 'autumn', 'label': '🍂 秋叶'},
                    {'value': 'snow', 'label': '❄️ 雪花'}
                ]
            },
            'parallax_enabled': {'type': 'boolean', 'label': '视差效果', 'default': True},
        }
    },
    'embedding': {
        'title': '向量化配置 (Embedding)',
        'icon': '🧠',
        'source': 'json',
        'section': 'embedding',
        'fields': {
            'api_base': {'type': 'text', 'label': 'API地址', 'default': 'https://api.siliconflow.cn/v1'},
            'api_key': {'type': 'password', 'label': 'API密钥', 'default': ''},
            'model': {'type': 'text', 'label': '模型名称', 'default': 'BAAI/bge-large-zh-v1.5'},
            'dimensions': {'type': 'number', 'label': '向量维度', 'min': 128, 'max': 4096, 'default': 1024},
            'timeout': {'type': 'number', 'label': '超时时间(秒)', 'min': 5, 'max': 120, 'default': 30},
        }
    },
    'knowledge': {
        'title': '知识库配置',
        'icon': '📚',
        'source': 'json',
        'section': 'knowledge',
        'fields': {
            'search_limit': {'type': 'number', 'label': '搜索结果数量', 'min': 1, 'max': 20, 'default': 5},
            'similarity_threshold': {'type': 'number', 'label': '相似度阈值', 'min': 0, 'max': 1, 'step': 0.05, 'default': 0.5},
            'max_context_chars': {'type': 'number', 'label': '最大上下文字符数', 'min': 1000, 'max': 32000, 'default': 8000},
        }
    },
    'upload': {
        'title': '上传配置',
        'icon': '📤',
        'source': 'env',
        'category': 'upload',
        'fields': {
            'UPLOAD_FOLDER': {'type': 'text', 'label': '上传目录', 'default': 'uploads'},
            'MAX_CONTENT_LENGTH': {'type': 'number', 'label': '最大文件大小(字节)', 'min': 1048576, 'max': 104857600, 'default': 16777216},
        }
    },
}


@dataclass
class ValidationResult:
    """验证结果"""
    valid: bool
    field: str
    message: str = ''


@dataclass
class BatchUpdateResult:
    """批量更新结果"""
    success: bool
    updated_count: int
    errors: List[ValidationResult]
    message: str = ''


class ConfigService:
    """配置管理服务 - 支持热重载"""

    def __init__(self, env_path: str = '.env', config_path: str = 'config.json'):
        # 获取项目根目录
        self.root_path = Path(current_app.root_path).parent if current_app else Path.cwd()
        self.env_path = self.root_path / env_path
        self.config_path = self.root_path / config_path
        self._config_cache = {}

    def get_all_configs(self) -> Dict[str, Any]:
        """
        获取所有配置（合并.env和config.json）
        返回分类后的配置字典
        """
        return {
            'env': self._parse_env_file(),
            'json': self._parse_json_file()
        }

    def _parse_env_file(self) -> Dict[str, Dict[str, str]]:
        """解析.env文件为分类字典"""
        configs = {
            'flask': {},
            'database': {},
            'ai_features': {},
            'upload': {},
            'session': {},
            'other': {}
        }

        if not self.env_path.exists():
            return configs

        with open(self.env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                if '=' in line:
                    # 处理可能包含多个=号的情况
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()

                    # 分类
                    if key.startswith('FLASK_'):
                        configs['flask'][key] = value
                    elif key.startswith('DATABASE_'):
                        configs['database'][key] = value
                    elif key.startswith('AI_'):
                        configs['ai_features'][key] = value
                    elif key.startswith('UPLOAD_') or key.startswith('MAX_CONTENT'):
                        configs['upload'][key] = value
                    elif key.startswith('SESSION_') or key.startswith('PERMANENT_'):
                        configs['session'][key] = value
                    else:
                        configs['other'][key] = value

        return configs

    def _parse_json_file(self) -> Dict[str, Any]:
        """解析config.json文件"""
        if not self.config_path.exists():
            return {}

        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def update_env_config(self, updates: Dict[str, str], category: str = 'other') -> bool:
        """
        更新.env配置

        Args:
            updates: 配置更新字典 {key: value}
            category: 配置分类（用于添加前缀）

        Returns:
            bool: 是否成功
        """
        try:
            # 读取现有内容
            existing_lines = []
            existing_keys = {}

            if self.env_path.exists():
                with open(self.env_path, 'r', encoding='utf-8') as f:
                    existing_lines = f.readlines()

            # 解析现有配置
            for i, line in enumerate(existing_lines):
                if '=' in line and not line.strip().startswith('#'):
                    key, _ = line.split('=', 1)
                    existing_keys[key.strip()] = i

            # 添加前缀
            prefix_map = {
                'flask': 'FLASK_',
                'database': 'DATABASE_',
                'ai_features': 'AI_',
                'upload': 'UPLOAD_',
                'session': 'SESSION_',
            }

            prefix = prefix_map.get(category, '')

            # 更新或添加配置
            for key, value in updates.items():
                full_key = f"{prefix}{key}" if not key.startswith(prefix) else key

                if full_key in existing_keys:
                    # 更新现有配置
                    existing_lines[existing_keys[full_key]] = f"{full_key}={value}\n"
                else:
                    # 添加新配置
                    existing_lines.append(f"{full_key}={value}\n")

            # 写回文件
            with open(self.env_path, 'w', encoding='utf-8') as f:
                f.writelines(existing_lines)

            # 触发热重载
            self._reload_config()

            # 记录变更历史
            self._log_config_change(updates, category)

            return True

        except Exception as e:
            current_app.logger.error(f"Update config failed: {str(e)}")
            return False

    def update_json_config(self, updates: Dict[str, Any], section: str = None) -> bool:
        """
        更新config.json配置

        Args:
            updates: 配置更新字典
            section: 配置节点（如 'site', 'ai_triggers'）

        Returns:
            bool: 是否成功
        """
        try:
            # 读取现有配置
            config = self._parse_json_file()

            # 更新配置
            if section:
                if section not in config:
                    config[section] = {}
                config[section].update(updates)
            else:
                config.update(updates)

            # 写回文件
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

            # 重新加载到Flask配置
            current_app.config['JSON_CONFIG'] = config

            return True

        except Exception as e:
            current_app.logger.error(f"Update JSON config failed: {str(e)}")
            return False

    def _reload_config(self):
        """热重载配置"""
        # 重新加载环境变量
        load_dotenv(self.env_path, override=True)

        # 需要特殊类型转换的配置项
        type_converters = {
            'PERMANENT_SESSION_LIFETIME': lambda v: timedelta(seconds=int(v)),
            'AI_ROAST_PROBABILITY': float,
            'AI_RATE_LIMIT_PER_HOUR': int,
            'AI_RATE_LIMIT_PER_DAY': int,
            'MAX_CONTENT_LENGTH': int,
            'DEBUG': lambda v: v.lower() == 'true',
            'AI_ROAST_ENABLED': lambda v: v.lower() == 'true',
            'AI_CHAT_ENABLED': lambda v: v.lower() == 'true',
            'AI_WRITE_ENABLED': lambda v: v.lower() == 'true',
            'AI_IMAGE_ENABLED': lambda v: v.lower() == 'true',
        }

        # 更新Flask应用配置
        for key, value in os.environ.items():
            if key.isupper() and value:
                # 应用类型转换
                if key in type_converters:
                    try:
                        value = type_converters[key](value)
                    except (ValueError, TypeError) as e:
                        current_app.logger.warning(f"Config type conversion failed for {key}: {e}")
                        continue
                current_app.config[key] = value

        # 重新加载config.json
        current_app.config['JSON_CONFIG'] = self._parse_json_file()

        current_app.logger.info('Configuration reloaded successfully')

    def _log_config_change(self, updates: Dict[str, str], category: str):
        """记录配置变更到数据库"""
        try:
            from flask import g
            from flask_login import current_user
            from app.models.config_history import ConfigHistory

            # 获取当前用户ID
            user_id = None
            if current_user and current_user.is_authenticated:
                user_id = current_user.id

            ConfigHistory.create(
                category=category,
                changes=updates,
                updated_by=user_id
            )

        except Exception as e:
            current_app.logger.error(f"Log config change failed: {str(e)}")

    def get_config_history(self, limit: int = 50) -> list:
        """获取配置变更历史"""
        try:
            from app.models.config_history import ConfigHistory

            history = ConfigHistory.get_recent(limit)
            return [h.to_dict() for h in history]
        except Exception as e:
            current_app.logger.error(f"Get config history failed: {str(e)}")
            return []

    def reset_to_defaults(self) -> bool:
        """重置为默认配置"""
        try:
            # 读取.env.example
            example_path = self.root_path / '.env.example'
            if not example_path.exists():
                return False

            with open(example_path, 'r', encoding='utf-8') as f:
                default_content = f.read()

            # 备份当前配置
            backup_path = self.root_path / f'.env.backup.{int(datetime.now().timestamp())}'
            if self.env_path.exists():
                import shutil
                shutil.copy(self.env_path, backup_path)

            # 写入默认配置
            with open(self.env_path, 'w', encoding='utf-8') as f:
                f.write(default_content)

            # 触发热重载
            self._reload_config()

            return True

        except Exception as e:
            current_app.logger.error(f"Reset config failed: {str(e)}")
            return False

    def get_config_schema(self) -> Dict[str, Any]:
        """获取配置Schema定义"""
        return CONFIG_SCHEMA

    def get_all_configs_structured(self) -> Dict[str, Any]:
        """
        获取结构化的所有配置，包含元数据和当前值
        返回按Schema组织的配置字典
        """
        env_configs = self._parse_env_file()
        json_configs = self._parse_json_file()
        
        result = {}
        
        for category_key, category_schema in CONFIG_SCHEMA.items():
            # 处理模块配置（ai_modules）
            if category_schema.get('is_module_config'):
                category_data = {
                    'title': category_schema['title'],
                    'icon': category_schema['icon'],
                    'source': category_schema['source'],
                    'is_module_config': True,
                    'modules': {}
                }
                
                # 获取JSON中的ai_modules配置
                ai_modules_config = json_configs.get('ai_modules', {})
                
                for module_key, module_schema in category_schema.get('modules', {}).items():
                    module_config = ai_modules_config.get(module_key, {})
                    module_defaults = AI_MODULE_SPECIFIC_DEFAULTS.get(module_key, {})
                    
                    module_data = {
                        'title': module_schema['title'],
                        'icon': module_schema['icon'],
                        'fields': {}
                    }
                    
                    for field_key, field_schema in module_schema['fields'].items():
                        # 获取字段值：优先使用配置值，否则使用默认值
                        default_value = module_defaults.get(field_key, field_schema.get('default', ''))
                        config_value = module_config.get(field_key)
                        
                        if config_value is not None and config_value != '':
                            value = config_value
                        else:
                            value = default_value
                        
                        field_data = {
                            **field_schema,
                            'key': field_key,
                            'value': value,
                        }
                        module_data['fields'][field_key] = field_data
                    
                    category_data['modules'][module_key] = module_data
                
                result[category_key] = category_data
            else:
                # 处理普通配置
                category_data = {
                    'title': category_schema['title'],
                    'icon': category_schema['icon'],
                    'source': category_schema['source'],
                    'fields': {}
                }
                
                for field_key, field_schema in category_schema.get('fields', {}).items():
                    field_data = {
                        **field_schema,
                        'key': field_key,
                        'value': self._get_field_value(category_schema, field_key, env_configs, json_configs),
                    }
                    category_data['fields'][field_key] = field_data
                
                result[category_key] = category_data
        
        return result

    def _get_field_value(self, category_schema: Dict, field_key: str, 
                         env_configs: Dict, json_configs: Dict) -> Any:
        """获取字段的当前值"""
        source = category_schema['source']
        field_schema = category_schema['fields'][field_key]
        default = field_schema.get('default', '')
        
        if source == 'env':
            # 从环境变量配置获取
            env_category = category_schema.get('category', 'other')
            env_data = env_configs.get(env_category, {})
            value = env_data.get(field_key, default)
            
            # 类型转换
            field_type = field_schema.get('type')
            if field_type == 'boolean':
                if isinstance(value, str):
                    return value.lower() in ('true', '1', 'yes')
                return bool(value)
            elif field_type == 'number':
                try:
                    if '.' in str(value):
                        return float(value)
                    return int(value)
                except (ValueError, TypeError):
                    return default
            return value
            
        elif source == 'json':
            # 从JSON配置获取
            section = category_schema.get('section', '')
            section_data = json_configs.get(section, {})
            return section_data.get(field_key, default)
        
        return default

    def validate_config(self, category: str, field_key: str, value: Any) -> ValidationResult:
        """
        验证单个配置项
        
        Args:
            category: 配置分类
            field_key: 字段键名
            value: 字段值
            
        Returns:
            ValidationResult: 验证结果
        """
        if category not in CONFIG_SCHEMA:
            return ValidationResult(valid=False, field=field_key, message=f'未知的配置分类: {category}')
        
        category_schema = CONFIG_SCHEMA[category]
        if field_key not in category_schema['fields']:
            return ValidationResult(valid=False, field=field_key, message=f'未知的配置项: {field_key}')
        
        field_schema = category_schema['fields'][field_key]
        field_type = field_schema.get('type', 'text')
        
        # 必填验证
        if field_schema.get('required') and (value is None or value == ''):
            return ValidationResult(valid=False, field=field_key, message=f'{field_schema.get("label", field_key)} 不能为空')
        
        # 类型验证
        if field_type == 'number' and value is not None and value != '':
            try:
                num_value = float(value)
                min_val = field_schema.get('min')
                max_val = field_schema.get('max')
                
                if min_val is not None and num_value < min_val:
                    return ValidationResult(valid=False, field=field_key, 
                                          message=f'{field_schema.get("label", field_key)} 不能小于 {min_val}')
                if max_val is not None and num_value > max_val:
                    return ValidationResult(valid=False, field=field_key, 
                                          message=f'{field_schema.get("label", field_key)} 不能大于 {max_val}')
            except (ValueError, TypeError):
                return ValidationResult(valid=False, field=field_key, 
                                      message=f'{field_schema.get("label", field_key)} 必须是数字')
        
        elif field_type == 'select':
            options = field_schema.get('options', [])
            valid_values = [opt['value'] for opt in options]
            if value not in valid_values:
                return ValidationResult(valid=False, field=field_key, 
                                      message=f'{field_schema.get("label", field_key)} 值无效')
        
        return ValidationResult(valid=True, field=field_key)

    def batch_update(self, updates: Dict[str, Dict[str, Any]]) -> BatchUpdateResult:
        """
        批量更新配置（原子性操作）
        
        Args:
            updates: {category: {field_key: value, ...}, ...}
                     对于ai_modules: {ai_modules: {module_key: {field_key: value, ...}, ...}}
            
        Returns:
            BatchUpdateResult: 更新结果
        """
        errors = []
        
        # 第一步：验证所有配置（跳过ai_modules的验证，因为它有特殊结构）
        for category, fields in updates.items():
            if category == 'ai_modules':
                # ai_modules有嵌套结构，跳过标准验证
                continue
            for field_key, value in fields.items():
                result = self.validate_config(category, field_key, value)
                if not result.valid:
                    errors.append(result)
        
        # 如果有验证错误，返回失败
        if errors:
            return BatchUpdateResult(
                success=False,
                updated_count=0,
                errors=errors,
                message=f'验证失败: {len(errors)} 个配置项无效'
            )
        
        # 第二步：分类更新
        env_updates = {}  # {category: {key: value}}
        json_updates = {}  # {section: {key: value}}
        
        for category, fields in updates.items():
            # 特殊处理ai_modules
            if category == 'ai_modules':
                # fields是 {module_key: {field_key: value, ...}, ...}
                if 'ai_modules' not in json_updates:
                    # 先读取现有配置
                    existing_config = self._parse_json_file()
                    json_updates['ai_modules'] = existing_config.get('ai_modules', {})
                
                for module_key, module_fields in fields.items():
                    if module_key not in json_updates['ai_modules']:
                        json_updates['ai_modules'][module_key] = {}
                    json_updates['ai_modules'][module_key].update(module_fields)
                continue
            
            if category not in CONFIG_SCHEMA:
                continue
                
            category_schema = CONFIG_SCHEMA[category]
            source = category_schema['source']
            
            if source == 'env':
                env_category = category_schema.get('category', 'other')
                if env_category not in env_updates:
                    env_updates[env_category] = {}
                
                for field_key, value in fields.items():
                    # 布尔值转换为字符串
                    if isinstance(value, bool):
                        value = 'true' if value else 'false'
                    env_updates[env_category][field_key] = str(value)
                    
            elif source == 'json':
                section = category_schema.get('section', '')
                if section not in json_updates:
                    json_updates[section] = {}
                json_updates[section].update(fields)
        
        # 第三步：执行更新
        updated_count = 0
        try:
            # 更新环境变量配置
            for env_category, env_fields in env_updates.items():
                if self.update_env_config(env_fields, env_category):
                    updated_count += len(env_fields)
            
            # 更新JSON配置
            for section, json_fields in json_updates.items():
                if self.update_json_config(json_fields, section):
                    # 对于ai_modules，计算实际更新的字段数
                    if section == 'ai_modules':
                        for module_fields in json_fields.values():
                            if isinstance(module_fields, dict):
                                updated_count += len(module_fields)
                    else:
                        updated_count += len(json_fields)
            
            return BatchUpdateResult(
                success=True,
                updated_count=updated_count,
                errors=[],
                message=f'成功更新 {updated_count} 个配置项'
            )
            
        except Exception as e:
            current_app.logger.error(f"Batch update failed: {str(e)}")
            return BatchUpdateResult(
                success=False,
                updated_count=0,
                errors=[ValidationResult(valid=False, field='', message=str(e))],
                message=f'更新失败: {str(e)}'
            )


def get_config_service() -> ConfigService:
    """获取配置服务实例"""
    return ConfigService()


def get_config_schema() -> Dict[str, Any]:
    """获取配置Schema定义"""
    return CONFIG_SCHEMA


def merge_config_with_defaults(config: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
    """
    合并配置与默认值，确保缺失字段使用默认值填充
    
    Args:
        config: 当前配置字典
        defaults: 默认值字典
        
    Returns:
        合并后的完整配置字典
    """
    result = dict(defaults)  # 从默认值开始
    
    if config is None:
        return result
    
    for key, default_value in defaults.items():
        if key in config:
            config_value = config[key]
            # 如果值是字典，递归合并
            if isinstance(default_value, dict) and isinstance(config_value, dict):
                result[key] = merge_config_with_defaults(config_value, default_value)
            # 如果配置值不为空（非None且非空字符串），使用配置值
            elif config_value is not None and config_value != '':
                result[key] = config_value
            # 否则保持默认值
        # 如果key不在config中，保持默认值（已在result中）
    
    # 添加config中存在但defaults中不存在的键
    for key, value in config.items():
        if key not in defaults:
            result[key] = value
    
    return result


def get_ai_global_config() -> Dict[str, Any]:
    """
    获取AI全局配置，合并默认值
    
    Returns:
        完整的AI全局配置字典
    """
    try:
        config_service = get_config_service()
        json_config = config_service._parse_json_file()
        ai_global = json_config.get('ai_global', {})
        return merge_config_with_defaults(ai_global, AI_GLOBAL_DEFAULTS)
    except Exception:
        return dict(AI_GLOBAL_DEFAULTS)


def get_ai_module_config(module: str) -> Dict[str, Any]:
    """
    获取指定AI模块的配置，合并默认值
    
    Args:
        module: 模块名称 (moderation, chat, write, roast, image, vision)
        
    Returns:
        完整的模块配置字典
    """
    if module not in AI_MODULE_SPECIFIC_DEFAULTS:
        raise ValueError(f"Unknown AI module: {module}")
    
    try:
        config_service = get_config_service()
        json_config = config_service._parse_json_file()
        ai_modules = json_config.get('ai_modules', {})
        module_config = ai_modules.get(module, {})
        
        # 获取模块特定默认值
        module_defaults = AI_MODULE_SPECIFIC_DEFAULTS[module]
        
        return merge_config_with_defaults(module_config, module_defaults)
    except Exception:
        return dict(AI_MODULE_SPECIFIC_DEFAULTS[module])


def get_effective_ai_config(module: str) -> Dict[str, Any]:
    """
    获取模块的有效AI配置（处理use_global逻辑）
    
    如果模块配置use_global=True，返回全局配置
    否则返回模块自身配置
    
    Args:
        module: 模块名称
        
    Returns:
        有效的配置字典，包含api_base, api_key, model, max_tokens, temperature
    """
    module_config = get_ai_module_config(module)
    
    def _safe_int(value, default=2000):
        """安全转换为整数"""
        try:
            return int(value) if value is not None else default
        except (ValueError, TypeError):
            return default
    
    def _safe_float(value, default=0.7):
        """安全转换为浮点数"""
        try:
            return float(value) if value is not None else default
        except (ValueError, TypeError):
            return default
    
    if module_config.get('use_global', True):
        # 使用全局配置
        global_config = get_ai_global_config()
        return {
            'api_base': global_config.get('api_base', ''),
            'api_key': global_config.get('api_key', ''),
            'model': global_config.get('model', ''),
            'max_tokens': _safe_int(global_config.get('max_tokens'), 2000),
            'temperature': _safe_float(global_config.get('temperature'), 0.7),
        }
    else:
        # 使用模块自身配置
        return {
            'api_base': module_config.get('api_base', ''),
            'api_key': module_config.get('api_key', ''),
            'model': module_config.get('model', ''),
            'max_tokens': _safe_int(module_config.get('max_tokens'), 2000),
            'temperature': _safe_float(module_config.get('temperature'), 0.7),
        }


def validate_ai_config(config: Dict[str, Any], require_all: bool = True) -> ValidationResult:
    """
    验证AI配置是否完整有效
    
    Args:
        config: 配置字典
        require_all: 是否要求所有必填字段
        
    Returns:
        ValidationResult: 验证结果
    """
    required_fields = ['api_base', 'api_key', 'model']
    
    if require_all:
        for field in required_fields:
            value = config.get(field)
            if not value or (isinstance(value, str) and not value.strip()):
                field_labels = {
                    'api_base': 'API地址',
                    'api_key': 'API密钥',
                    'model': '模型名称'
                }
                return ValidationResult(
                    valid=False,
                    field=field,
                    message=f'{field_labels.get(field, field)} 不能为空'
                )
    
    # 验证max_tokens范围
    max_tokens = config.get('max_tokens')
    if max_tokens is not None:
        try:
            max_tokens = int(max_tokens)
            if max_tokens < 100 or max_tokens > 32000:
                return ValidationResult(
                    valid=False,
                    field='max_tokens',
                    message='max_tokens 必须在 100-32000 之间'
                )
        except (ValueError, TypeError):
            return ValidationResult(
                valid=False,
                field='max_tokens',
                message='max_tokens 必须是数字'
            )
    
    # 验证temperature范围
    temperature = config.get('temperature')
    if temperature is not None:
        try:
            temperature = float(temperature)
            if temperature < 0 or temperature > 2:
                return ValidationResult(
                    valid=False,
                    field='temperature',
                    message='temperature 必须在 0-2 之间'
                )
        except (ValueError, TypeError):
            return ValidationResult(
                valid=False,
                field='temperature',
                message='temperature 必须是数字'
            )
    
    return ValidationResult(valid=True, field='')



def validate_module_config_on_save(module: str, config: Dict[str, Any]) -> ValidationResult:
    """
    验证模块配置保存时的有效性
    
    当use_global=false时，验证必填字段是否完整
    当use_global=true时，直接通过验证
    
    Args:
        module: 模块名称
        config: 配置字典
        
    Returns:
        ValidationResult: 验证结果
    """
    if module not in AI_MODULE_SPECIFIC_DEFAULTS:
        return ValidationResult(
            valid=False,
            field='module',
            message=f'未知的AI模块: {module}'
        )
    
    use_global = config.get('use_global', True)
    
    # 如果使用全局配置，不需要验证模块自身的必填字段
    if use_global:
        return ValidationResult(valid=True, field='')
    
    # 不使用全局配置时，验证必填字段
    return validate_ai_config(config, require_all=True)
