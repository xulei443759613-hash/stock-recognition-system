from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_recognition_system import GroupMessage, MarketEvidence, StockRecognitionEngine


RAW_MESSAGE = """
【6月30号 下午金股】:

【富祥股份 300497】

入场参考：21.80~22.20元
目标参考：24.2元
止损参考：19.8元
参考逻辑：半年机构调研+游资参与+基金参与+北上资金参与+资金热度上升+毛利率上升，业绩+涨价。

以上信息不构成投资建议。
"""


def main() -> None:
    engine = StockRecognitionEngine()
    message = GroupMessage(raw_text=RAW_MESSAGE, push_time="14:40")
    evidence = MarketEvidence(
        current_price=21.90,
        is_limit_up=False,
        five_day_change_pct=8.5,
        market_index_change_pct=-0.6,
        verified_claims={"毛利率上升": True},
        data_warnings=["demo uses manual market data"],
    )
    result = engine.review(message, evidence, account_value=10000)

    print("signal:", result.action.value)
    print("confidence:", result.confidence)
    print("max_position_pct:", f"{result.max_position_pct:.2%}")
    print("red_flags:", result.red_flags)
    print("hard_vetoes:", result.hard_vetoes)
    for name, rr in result.risk_rewards.items():
        print(name, rr)
    print()
    print(result.report)


if __name__ == "__main__":
    main()
