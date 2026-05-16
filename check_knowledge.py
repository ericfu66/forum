"""
知识库诊断和修复脚本
检查向量数据状态并提供修复选项
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

def check_knowledge():
    """检查知识库状态"""
    from app import create_app
    from app.models.post_knowledge import PostKnowledge
    from app.models.custom_knowledge import CustomKnowledge
    from app.extensions import db
    
    app = create_app()
    
    with app.app_context():
        # 统计信息
        total = PostKnowledge.query.count()
        print(f"\n=== 知识库诊断 ===")
        print(f"帖子知识条目数: {total}")
        
        custom_total = CustomKnowledge.query.filter_by(is_active=True).count()
        print(f"自定义知识条目数: {custom_total}")
        
        if total == 0 and custom_total == 0:
            print("❌ 知识库为空，请先添加帖子到知识库")
            return
        
        # 检查有向量的条目
        with_embedding = PostKnowledge.query.filter(
            PostKnowledge.embedding.isnot(None),
            PostKnowledge.embedding != ''
        ).count()
        print(f"\n帖子知识 - 有向量: {with_embedding}, 无向量: {total - with_embedding}")
        
        custom_with_embedding = CustomKnowledge.query.filter(
            CustomKnowledge.is_active == True,
            CustomKnowledge.embedding.isnot(None),
            CustomKnowledge.embedding != ''
        ).count()
        print(f"自定义知识 - 有向量: {custom_with_embedding}, 无向量: {custom_total - custom_with_embedding}")
        
        # 检查向量数据格式
        print(f"\n=== 向量数据检查 ===")
        sample = PostKnowledge.query.filter(
            PostKnowledge.embedding.isnot(None)
        ).first()
        
        if sample:
            print(f"样本条目 ID: {sample.id}, 帖子ID: {sample.post_id}")
            print(f"标题: {sample.title[:50]}...")
            
            # 检查 embedding 字段
            raw_embedding = sample.embedding
            if raw_embedding:
                print(f"embedding 字段长度: {len(raw_embedding)} 字符")
                print(f"embedding 前100字符: {raw_embedding[:100]}...")
                
                # 尝试解析
                vec = sample.get_embedding_vector()
                if vec:
                    print(f"✅ 向量解析成功，维度: {len(vec)}")
                else:
                    print(f"❌ 向量解析失败")
            else:
                print(f"❌ embedding 字段为空")
        else:
            print("❌ 没有找到有向量的帖子条目")
            
            # 检查是否有条目但没有向量
            any_entry = PostKnowledge.query.first()
            if any_entry:
                print(f"\n发现条目但无向量:")
                print(f"  ID: {any_entry.id}, 帖子ID: {any_entry.post_id}")
                print(f"  标题: {any_entry.title[:50]}...")
                print(f"  embedding 字段: {repr(any_entry.embedding)[:100]}")
        
        # 检查 NULL vs 空字符串
        print(f"\n=== NULL vs 空字符串检查 ===")
        null_count = PostKnowledge.query.filter(
            PostKnowledge.embedding.is_(None)
        ).count()
        empty_str_count = PostKnowledge.query.filter(
            PostKnowledge.embedding == ''
        ).count()
        print(f"embedding 为 NULL: {null_count}")
        print(f"embedding 为空字符串: {empty_str_count}")
        
        # 建议
        print(f"\n=== 建议 ===")
        if with_embedding == 0 and custom_with_embedding == 0:
            print("⚠️ 所有条目都没有向量，需要重新向量化")
            print("运行: python check_knowledge.py --revectorize")
        elif (total - with_embedding) > 0 or (custom_total - custom_with_embedding) > 0:
            missing = (total - with_embedding) + (custom_total - custom_with_embedding)
            print(f"⚠️ 有 {missing} 条记录没有向量")
            print("运行: python check_knowledge.py --revectorize-missing")


def revectorize_all():
    """重新向量化所有条目"""
    from app import create_app
    from app.models.post_knowledge import PostKnowledge
    from app.models.custom_knowledge import CustomKnowledge
    from app.services.embedding_service import embed_text
    from app.extensions import db
    
    app = create_app()
    
    with app.app_context():
        print("\n=== 开始重新向量化 ===")
        
        # 处理帖子知识
        post_entries = PostKnowledge.query.all()
        print(f"帖子知识条目: {len(post_entries)}")
        
        success = 0
        failed = 0
        
        for entry in post_entries:
            text = f"{entry.title}\n{entry.content}"
            try:
                embedding = embed_text(text)
                if embedding:
                    entry.set_embedding_vector(embedding)
                    db.session.commit()
                    success += 1
                    print(f"  ✓ 帖子 {entry.post_id}: {entry.title[:30]}...")
                else:
                    failed += 1
                    print(f"  ✗ 帖子 {entry.post_id}: 向量化返回空")
            except Exception as e:
                failed += 1
                print(f"  ✗ 帖子 {entry.post_id}: {e}")
        
        print(f"\n帖子知识: 成功 {success}, 失败 {failed}")
        
        # 处理自定义知识
        custom_entries = CustomKnowledge.query.filter_by(is_active=True).all()
        print(f"\n自定义知识条目: {len(custom_entries)}")
        
        custom_success = 0
        custom_failed = 0
        
        for entry in custom_entries:
            text = f"{entry.title}\n{entry.content}"
            try:
                embedding = embed_text(text)
                if embedding:
                    entry.set_embedding_vector(embedding)
                    db.session.commit()
                    custom_success += 1
                    print(f"  ✓ 自定义 {entry.id}: {entry.title[:30]}...")
                else:
                    custom_failed += 1
                    print(f"  ✗ 自定义 {entry.id}: 向量化返回空")
            except Exception as e:
                custom_failed += 1
                print(f"  ✗ 自定义 {entry.id}: {e}")
        
        print(f"\n自定义知识: 成功 {custom_success}, 失败 {custom_failed}")
        print(f"\n=== 向量化完成 ===")


def revectorize_missing():
    """只向量化缺失向量的条目"""
    from app import create_app
    from app.models.post_knowledge import PostKnowledge
    from app.services.embedding_service import embed_text
    from app.extensions import db
    
    app = create_app()
    
    with app.app_context():
        entries = PostKnowledge.get_entries_without_embeddings()
        print(f"\n找到 {len(entries)} 条缺失向量的记录")
        
        success = 0
        failed = 0
        
        for entry in entries:
            text = f"{entry.title}\n{entry.content}"
            try:
                embedding = embed_text(text)
                if embedding:
                    entry.set_embedding_vector(embedding)
                    db.session.commit()
                    success += 1
                    print(f"  ✓ {entry.post_id}: {entry.title[:30]}...")
                else:
                    failed += 1
                    print(f"  ✗ {entry.post_id}: 向量化失败")
            except Exception as e:
                failed += 1
                print(f"  ✗ {entry.post_id}: {e}")
        
        print(f"\n完成! 成功: {success}, 失败: {failed}")


def test_search():
    """测试向量搜索"""
    from app import create_app
    from app.services.knowledge_service import search_similar_knowledge, get_relevant_knowledge
    
    app = create_app()
    
    with app.app_context():
        query = input("\n输入测试查询 (或回车使用默认): ").strip()
        if not query:
            query = "论坛功能"
        
        print(f"\n测试查询: {query}")
        print("=" * 50)
        
        # 测试向量搜索
        print("\n1. 向量搜索结果:")
        results = search_similar_knowledge(query, limit=5, threshold=0.3)
        if results:
            for knowledge, score in results:
                print(f"  [{score:.4f}] {knowledge.title[:40]}...")
        else:
            print("  无结果")
        
        # 测试完整知识获取
        print("\n2. 知识上下文:")
        context = get_relevant_knowledge(query)
        if context:
            print(f"  长度: {len(context)} 字符")
            print(f"  预览: {context[:200]}...")
        else:
            print("  无上下文")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == '--revectorize':
            revectorize_all()
        elif sys.argv[1] == '--revectorize-missing':
            revectorize_missing()
        elif sys.argv[1] == '--test':
            test_search()
        else:
            print("用法:")
            print("  python check_knowledge.py           # 诊断")
            print("  python check_knowledge.py --revectorize        # 重新向量化所有")
            print("  python check_knowledge.py --revectorize-missing # 只向量化缺失的")
            print("  python check_knowledge.py --test    # 测试搜索")
    else:
        check_knowledge()
