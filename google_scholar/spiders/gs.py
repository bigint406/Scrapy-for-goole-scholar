from scrapy import Request, Spider
import re
from bs4 import BeautifulSoup

from google_scholar.items import GoogleScholarItem

headers = {b'Accept': b'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
 b'Accept-Language': b'en',
 b'User-Agent': b'Scrapy/2.11.2 (+https://scrapy.org)',
 b'Accept-Encoding': b'gzip, deflate'}

valid_publishers = {
    'acm': "dl.acm.org",
    'ieee': "ieeexplore.ieee.org",
    'usenix': "usenix.org",
}

acm_possible_xpath = [
    '//*[@id="skip-to-main-content"]/main/article/header/div[@class="core-container"]/div[@class="core-self-citation"]/div[@property="isPartOf"]/a',
    '//*[@id="skip-to-main-content"]/main/article/header/div[@class="core-container"]/div[@class="core-self-citation"]/div[@class="core-enumeration"]/a/span[@typeof="Periodical"]/span[@property="name"]',
]

class GsSpider(Spider):
    name = "gs"
    allowed_domains = ["scholar.google.com", "dl.acm.org", "ieeexplore.ieee.org", "usenix.org",]
    # paperId = '5793755016373744200'
    paperId = '17608452031319931398'
    
    base_url = 'https://scholar.google.com/scholar?start=%d&hl=en&as_sdt=2005&sciodt=0,5&cites=' + paperId + '&scipsc='
    
    start_urls = [base_url % 0]
    
    error_cnt = 0

    def write_error(self, error, response):
        self.logger.error(error)
        with open('logs/%d.html' % self.error_cnt, 'w', encoding='utf-8') as f:
            self.error_cnt += 1
            f.write(response.url)
            f.write("\n")
            f.write(response.body.decode('utf-8'))
            f.flush()


    def get_html_text(self, xpath, name, response):
        html_item = response.xpath(xpath)
        if len(html_item) == 0:
            self.write_error("Parse "+name+" error, no item", response)
            return
        soup = BeautifulSoup(html_item.extract_first(), 'html.parser')
        return soup.get_text()
    

    def parse(self, response):
        element_with_id = response.xpath('/html/body/div[@id="gs_top"]/div[@id="gs_ab"]/div[@id="gs_ab_md"]/div[@class="gs_ab_mdw"]').extract_first()
        result = re.search(r'About (\d+) results', element_with_id)
        if result:
            cnt = int(result.group(1))
        
        for i in range(0, cnt, 10):
            url = self.base_url % i
            yield Request(url=url, callback=self.parse_data, headers=headers)


    def parse_data(self, response):
        list = response.xpath('//*[@id="gs_res_ccl_mid"]/div')

        for div in list:
            html_title = div.xpath('div[@class="gs_ri"]/h3[@class="gs_rt"]/a')
            a = html_title.attrib['href']
            for k, v in valid_publishers.items():
                if a.find(v) != -1:
                    if k == 'acm':
                        pass
                        yield Request(url=a, callback=self.parse_acm, dont_filter=True)
                    elif k == 'ieee':
                        pass
                        yield Request(url=a, callback=self.parse_ieee, meta={'selenium': True})
                    elif k == 'usenix':
                        pass
                        yield Request(url=a, callback=self.parse_usenix)


    def parse_usenix(self, response):
        title = response.xpath('//*[@id="page-title"]/text()').extract_first()
        publisher = response.xpath('//*[@id="content"]/div[@class="block-content"]/article[1]/div/div[4]/div/div/section/div/div/p/text()[1]').extract_first()
        if publisher is not None:
            publisher = publisher.strip().split(' ')[0]
        year = response.xpath('//*[@id="node-paper-full-group-open-access-content"]/div[2]/div/div/div/div[2]/div[1]/text()[5]').extract_first()
        if year is not None:
            try:
                result = re.search(r"{\d+}", year)
                year = int(result.group()[1:-1])
            except AttributeError:
                self.logger.error("Parse usenix year error: '" + year+"'")

        yield GoogleScholarItem(
            title=title,
            publisher=publisher,
            year=year,
            url=response.url
        )


    def parse_acm(self, response):
        soup = None
        publisher = None
        xpath_idx = 0
        while xpath_idx < len(acm_possible_xpath):
            html_item = response.xpath(acm_possible_xpath[xpath_idx])
            if len(html_item) != 0:
                soup = BeautifulSoup(html_item.extract_first(), 'html.parser')
                break
            xpath_idx += 1

        if soup is None:
            self.write_error("Parse acm publisher error, no item", response)
        else:
            publisher = soup.get_text()
            if xpath_idx == 0:
                try:
                    result = re.search(r" '(\d+):", publisher)
                    publisher = publisher[:result.start()]
                except AttributeError:
                    self.logger.error("Parse acm type %d publisher error: '" % xpath_idx + publisher+"'")
        
        title = self.get_html_text('//*[@id="skip-to-main-content"]/main/article/header/div/h1', "acm title", response)

        year = self.get_html_text('//*[@id="skip-to-main-content"]/main/article/header/div/div[@class="core-published"]/span[@class="core-date-published"]', "acm year", response)
        if year is not None:
            year = int(year.split(' ')[-1])

        yield GoogleScholarItem(
            title=title,
            publisher=publisher,
            year=year,
            url=response.url
        )


    def parse_ieee(self, response):
        title = self.get_html_text('//*[@id="xplMainContentLandmark"]/div/xpl-document-details/div/div[1]/section[2]/div/xpl-document-header/section/div[2]/div/div/div[1]/div/div[1]/h1/span', "ieee title", response)
        
        publisher = self.get_html_text('//*[@id="xplMainContentLandmark"]/div/xpl-document-details/div/div[1]/div/div[2]/section/div[2]/div/xpl-document-abstract/section/div[2]/div[2]/a', "ieee publisher", response)
        if publisher is not None:
            publisher = publisher.strip()
            if publisher[-1] == ')':
                try:
                    result = re.search(r"\(.*\)$", publisher)
                    publisher = result.group()[1:-1]
                except AttributeError:
                    self.logger.error("Parse ieee publisher error: '" + publisher+"'")

        year = response.xpath('//*[@id="xplMainContentLandmark"]/div/xpl-document-details/div/div[1]/div/div[2]/section/div[2]/div/xpl-document-abstract/section/div[2]/div[3]/div[1]/div[2]/text()').extract_first()
        if year is not None:
            try:
                year = int(year.strip().split(' ')[-1])
            except ValueError:
                self.logger.error("Parse ieee year error: '" + year+"'")
        
        yield GoogleScholarItem(
            title=title,
            publisher=publisher,
            year=year,
            url=response.url
        )

