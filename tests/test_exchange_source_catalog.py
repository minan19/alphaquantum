import unittest

from app.engines.exchange_source_catalog import (
    build_default_market_pages,
    list_exchange_sources,
    profile_for_domain,
    seed_symbols_for_domain,
)


class ExchangeSourceCatalogTests(unittest.TestCase):
    def test_list_sources_by_region(self) -> None:
        sources = list_exchange_sources(regions=["TR", "EU"], limit=10)
        self.assertGreaterEqual(len(sources), 4)
        regions = {item.region for item in sources}
        self.assertIn("TR", regions)
        self.assertIn("EU", regions)

    def test_profile_and_seed_symbols_by_domain(self) -> None:
        profile = profile_for_domain("www.borsaistanbul.com")
        self.assertIsNotNone(profile)
        self.assertEqual(profile.region, "TR")
        symbols = seed_symbols_for_domain("borsaistanbul.com")
        self.assertIn("XU100.IS", symbols)

    def test_build_default_pages(self) -> None:
        pages = build_default_market_pages(regions=["GLOBAL"], limit=6)
        self.assertGreaterEqual(len(pages), 3)
        first = pages[0]
        self.assertIn("url", first)
        self.assertIn("focus_terms", first)


if __name__ == "__main__":
    unittest.main()
