#!/usr/bin/env python3
"""
TTB Webscraping
"""


import requests
from bs4 import BeautifulSoup
import re
import datetime
import warnings

__author__ = "Jonathan Hirokawa"
__version__ = "0.1.0"
__license__ = "MIT"


class TTB_query(object):

    def __init__(self, date_start=None, date_end=None, fancy_name=None, prod_name_type=None, class_desired=None,
                 class_code=None, origin_code=None, ttb_id_start=None, ttb_id_end=None, serial_start=None,
                 serial_end=None, permit_id=None, vendor_code=None):
        """
        Performs a new 'advanced' query on the TTB database

        :param date_start: start of date range for when the COLA was approved (ex 09/01/2016)
        :param date_end: end of date range for when the COLA was approved (ex 09/24/2017)
        :param fancy_name: may be used in addition to standard name to further ID product
        :param prod_name_type: E
        :param class_desired: 'desc'
        :param class_code:
        :param origin_code:00
        :param ttb_id_start:
        :param ttb_id_end:
        :param serial_start:
        :param serial_end:
        :param permit_id:
        :param vendor_code:
        :return:
        """

        self.session = requests.Session()
        self.soup = None

        url = r'https://www.ttbonline.gov/colasonline/publicSearchColasAdvancedProcess.do'

        payload = {'searchCriteria.dateCompletedFrom': date_start,
                   'searchCriteria.dateCompletedTo': date_end,
                   'searchCriteria.productOrFancifulName': fancy_name,
                   'searchCriteria.productNameSearchType': prod_name_type,
                   'searchCriteria.classTypeDesired': class_desired,
                   'searchCriteria.classTypeCode': class_code,
                   'searchCriteria.originCodeArray': origin_code,
                   'searchCriteria.ttbIdFrom': ttb_id_start,
                   'searchCriteria.ttbIdTo': ttb_id_end,
                   'searchCriteria.serialNumFrom': serial_start,
                   'searchCriteria.serialNumTo': serial_end,
                   'searchCriteria.permitId': permit_id,
                   'searchCriteria.vendorCode': vendor_code
                   }

        params = {'action': 'search'}

        response = self.session.post(url, params=params, data=payload)
        self.soup = BeautifulSoup(response.text, 'html5lib')

    def next_page(self):
        """
        Follow a 'next page' link (requires active session!)

        TTB uses cookies (specifically the JSESSIONID variable) to keep track of users and serve consistent results.
        By keeping a session active across queries, we can avoid a lot of the headache involved in passing the needed
        data around.
        """
        url = r'https://www.ttbonline.gov/colasonline/publicPageAdvancedCola.do'

        params = {'action': 'page',
                  'pgfcn': 'nextset'}

        response = self.session.get(url, params=params)
        self.soup = BeautifulSoup(response.text, 'html5lib')

    def get_ids(self):
        """Extract the TTB IDs listed"""
        dk = [link.get_text() for link in self.soup.select('tr.dk a')]  # extract dark highlighted rows
        lt = [link.get_text() for link in self.soup.select('tr.lt a')]  # extract light highlighted rows

        return dk + lt

    def get_num_results(self):
        """Return the number of search results for a query"""
        pagination_div = self.soup.select('div.pagination')
        return int(re.findall(r'\(Total Matching Records: ([0-9]+)\)', pagination_div[0].get_text())[0])


class TTB_crawler(object):

    def __init__(self, date_start, date_end, origin_code):
        self.query = TTB_query(date_start=date_start, date_end=date_end, origin_code=origin_code)  # naive query

        self.qstart = datetime.datetime.strptime(date_start, '%m/%d/%Y')  # convert to datetime obj
        self.qend = datetime.datetime.strptime(date_end, '%m/%d/%Y')

    def crawl(self):

        total_hits = self.query.get_num_results()

        if total_hits > 500:
            warnings.warn('Found > 500 TTBIDs, breaking into smaller queries')
            # could go, month, then day, find the TTBID used and then grab segments of 500

def main():
    """ Main entry point of the app """
    #query = TTB_query(date_start='01/01/2016', date_end='01/01/2017', origin_code='00')
    #print(query.get_num_results())

    crawler = TTB_crawler('01/01/2016', '01/01/2017', '00')
    crawler.crawl()

if __name__ == "__main__":
    """ This is executed when run from the command line """
    main()