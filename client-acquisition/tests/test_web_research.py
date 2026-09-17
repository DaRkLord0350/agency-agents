import unittest

from lead_engine.web_research import _clean_ddg_url, build_queries


class WebResearchTests(unittest.TestCase):
    def test_build_queries_contains_company_and_contact(self):
        queries = build_queries("Hyppy", "Sawni Gupta")
        self.assertTrue(any('"Hyppy" ecommerce operations' in q for q in queries))
        self.assertIn('"Sawni Gupta" "Hyppy"', queries)

    def test_clean_ddg_redirect(self):
        url = "https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fcareers"
        self.assertEqual(_clean_ddg_url(url), "https://example.com/careers")


if __name__ == "__main__":
    unittest.main()
