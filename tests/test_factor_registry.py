"""
Tests for fundfactory_core.factors.registry.
"""


def test_factor_ids_returns_at_least_twenty():
    """factor_ids() must return at least 20 registered factor IDs."""
    from fundfactory_core.factors.registry import factor_ids

    ids = factor_ids()
    assert len(ids) >= 20, f"expected at least 20 factors, got {len(ids)}: {ids}"


def test_factor_ids_includes_mom_5d_and_roe():
    """factor_ids() must include MOM_5D and ROE."""
    from fundfactory_core.factors.registry import factor_ids

    ids = factor_ids()
    assert "MOM_5D" in ids, f"MOM_5D not found in {ids}"
    assert "ROE" in ids, f"ROE not found in {ids}"


def test_factor_ids_includes_expected_set():
    """factor_ids() must include the full set of sample factors."""
    from fundfactory_core.factors.registry import factor_ids

    ids = set(factor_ids())
    expected = {
        # Original 10
        "MOM_5D", "MOM_20D", "MOM_60D",
        "VOL_20D", "VOL_60D",
        "LNCAP", "PE_SIMPLE", "PB_SIMPLE",
        "ROE", "ROA",
        # New 量价因子
        "RET_10D", "RET_20D", "RET_60D",
        "VOL_RATIO_5D", "VOL_RATIO_20D",
        "AMOUNT_RATIO_5D", "AMOUNT_RATIO_20D",
        "AMPLITUDE_20D", "AMPLITUDE_60D",
        "CLOSE_POS_20D", "CLOSE_POS_60D",
        "TURNOVER_20D",
        "VOL_VOL_20D",
        "PRICE_OSC_20D",
    }
    assert expected.issubset(ids), f"missing factors: {expected - ids}"


def test_each_factor_has_metadata():
    """Every registered factor must have complete metadata."""
    from fundfactory_core.factors.registry import factor_ids, get_metadata

    required_keys = {"factor_id", "name", "category", "description", "direction", "lookback_days"}
    for fid in factor_ids():
        meta = get_metadata(fid)
        assert meta is not None, f"No metadata for factor {fid}"
        missing = required_keys - set(meta.keys())
        assert not missing, f"Factor {fid} missing metadata keys: {missing}"
