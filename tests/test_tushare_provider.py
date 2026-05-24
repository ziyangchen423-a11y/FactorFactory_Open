import pandas as pd

from fundfactory_core.data_providers.tushare_provider import TushareProvider


def test_financial_date_fields_remain_yyyymmdd_strings(monkeypatch):
    provider = TushareProvider(token="test-token")

    def fake_call(api_name, params, fields):
        return pd.DataFrame(
            [
                {
                    "ts_code": "000001.SZ",
                    "ann_date": 20240430,
                    "f_ann_date": 20240430.0,
                    "end_date": "20231231",
                    "revenue": 100.0,
                    "oper_cost": 60.0,
                    "sell_exp": 5.0,
                    "admin_exp": 4.0,
                    "fin_exp": 3.0,
                    "rd_exp": 2.0,
                    "operate_profit": 20.0,
                    "total_profit": 18.0,
                    "income_tax": 3.0,
                    "n_income": 15.0,
                    "n_income_attr_p": 12.0,
                    "basic_eps": 1.2,
                    "ebit": 22.0,
                    "ebitda": 25.0,
                    "update_flag": "1",
                }
            ]
        )

    monkeypatch.setattr(provider, "_call", fake_call)

    record = provider.fetch_income_statement("000001.SZ", "20230101", "20241231")[0]

    assert record["ann_date"] == "20240430"
    assert record["f_ann_date"] == "20240430"
    assert record["end_date"] == "20231231"
    assert record["update_flag"] == "1"
    assert record["revenue"] == 100.0
