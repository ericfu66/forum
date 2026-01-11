"""
向量相似度计算工具
提供余弦相似度计算和相似度搜索功能
"""
import math
from typing import List, Tuple, Any, Optional


class SimilarityCalculator:
    """向量相似度计算工具"""
    
    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """
        计算两个向量的余弦相似度
        
        Args:
            vec1: 第一个向量
            vec2: 第二个向量
            
        Returns:
            余弦相似度值，范围 [-1, 1]
            如果任一向量为零向量，返回 0.0
        """
        if not vec1 or not vec2:
            return 0.0
        
        if len(vec1) != len(vec2):
            raise ValueError(f"Vector dimensions must match: {len(vec1)} vs {len(vec2)}")
        
        # 计算点积和模长
        dot_product = 0.0
        norm1 = 0.0
        norm2 = 0.0
        
        for a, b in zip(vec1, vec2):
            dot_product += a * b
            norm1 += a * a
            norm2 += b * b
        
        # 处理零向量
        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0
        
        # 计算余弦相似度
        similarity = dot_product / (math.sqrt(norm1) * math.sqrt(norm2))
        
        # 处理浮点数精度问题，确保结果在 [-1, 1] 范围内
        return max(-1.0, min(1.0, similarity))
    
    @staticmethod
    def batch_cosine_similarity(
        query_vec: List[float], 
        vectors: List[List[float]]
    ) -> List[float]:
        """
        批量计算查询向量与多个向量的相似度
        
        Args:
            query_vec: 查询向量
            vectors: 候选向量列表
            
        Returns:
            相似度列表，与输入向量列表一一对应
        """
        if not query_vec or not vectors:
            return []
        
        return [
            SimilarityCalculator.cosine_similarity(query_vec, vec) 
            for vec in vectors
        ]
    
    @staticmethod
    def find_top_similar(
        query_vec: List[float],
        candidates: List[Tuple[Any, List[float]]],
        top_k: int = 5,
        threshold: float = 0.0
    ) -> List[Tuple[Any, float]]:
        """
        找出最相似的 top-k 个候选
        
        Args:
            query_vec: 查询向量
            candidates: [(item, vector), ...] 候选列表
            top_k: 返回数量
            threshold: 相似度阈值（低于此值的结果会被过滤）
            
        Returns:
            [(item, similarity), ...] 按相似度降序排列
        """
        if not query_vec or not candidates:
            return []
        
        # 计算所有候选的相似度
        scored_candidates: List[Tuple[Any, float]] = []
        for item, vec in candidates:
            if vec:  # 跳过空向量
                similarity = SimilarityCalculator.cosine_similarity(query_vec, vec)
                if similarity >= threshold:
                    scored_candidates.append((item, similarity))
        
        # 按相似度降序排序
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        
        # 返回 top-k
        return scored_candidates[:top_k]


# 便捷函数
def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """计算两个向量的余弦相似度"""
    return SimilarityCalculator.cosine_similarity(vec1, vec2)


def find_top_similar(
    query_vec: List[float],
    candidates: List[Tuple[Any, List[float]]],
    top_k: int = 5,
    threshold: float = 0.0
) -> List[Tuple[Any, float]]:
    """找出最相似的 top-k 个候选"""
    return SimilarityCalculator.find_top_similar(query_vec, candidates, top_k, threshold)
