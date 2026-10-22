import unittest

from galaxy_core.shared_kernel.utils.time_parser import (
    get_default_start_date_for_symbol,
    resolve_default_start_date,
)


class TestKlineDefaultStartDates(unittest.TestCase):
    def test_get_default_start_date_for_stock(self):
        self.assertEqual(get_default_start_date_for_symbol("600000.SH"), "20130101")

    def test_get_default_start_date_for_option(self):
        self.assertEqual(
            get_default_start_date_for_symbol("10003737.OPTION"), "20150101"
        )

    def test_get_default_start_date_for_hkt(self):
        self.assertEqual(get_default_start_date_for_symbol("900001.SH"), "20230101")

    def test_get_default_start_date_for_zj_future(self):
        self.assertEqual(get_default_start_date_for_symbol("IF2403.FUTURE"), "20100401")

    def test_get_default_start_date_for_ds_future(self):
        self.assertEqual(get_default_start_date_for_symbol("M2405.FUTURE"), "20130601")

    def test_get_default_start_date_for_zs_future(self):
        self.assertEqual(get_default_start_date_for_symbol("SR405.FUTURE"), "20110101")

    def test_get_default_start_date_for_sq_future(self):
        self.assertEqual(get_default_start_date_for_symbol("CU2405.FUTURE"), "20190801")

    def test_resolve_default_start_date_uses_latest_bound_for_mixed_symbols(self):
        self.assertEqual(
            resolve_default_start_date(["600000.SH", "10003737.OPTION"], None),
            "20150101",
        )

    def test_resolve_default_start_date_preserves_explicit_start(self):
        self.assertEqual(
            resolve_default_start_date(["600000.SH", "10003737.OPTION"], "20200101"),
            "20200101",
        )

    def test_get_default_start_date_for_unknown_symbol_raises(self):
        with self.assertRaisesRegex(ValueError, "无法推断证券类型"):
            get_default_start_date_for_symbol("INVALID")


if __name__ == "__main__":
    unittest.main()
