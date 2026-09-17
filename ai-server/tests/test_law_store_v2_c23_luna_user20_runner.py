from scripts.evaluate_law_store_v2_c23_luna_user20 import _StoreFalseResponses


class _FakeResponses:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def create(self, *args: object, **kwargs: object) -> dict[str, object]:
        self.calls.append((args, kwargs))
        return kwargs


def test_store_false_proxy_sets_false_when_omitted() -> None:
    target = _FakeResponses()

    result = _StoreFalseResponses(target).create(model="gpt-5.6-luna")

    assert result["store"] is False
    assert target.calls[0][1]["store"] is False


def test_store_false_proxy_does_not_allow_true_override() -> None:
    target = _FakeResponses()

    result = _StoreFalseResponses(target).create(store=True)

    assert result["store"] is False
    assert target.calls[0][1]["store"] is False
