from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date, timedelta

from krx_client import KRXBaseRow
from rules import is_excluded_security, is_seed_target
from settings import SEED_LOOKBACK_DAYS


AS_OF = date(2026, 11, 19)
ORDINARY_ROW = KRXBaseRow(
    stock_code="123456",
    company_name="일반기업",
    company_name_eng=None,
    listing_date=date(2026, 10, 27),
    market_type="KOSDAQ",
    security_group="주권",
    stock_cert_type="보통주",
    sector_name="벤처기업부",
    par_value=None,
    listed_shares=None,
    raw_payload={},
)


class SecurityRulesTests(unittest.TestCase):
    def test_sk_securities_no14_spac_is_excluded(self) -> None:
        row = replace(
            ORDINARY_ROW,
            stock_code="0205H0",
            company_name="에스케이증권제14호기업인수목적",
            company_name_eng="SK Securities No.14 Special Purpose Acquisition Company",
            sector_name="SPAC(소속부없음)",
        )
        self.assertEqual(is_excluded_security(row), (True, "company_name_excluded"))
        self.assertEqual(is_seed_target(row, as_of=AS_OF), (False, "company_name_excluded"))

    def test_spac_name_is_excluded_without_sector_metadata(self) -> None:
        for name in (
            "에스케이증권제14호기업인수목적",
            "에스케이증권제14호 기업 인수 목적 주식회사",
            "에스케이증권제14호기업\t인수\n목적",
            "테스트스팩1호",
            "Test spac No.1",
        ):
            with self.subTest(name=name):
                row = replace(ORDINARY_ROW, company_name=name, sector_name=None)
                self.assertEqual(is_excluded_security(row), (True, "company_name_excluded"))

    def test_spac_sector_is_excluded_without_name_keywords(self) -> None:
        for sector in ("SPAC(소속부없음)", "spac", "스팩", "기업인수목적"):
            with self.subTest(sector=sector):
                row = replace(ORDINARY_ROW, sector_name=sector)
                self.assertEqual(is_excluded_security(row), (True, "sector_name_excluded"))
                self.assertEqual(is_seed_target(row, as_of=AS_OF), (False, "sector_name_excluded"))

    def test_spac_security_group_is_excluded(self) -> None:
        for group in ("SPAC", "스팩", "기업인수목적"):
            with self.subTest(group=group):
                row = replace(ORDINARY_ROW, security_group=group)
                self.assertEqual(is_excluded_security(row), (True, "security_group_excluded"))

    def test_existing_special_security_exclusions_are_preserved(self) -> None:
        cases = (
            ({"company_name": "테스트리츠"}, "company_name_excluded"),
            ({"company_name": "Test REIT"}, "company_name_excluded"),
            ({"security_group": "ETF"}, "security_group_excluded"),
            ({"security_group": "ETN"}, "security_group_excluded"),
            ({"security_group": "ELW"}, "security_group_excluded"),
            ({"stock_cert_type": "수익증권"}, "stock_cert_type_excluded"),
        )
        for fields, reason in cases:
            with self.subTest(fields=fields):
                self.assertEqual(is_excluded_security(replace(ORDINARY_ROW, **fields)), (True, reason))

    def test_ordinary_recent_ipos_are_still_eligible(self) -> None:
        for market in ("KOSPI", "KOSDAQ"):
            for sector in ("우량기업부", "중견기업부", "벤처기업부", None):
                with self.subTest(market=market, sector=sector):
                    row = replace(ORDINARY_ROW, market_type=market, sector_name=sector)
                    self.assertEqual(is_excluded_security(row), (False, None))
                    self.assertEqual(is_seed_target(row, as_of=AS_OF), (True, "ok"))

    def test_listing_date_limits_are_preserved(self) -> None:
        for listing_date in (
            AS_OF - timedelta(days=SEED_LOOKBACK_DAYS + 1),
            AS_OF + timedelta(days=1),
        ):
            with self.subTest(listing_date=listing_date):
                row = replace(ORDINARY_ROW, listing_date=listing_date)
                self.assertEqual(is_seed_target(row, as_of=AS_OF), (False, "listing_date_out_of_range"))


if __name__ == "__main__":
    unittest.main()
