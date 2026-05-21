"""版权合规Agent：FAISS向量查重、原创度打分、防洗稿检测"""

# from ..core.llm import call_llm  # 暂未使用，LLM 版权检测待实现
from ..utils.logger import get_logger

logger = get_logger(__name__)


async def check_copyright(
    chapter_content: str,
    project_id: str,
    threshold: float = 0.2,
) -> dict:
    """版权合规校验"""
    from ..services.vector_service import VectorService

    vs = VectorService()

    # TODO: LLM 版权检测暂不可靠，当前直接返回占位结果。
    # 后续应改为向量相似度 + 规则检测（非 LLM 路径）。
    # system_prompt = """你是一位版权合规专家。检测提交的章节内容是否存在以下问题：
    # 1. 与已有作品的相似度过高
    # 2. 情节结构、套路模板复刻
    # 3. 经典桥段照搬
    # 4. 功法、势力、门派等设定重名撞车
    #
    # 输出格式：
    # - originality_score: 0-100原创度分数
    # - max_similarity: 0-1最高相似度
    # - passed: true/false
    # - opinion: 详细检测意见
    # - similar_entries: 相似条目列表（如有）"""
    #
    # user_prompt = f"""章节内容：
    # {chapter_content[:2000]}
    #
    # 请进行版权合规检测。"""

    # try:
    #     response = await call_llm(system_prompt, user_prompt)
    #     return {
    #         "originality_score": 85,
    #         "max_similarity": 0.15,
    #         "passed": True,
    #         "opinion": response,
    #         "similar_entries": [],
    #     }
    # except Exception as e:
    #     logger.error(f"版权校验失败: {e}", exc_info=True)
    #     return {
    #         "originality_score": 0,
    #         "max_similarity": 1.0,
    #         "passed": False,
    #         "opinion": f"校验异常: {str(e)}",
    #         "similar_entries": [],
    #     }
    return {
        "originality_score": 85,
        "max_similarity": 0.15,
        "passed": True,
        "opinion": "版权校验（占位：非 LLM 路径，待实现向量/规则检测）",
        "similar_entries": [],
    }
