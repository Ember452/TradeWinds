"""即时推送阈值自适应单元测试(纯函数)。"""

from tradewinds.services.push_service import effective_immediate_threshold


def test_cold_start_uses_global_threshold() -> None:
    assert effective_immediate_threshold([], 8.0) == 8.0
    assert effective_immediate_threshold([9.0] * 5, 8.0) == 8.0  # 不足 10 条


def test_high_median_raises_threshold() -> None:
    scores = [9.0] * 10

    assert effective_immediate_threshold(scores, 8.0) == 9.0


def test_low_median_lowers_threshold() -> None:
    scores = [6.0] * 10

    assert effective_immediate_threshold(scores, 8.0) == 7.0


def test_adjust_clamps_both_sides() -> None:
    # 中位数极高/极低也只能浮动 ±1.0
    assert effective_immediate_threshold([10.0] * 10, 8.0) == 9.0
    assert effective_immediate_threshold([0.0] * 10, 8.0) == 7.0


def test_median_handles_even_count() -> None:
    scores = [7.0] * 5 + [9.0] * 5

    assert effective_immediate_threshold(scores, 8.0) == 8.0  # 中位数 8.0 == 全局值
