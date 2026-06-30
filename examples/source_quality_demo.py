from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_recognition_system.models import SignalAction
from stock_recognition_system.records import SourceOutcome, score_source_quality


def main() -> None:
    outcomes = [
        SourceOutcome(SignalAction.ABANDON, late_push=True),
        SourceOutcome(SignalAction.WAIT_PULLBACK, chased_after_target=True),
        SourceOutcome(SignalAction.SIMULATE, reached_target=True),
        SourceOutcome(SignalAction.SMALL_TEST, hit_stop_loss=True),
    ]
    print(score_source_quality(outcomes))


if __name__ == "__main__":
    main()
