from datetime import date

from src.next_dutch_firsts import (
    FILTERS,
    WEIGHTS,
    CsvDemoSource,
    apply_filter,
    load_ranked,
    rarity_category,
    score_candidates,
    timeline,
    top_rising,
    compute_momentum,
    Candidate,
    MOMENTUM_MAX,
    summary_counts,
    timeline_label,
    integer_breakdown,
)


def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1) < 1e-9


def test_rarity_categories():
    labels = [rarity_category(n) for n in (0, 1, 5, 6, 10, 11, 25, 26)]
    assert labels == [
        "Not Recorded", "1-5 Records", "1-5 Records", "6-10 Records",
        "6-10 Records", "11-25 Records", "11-25 Records", "25+ Records",
    ]


def test_scores_and_rarity_bonus():
    ranked = score_candidates(CsvDemoSource().load(), today=date(2026, 1, 1))
    scores = [c.prediction_score for c in ranked]
    assert scores == sorted(scores, reverse=True)
    assert all(0 <= s <= 100 and c.rationale for s, c in zip(scores, ranked))
    base = ranked[0]
    rare = type(base)(**{**base.__dict__, "dutch_record_count": 0})
    common = type(base)(**{**base.__dict__, "dutch_record_count": 30})
    first = score_candidates([common, rare], today=date(2026, 1, 1))[0]
    assert first.dutch_record_count == 0


def test_filters():
    ranked = load_ranked()
    assert len(apply_filter(ranked, FILTERS[0])) == len(ranked)
    firsts = apply_filter(ranked, FILTERS[1])
    assert firsts and all(c.dutch_record_count == 0 for c in firsts)
    assert all(c.dutch_record_count < 10 for c in apply_filter(ranked, FILTERS[2]))
    pipe = apply_filter(ranked, FILTERS[3])
    assert pipe and all(c.corvo_records > 0 for c in pipe)


def test_timeline_order():
    c = load_ranked()[0]
    assert [r for r, _, _ in timeline(c)] == ["Corvo", "Ireland", "UK", "Netherlands"]


def test_long_overdue_filter():
    overdue = apply_filter(load_ranked(), FILTERS[4])
    assert overdue
    for c in overdue:
        assert c.years_since_last_dutch_record() >= 10
        assert c.dutch_record_count > 0
    years = [c.years_since_last_dutch_record() for c in overdue]
    assert years == sorted(years, reverse=True)


TODAY = date(2026, 6, 1)


def _cand(**kw):
    base = dict(
        common_name="X", scientific_name="X x", corvo_records=10, ireland_records=10,
        uk_records=10, france_records=0, spain_records=0, portugal_records=0,
    )
    return Candidate(**{**base, **kw})


def test_momentum_points():
    c = _cand(corvo_latest_year=2025, ireland_latest_year=2024, uk_latest_year=2020, recent_records=1)
    compute_momentum(c, TODAY)
    assert c.momentum_score == 13 and c.momentum_regions == ("corvo", "ireland")
    surging = _cand(corvo_latest_year=2026, ireland_latest_year=2026, uk_latest_year=2026, recent_records=5)
    compute_momentum(surging, TODAY)
    assert surging.momentum_score == MOMENTUM_MAX == 20
    quiet = _cand(corvo_latest_year=2015)
    compute_momentum(quiet, TODAY)
    assert quiet.momentum_score == 0 and quiet.momentum_label == "○ Low Momentum"


def test_momentum_affects_total_ranking():
    hot = _cand(common_name="Hot", corvo_latest_year=2026, ireland_latest_year=2026, uk_latest_year=2026)
    cold = _cand(common_name="Cold", corvo_latest_year=2026, ireland_latest_year=2015, uk_latest_year=2015)
    ranked = score_candidates([cold, hot], today=TODAY)
    assert ranked[0].common_name == "Hot"
    assert ranked[0].prediction_score > ranked[1].prediction_score


def test_rising_fast_and_top_rising():
    ranked = load_ranked()
    rising = apply_filter(ranked, FILTERS[5])
    assert rising and all(c.momentum_score >= 13 for c in rising)
    top = top_rising(ranked)
    assert len(top) == 5
    assert [c.momentum_score for c in top] == sorted((c.momentum_score for c in top), reverse=True)
    assert "active movement" in rising[0].rationale


def test_breakdown_sums_exactly_to_score():
    for c in load_ranked():
        assert sum(c.score_breakdown.values()) == c.prediction_score
        assert set(c.score_breakdown) == set(WEIGHTS)
    pts = {"a": 10.5, "b": 10.5, "c": 10.5, "d": 10.5, "e": 0.4}
    assert sum(integer_breakdown(pts).values()) == round(sum(pts.values()))


def test_top_rising_only_qualifying_and_may_be_short():
    quiet = [_cand(common_name=str(i), corvo_latest_year=2000) for i in range(3)]
    assert top_rising(score_candidates(quiet, today=TODAY)) == []
    for c in top_rising(load_ranked()):
        assert c.momentum_score >= 13


def test_summary_counts_match_filters():
    ranked = load_ranked()
    counts = summary_counts(ranked)
    assert len(counts) == 5 and all(v >= 0 for v in counts.values())
    assert counts[FILTERS[5]] == len(apply_filter(ranked, FILTERS[5]))


def test_timeline_labels():
    c = _cand(corvo_latest_year=2025, ireland_latest_year=2024, uk_latest_year=2025)
    labels = [timeline_label(*stage) for stage in timeline(c, TODAY)]
    assert labels == ["Corvo (2025, 1y ago)", "Ireland (2024, 2y ago)", "UK (2025, 1y ago)", "Netherlands (never)"]
