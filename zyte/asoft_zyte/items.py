# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class QuoteItem(scrapy.Item):
    """Item for quotes from quotes.toscrape.com smoke test"""

    quote = scrapy.Field()
    author = scrapy.Field()
    tags = scrapy.Field()
    url = scrapy.Field()


class InvoiceItem(scrapy.Item):
    """Item for future invoice scraping (placeholder)"""

    invoice_number = scrapy.Field()
    vendor_name = scrapy.Field()
    invoice_date = scrapy.Field()
    total_amount = scrapy.Field()
    vat_amount = scrapy.Field()
    currency = scrapy.Field()
    raw_text = scrapy.Field()
    source_url = scrapy.Field()
    scraped_at = scrapy.Field()
