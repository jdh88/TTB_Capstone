#!/usr/bin/env python3
"""
TTB Webscraping
"""


import requests
from bs4 import BeautifulSoup
import re
import datetime
import itertools

__author__ = "Jonathan Hirokawa"
__version__ = "0.1.0"
__license__ = "MIT"


class TTB_query(object):

    def __init__(self, date_start=None, date_end=None, fancy_name=None, prod_name_type=None, class_desired=None,
                 class_code=None, origin_code=None, ttb_id_start=None, ttb_id_end=None, serial_start=None,
                 serial_end=None, permit_id=None, vendor_code=None):
        """
        Performs a new 'advanced' query on the TTB database

        :param date_start: start of date range for when the COLA was approved (ex '09/01/2016')
        :param date_end: end of date range for when the COLA was approved (ex '09/24/2017')
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

        NOTE: if there are no more 'Next' pages, soup becomes None
        """

        old_soup = self.soup

        url = r'https://www.ttbonline.gov/colasonline/publicPageAdvancedCola.do'

        params = {'action': 'page',
                  'pgfcn': 'nextset'}

        response = self.session.get(url, params=params)
        new_soup = BeautifulSoup(response.text, 'html5lib')

        if old_soup == new_soup:
            # no new data (no next page)
            self.soup = None
        else:
            self.soup = new_soup

    def get_table_data(self):
        """Extract the table data from a page of the search"""

        def process_row(row):
            return [col.get_text().strip() for col in row.select('td')]

        rows = self.soup.select('.box table tr')

        if rows:
            keys = [header.get_text() for header in rows[0].select('th')]

            td = [dict(zip(keys, process_row(row))) for row in rows[1:]]

            return td
        else:
            return []

    def get_ids(self):
        """Extract the TTB IDs listed on the current page"""
        dk = [link.get_text() for link in self.soup.select('tr.dk a')]  # extract dark highlighted rows
        lt = [link.get_text() for link in self.soup.select('tr.lt a')]  # extract light highlighted rows

        return dk + lt

    def get_num_results(self):
        """Return the number of search results for a query"""
        pagination_div = self.soup.select('div.pagination')
        try:
            return int(re.findall(r'\(Total Matching Records: ([0-9]+)\)', pagination_div[0].get_text())[0])
        except IndexError:
            return pagination_div

    def get_all_results(self):
        """Iterate through each page aggregating results"""

        res = []
        while self.soup:
            res += self.get_table_data()
            self.next_page()

        return res



class TTB_crawler(object):

    def __init__(self, date_start, date_end, origin_code):

        start = datetime.datetime.strptime(date_start, '%m/%d/%Y')  # convert to datetime obj
        stop = datetime.datetime.strptime(date_end, '%m/%d/%Y')

        #self.date_start = start.strftime('%d/%m/%Y')  # store the date as a string
        #self.date_end = stop.strftime('%d/%m/%Y')
        self.date_start = date_start
        self.date_end = date_end
        self.origin_code = origin_code

    def run(self):
        return self.crawl(self.date_start, self.date_end, self.origin_code)

    @staticmethod
    def date_range(start, end, intv):
        """Break down date range into intv discrete date ranges"""
        start = datetime.datetime.strptime(start, "%m/%d/%Y")
        end = datetime.datetime.strptime(end, "%m/%d/%Y")
        diff = (end - start) / intv
        for i in range(intv):
            yield (start + diff * i).strftime("%m/%d/%Y")
        yield end.strftime("%m/%d/%Y")

    @staticmethod
    def pairwise(iterable):
        """s -> (s0,s1), (s1,s2), (s2, s3), ..."""
        a, b = itertools.tee(iterable)
        next(b, None)
        return zip(a, b)

    @staticmethod
    def crawl(date_start, date_end, origin_code=['00']):
        """Find every TTBID in given range"""

        query = TTB_query(date_start=date_start, date_end=date_end,
                          origin_code=origin_code)

        total_hits = query.get_num_results()
        print('Subquery hits: {}'.format(total_hits))
        res = []

        # did our query return any values
        if total_hits:

            # only 500 results at a time are returned, check to see if we hit that limit
            if total_hits > 500:

                # calculate how many days we are currently searching for
                date_window = datetime.datetime.strptime(date_end, "%m/%d/%Y") - datetime.datetime.strptime(date_start, "%m/%d/%Y")

                # see if we are looking at a single day
                if date_window == datetime.timedelta(0):

                    # ideally, we'd just use ttb_id ranges, but this search term unfortunately does not behave
                    # as expected instead we just subdivide by origin codes
                    if len(origin_code) > 1:
                        res = TTB_crawler.crawl(date_start, date_end, origin_code=origin_code[0:int(len(origin_code) / 2)])
                        res += TTB_crawler.crawl(date_start, date_end, origin_code=origin_code[int(len(origin_code) / 2):])
                    else:
                        # if necessary we could also subdivide by type, but that will make only small differences
                        print('Unable to further decompose query: {dstart}-{dstop}, {orig}'.format(dstart=date_start,
                                                                                                   dstop=date_end,
                                                                                                   orig=origin_code))

                else:
                    # down to two day window
                    if date_window == datetime.timedelta(1):
                        # search for each day individually
                        res = TTB_crawler.crawl(date_start=date_start, date_end=date_start, origin_code=origin_code)
                        res += TTB_crawler.crawl(date_start=date_end, date_end=date_end, origin_code=origin_code)

                    # range of days left
                    else:
                        # break the date range in half and try again
                        date_spans = list(TTB_crawler.pairwise(TTB_crawler.date_range(date_start, date_end, 2)))

                        res = TTB_crawler.crawl(date_start=date_spans[0][0], date_end=date_spans[0][1], origin_code=origin_code)
                        res += TTB_crawler.crawl(date_start=date_spans[1][0], date_end=date_spans[1][1], origin_code=origin_code)
            else:
                res = query.get_all_results()
        return res

def main():
    """ Main entry point of the app """
    #query = TTB_query(date_start='01/01/2016', date_end='01/01/2017', origin_code='00')
    #print(query.get_num_results())

    import pandas as pd
    #origin_codes = pd.read_csv('origin_codes.txt', header=None, sep='\t')
    #origin_codes.columns = ['code', 'location']
    #origin_codes = list(origin_codes['code']

    # generate a list of only US state origin codes (4E is alaska)
    origin_codes = [str(i).zfill(2) for i in list(range(0, 50))] + ['4E']

    start_date = datetime.datetime(2017, 9, 1)
    stop_date = datetime.datetime(2017, 12, 31)
    crawler = TTB_crawler(start_date.strftime('%m/%d/%Y'), stop_date.strftime('%m/%d/%Y'), origin_codes)
    res = crawler.run()
    print('Number of results: {}'.format(len(res)))
    df = pd.DataFrame(res)
    df.to_pickle('{}-{}.pkl'.format(start_date.strftime('%Y%m%d'), start_date.strftime('%Y%m%d')))


if __name__ == "__main__":
    """ This is executed when run from the command line """
    main()