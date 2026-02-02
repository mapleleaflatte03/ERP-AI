"""
Smoke Test Spider - quotes.toscrape.com
========================================
Purpose: Verify Scrapy setup and Zyte deployment works correctly.
Target: https://quotes.toscrape.com/ (safe practice site)
Output: quote, author, tags, url

This spider is intentionally lightweight:
- Only scrapes first 2 pages max
- Respects robots.txt
- Uses 1 second delay between requests
"""

import scrapy

from asoft_zyte.items import QuoteItem


class SmokeQuotesSpider(scrapy.Spider):
    """
    Smoke test spider that scrapes quotes from quotes.toscrape.com.
    Safe for testing - this site is designed for scraping practice.
    """

    name = "smoke_quotes"
    allowed_domains = ["quotes.toscrape.com"]
    start_urls = ["https://quotes.toscrape.com/"]

    # Custom settings for this spider (override global settings)
    custom_settings = {
        "DOWNLOAD_DELAY": 1,
        "CONCURRENT_REQUESTS": 1,
        "DEPTH_LIMIT": 2,  # Only follow 2 levels deep
        "CLOSESPIDER_PAGECOUNT": 3,  # Max 3 pages
        "CLOSESPIDER_ITEMCOUNT": 15,  # Max 15 items
    }

    def parse(self, response):
        """
        Parse the main quotes listing page.
        Extract quotes and follow pagination (limited).
        """
        self.logger.info(f"Parsing: {response.url}")

        # Extract all quotes from current page
        quotes = response.css("div.quote")
        self.logger.info(f"Found {len(quotes)} quotes on page")

        for quote_div in quotes:
            item = QuoteItem()

            # Extract quote text (remove surrounding quotes)
            text = quote_div.css("span.text::text").get()
            if text:
                # Remove the fancy quotes characters
                item["quote"] = text.strip().strip(""").strip(""")

            # Extract author
            item["author"] = quote_div.css("small.author::text").get()

            # Extract tags as list
            item["tags"] = quote_div.css("div.tags a.tag::text").getall()

            # Store source URL
            item["url"] = response.url

            yield item

        # Follow "Next" pagination link (limited by DEPTH_LIMIT)
        next_page = response.css("li.next a::attr(href)").get()
        if next_page:
            self.logger.info(f"Following next page: {next_page}")
            yield response.follow(next_page, callback=self.parse)
        else:
            self.logger.info("No more pages to follow")
