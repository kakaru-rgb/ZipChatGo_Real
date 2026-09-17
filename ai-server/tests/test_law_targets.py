from app.law.targets import CIVIL_ACT_REAL_ESTATE_RANGES, LAW_TARGETS, LawTarget


def test_stage_7_2_law_targets_are_declared_once() -> None:
    target_names = {target.name for target in LAW_TARGETS}

    assert "상가건물 임대차보호법" in target_names
    assert "상가건물 임대차보호법 시행령" in target_names
    assert "민법" in target_names
    assert "부동산등기법" in target_names
    assert "부동산등기규칙" in target_names
    assert "집합건물의 소유 및 관리에 관한 법률" in target_names
    assert "집합건물의 소유 및 관리에 관한 법률 시행령" in target_names


def test_civil_act_target_keeps_only_real_estate_related_ranges() -> None:
    civil_act = next(target for target in LAW_TARGETS if target.name == "민법")

    assert civil_act.article_ranges == CIVIL_ACT_REAL_ESTATE_RANGES
    assert civil_act.includes_article(390)
    assert civil_act.includes_article(565)
    assert civil_act.includes_article(618)
    assert civil_act.includes_article(654)
    assert not civil_act.includes_article(1)
    assert not civil_act.includes_article(400)
    assert not civil_act.includes_article(600)


def test_target_without_ranges_includes_every_article() -> None:
    target = LawTarget("상가건물 임대차보호법", "법률")

    assert target.includes_article(1)
    assert target.includes_article(999)
