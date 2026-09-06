"""偏好画像单元测试:prompt 段落渲染(纯函数)。"""

from tradewinds.services.preference_service import build_scoring_prompt_section


def test_empty_preferences_renders_nothing() -> None:
    assert build_scoring_prompt_section([]) == ""


def test_preferences_section_states_reference_only() -> None:
    section = build_scoring_prompt_section(["关注过的内容方向:agent-evals", "订阅过相关主题:RAG"])

    assert "关注过的内容方向:agent-evals" in section
    assert "订阅过相关主题:RAG" in section
    # 必须显式声明"仅作参考",防止偏好压过主题判定标准
    assert "仅作参考信号" in section
    assert "以本主题判定标准为准" in section
