import unittest
from unittest.mock import patch

from lead_engine.web_research import (
    _clean_ddg_url,
    _parse_search_html,
    build_queries,
    search_public_web,
)


class WebResearchTests(unittest.TestCase):
    def test_build_queries_contains_company_and_contact(self):
        queries = build_queries("Hyppy", "Sawni Gupta")
        self.assertTrue(any('"Hyppy" ecommerce operations' in q for q in queries))
        self.assertIn('"Sawni Gupta" "Hyppy"', queries)

    def test_clean_ddg_redirect(self):
        url = "https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fcareers"
        self.assertEqual(_clean_ddg_url(url), "https://example.com/careers")

    def test_parse_standard_ddg_markup(self):
        html = """
        <a class="result__a" href="https://example.com/careers">Example Careers</a>
        <div class="result__snippet">Hiring ecommerce operations staff.</div>
        """
        results = _parse_search_html(html, max_results=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Example Careers")
        self.assertEqual(results[0].url, "https://example.com/careers")
        self.assertIn("ecommerce operations", results[0].snippet)

    def test_parse_lite_ddg_markup(self):
        html = """
        <a class="result-link" href="https://example.com/shop">Example Shop</a>
        <td class="result-snippet">Shopify store information.</td>
        """
        results = _parse_search_html(html, max_results=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].url, "https://example.com/shop")
        self.assertIn("Shopify", results[0].snippet)

    @patch("lead_engine.web_research._fetch_search_endpoint")
    def test_search_falls_back_when_first_endpoint_has_no_results(self, mock_fetch):
        mock_fetch.side_effect = [
            [],
            [
                type("Result", (), {
                    "title": "Fallback",
                    "url": "https://example.com/fallback",
                    "snippet": "fallback result",
                })()
            ],
        ]
        results = search_public_web("Hyppy ecommerce", max_results=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].url, "https://example.com/fallback")
        self.assertEqual(mock_fetch.call_count, 2)


if __name__ == "__main__":
    unittest.main()
