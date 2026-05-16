"""
AI小说对话模型
存储用户的小说RP对话
"""
from app.extensions import db
from sqlalchemy.orm.attributes import flag_modified
from datetime import datetime
import json


class NovelDialog(db.Model):
    """AI小说对话模型"""
    __tablename__ = 'novel_dialogs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), default='新故事')
    character_id = db.Column(db.Integer, db.ForeignKey('novel_characters.id'), nullable=True)
    
    # 预设配置（JSON存储启用的条目）
    preset_config = db.Column(db.JSON, default=dict)
    
    # 对话消息
    messages = db.Column(db.JSON, default=list)
    
    # 用户自定义的persona描述
    user_persona = db.Column(db.Text, default='')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关联
    character = db.relationship('NovelCharacter', backref='dialogs')

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'character_id': self.character_id,
            'character': self.character.to_dict() if self.character else None,
            'preset_config': self.preset_config or {},
            'messages': self.messages or [],
            'user_persona': self.user_persona,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def create(user_id, title='', character_id=None, preset_config=None, user_persona=''):
        """创建新对话"""
        dialog = NovelDialog(
            user_id=user_id,
            title=title or '新故事',
            character_id=character_id,
            preset_config=preset_config or {},
            user_persona=user_persona
        )
        db.session.add(dialog)
        db.session.commit()
        return dialog

    @staticmethod
    def find_by_id(dialog_id):
        """通过ID查找对话"""
        return NovelDialog.query.get(dialog_id)

    @staticmethod
    def find_by_user(user_id, page=1, per_page=20):
        """获取用户的对话列表"""
        pagination = NovelDialog.query.filter_by(user_id=user_id)\
            .order_by(NovelDialog.updated_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        return pagination.items, pagination.total

    def add_message(self, role, content):
        """添加消息"""
        message = {
            'role': role,
            'content': content,
            'timestamp': datetime.utcnow().isoformat()
        }
        if self.messages is None:
            self.messages = []
        new_messages = list(self.messages)
        new_messages.append(message)
        self.messages = new_messages
        self.updated_at = datetime.utcnow()

        # 更新标题
        if role == 'user' and (not self.title or self.title == '新故事'):
            self.title = content[:30] + ('...' if len(content) > 30 else '')

        flag_modified(self, 'messages')
        db.session.commit()

    def get_messages_for_api(self):
        """获取用于API调用的消息格式"""
        return [{'role': m['role'], 'content': m['content']} for m in (self.messages or [])]

    def remove_last_assistant_message(self):
        """删除最后一条AI消息（用于重新生成）"""
        if not self.messages:
            return False
        
        new_messages = list(self.messages)
        for i in range(len(new_messages) - 1, -1, -1):
            if new_messages[i].get('role') == 'assistant':
                new_messages.pop(i)
                self.messages = new_messages
                self.updated_at = datetime.utcnow()
                flag_modified(self, 'messages')
                db.session.commit()
                return True
        return False

    def update_preset_config(self, config):
        """更新预设配置"""
        self.preset_config = config
        self.updated_at = datetime.utcnow()
        flag_modified(self, 'preset_config')
        db.session.commit()


class NovelCharacter(db.Model):
    """小说角色模型"""
    __tablename__ = 'novel_characters'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    avatar = db.Column(db.String(10), default='👧')  # emoji头像
    avatar_url = db.Column(db.String(500), default='')  # 图片头像URL
    description = db.Column(db.Text, default='')  # 角色描述
    personality = db.Column(db.Text, default='')  # 性格设定
    scenario = db.Column(db.Text, default='')  # 场景设定
    first_message = db.Column(db.Text, default='')  # 开场白
    example_dialogs = db.Column(db.Text, default='')  # 示例对话
    
    # 正则表达式规则（JSON存储）
    regex_rules = db.Column(db.JSON, default=list)
    
    # 是否为系统预设角色
    is_system = db.Column(db.Boolean, default=False)
    # 创建者（用户自定义角色）
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'avatar': self.avatar,
            'avatar_url': self.avatar_url,
            'description': self.description,
            'personality': self.personality,
            'scenario': self.scenario,
            'first_message': self.first_message,
            'example_dialogs': self.example_dialogs,
            'regex_rules': self.regex_rules or [],
            'is_system': self.is_system,
            'created_by': self.created_by,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    @staticmethod
    def create(**kwargs):
        """创建角色"""
        character = NovelCharacter(**kwargs)
        db.session.add(character)
        db.session.commit()
        return character

    @staticmethod
    def get_system_characters():
        """获取系统预设角色"""
        return NovelCharacter.query.filter_by(is_system=True, is_active=True).all()

    @staticmethod
    def get_user_characters(user_id):
        """获取用户自定义角色"""
        return NovelCharacter.query.filter_by(created_by=user_id, is_active=True).all()

    @staticmethod
    def init_default_characters():
        """初始化默认角色（青梅竹马）"""
        # 检查是否已存在
        if NovelCharacter.query.filter_by(name='林晓雨', is_system=True).first():
            return
        
        # 青梅竹马角色
        NovelCharacter.create(
            name='林晓雨',
            avatar='👧',
            is_system=True,
            description='''林晓雨，22岁，你从小一起长大的青梅竹马。
她有着一头乌黑的长发，常常扎成马尾，明亮的眼睛里总是带着温柔的笑意。
身高165cm，身材匀称，喜欢穿简单舒适的衣服。
目前是大学四年级学生，主修文学专业，喜欢阅读和写作。
性格温柔体贴，但有时也会有些小任性，对你有着特殊的感情却一直没有说出口。''',
            personality='''温柔体贴、善解人意、偶尔小任性
对{{user}}有着深藏的感情，会不自觉地关心和照顾
喜欢阅读、写作、烹饪
有些害羞，但在{{user}}面前会比较放松
会吃醋但不会直接表现出来
说话温柔，偶尔会撒娇''',
            scenario='''你和林晓雨是从小一起长大的青梅竹马，两家是邻居。
从幼儿园到高中一直是同班同学，大学虽然不在同一所学校，但经常联系。
现在是周末，晓雨来找你一起出去玩。''',
            first_message='''*轻轻敲了敲你的房门，声音带着一丝期待*

"{{user}}，在家吗？今天天气这么好，我们出去走走吧~"

*门开了，看到你的瞬间，嘴角不自觉地上扬*

"嘿嘿，我就知道你在家。快点收拾一下，我们去公园逛逛？听说那边的樱花开了呢。"

*说着，眼睛亮晶晶地看着你，马尾随着她的动作轻轻晃动*''',
            example_dialogs='''{{user}}: 晓雨，你今天怎么这么早就来了？
{{char}}: *微微红了脸* "才...才没有很早啦，我只是刚好路过而已..."
*低下头，手指不自觉地绞着衣角*
"而且...而且我想早点见到你嘛..."
*声音越来越小，最后几乎听不见*

{{user}}: 你饿了吗？我给你做点吃的？
{{char}}: *眼睛一亮* "真的吗？那我要吃你做的蛋炒饭！"
*开心地跟在你身后进了厨房*
"我来帮你打下手吧，虽然我厨艺不太好...但是我可以帮你洗菜！"
*挽起袖子，一副跃跃欲试的样子*'''
        )


class NovelUserPreset(db.Model):
    """用户自定义预设条目"""
    __tablename__ = 'novel_user_presets'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    key = db.Column(db.String(100), nullable=False)  # 预设key
    name = db.Column(db.String(200), nullable=False)  # 显示名称
    role = db.Column(db.String(20), default='system')  # user/assistant/system
    content = db.Column(db.Text, nullable=False)  # 预设内容
    enabled = db.Column(db.Boolean, default=True)  # 默认是否启用
    order_index = db.Column(db.Integer, default=100)  # 排序索引
    is_override = db.Column(db.Boolean, default=False)  # 是否是对系统预设的覆盖
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'key': self.key,
            'name': self.name,
            'role': self.role,
            'content': self.content,
            'enabled': self.enabled,
            'order_index': self.order_index,
            'required': False,  # 用户预设都不是必需的
            'is_custom': not self.is_override,
            'is_override': self.is_override,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    @staticmethod
    def get_user_presets(user_id):
        """获取用户的自定义预设（不包括覆盖）"""
        return NovelUserPreset.query.filter_by(
            user_id=user_id, is_active=True, is_override=False
        ).order_by(NovelUserPreset.order_index).all()

    @staticmethod
    def get_user_overrides(user_id):
        """获取用户对系统预设的覆盖"""
        return NovelUserPreset.query.filter_by(
            user_id=user_id, is_active=True, is_override=True
        ).all()

    @staticmethod
    def get_override(user_id, key):
        """获取用户对特定系统预设的覆盖"""
        return NovelUserPreset.query.filter_by(
            user_id=user_id, key=key, is_override=True, is_active=True
        ).first()

    @staticmethod
    def create(user_id, key, name, role, content, enabled=True, order_index=100, is_override=False):
        """创建用户预设"""
        preset = NovelUserPreset(
            user_id=user_id,
            key=key,
            name=name,
            role=role,
            content=content,
            enabled=enabled,
            order_index=order_index,
            is_override=is_override
        )
        db.session.add(preset)
        db.session.commit()
        return preset


class NovelPresetProfile(db.Model):
    """预设配置文件 - 用于保存和切换不同的预设组合"""
    __tablename__ = 'novel_preset_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)  # 配置文件名称
    description = db.Column(db.String(500))  # 描述
    preset_config = db.Column(db.Text, default='{}')  # 预设开关配置 JSON
    custom_presets = db.Column(db.Text, default='[]')  # 自定义预设列表 JSON
    regex_rules = db.Column(db.Text, default='[]')  # 正则表达式规则 JSON
    is_default = db.Column(db.Boolean, default=False)  # 是否为默认配置
    include_system_presets = db.Column(db.Boolean, default=True)  # 是否包含系统预设
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_preset_config(self):
        """获取预设配置"""
        import json
        try:
            return json.loads(self.preset_config or '{}')
        except:
            return {}

    def set_preset_config(self, config):
        """设置预设配置"""
        import json
        self.preset_config = json.dumps(config, ensure_ascii=False)

    def get_custom_presets(self):
        """获取自定义预设列表"""
        import json
        try:
            return json.loads(self.custom_presets or '[]')
        except:
            return []

    def set_custom_presets(self, presets):
        """设置自定义预设列表"""
        import json
        self.custom_presets = json.dumps(presets, ensure_ascii=False)

    def get_regex_rules(self):
        """获取正则表达式规则"""
        import json
        try:
            return json.loads(self.regex_rules or '[]')
        except:
            return []

    def set_regex_rules(self, rules):
        """设置正则表达式规则"""
        import json
        self.regex_rules = json.dumps(rules, ensure_ascii=False)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'description': self.description,
            'preset_config': self.get_preset_config(),
            'custom_presets': self.get_custom_presets(),
            'regex_rules': self.get_regex_rules(),
            'is_default': self.is_default,
            'include_system_presets': self.include_system_presets,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def get_user_profiles(user_id):
        """获取用户的所有预设配置文件"""
        return NovelPresetProfile.query.filter_by(
            user_id=user_id, is_active=True
        ).order_by(NovelPresetProfile.created_at.desc()).all()

    @staticmethod
    def get_default_profile(user_id):
        """获取用户的默认配置文件"""
        return NovelPresetProfile.query.filter_by(
            user_id=user_id, is_default=True, is_active=True
        ).first()

    @staticmethod
    def create(user_id, name, description='', preset_config=None, custom_presets=None, 
               regex_rules=None, include_system_presets=True, is_default=False):
        """创建预设配置文件"""
        import json
        profile = NovelPresetProfile(
            user_id=user_id,
            name=name,
            description=description,
            preset_config=json.dumps(preset_config or {}, ensure_ascii=False),
            custom_presets=json.dumps(custom_presets or [], ensure_ascii=False),
            regex_rules=json.dumps(regex_rules or [], ensure_ascii=False),
            include_system_presets=include_system_presets,
            is_default=is_default
        )
        db.session.add(profile)
        db.session.commit()
        return profile
