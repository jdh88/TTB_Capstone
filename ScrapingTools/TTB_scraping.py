#!/usr/bin/env python3
"""
TTB Webscraping
"""


import requests
from bs4 import BeautifulSoup
import re

from PIL import Image
import io

from collections import deque

__author__ = "Jonathan Hirokawa"
__version__ = "0.1.0"
__license__ = "MIT"


class TTB_Scraper(object):

    def __init__(self, ttb_id):
        """
        Initialize a TTB_Scraper object

        :param ttb_id: a valid id number for the web scraper ex 17115001000140
        """
        self.ttb_id = ttb_id
        self.session = requests.Session()

    def get_soup(self, action):
        """Get soup of query"""

        url = r'https://www.ttbonline.gov/colasonline/viewColaDetails.do'
        params = {'action': action,
                  'ttbid': self.ttb_id}

        response = self.session.get(url, params=params)

        soup = BeautifulSoup(response.text, 'html5lib')

        return soup

    def publicDisplaySearchBasic_scraping(self):
        """
        Scrapes a basic form page of the TTB website

        :param id: the record's id number
        :return:
        """

        soup = self.get_soup('publicDisplaySearchBasic')

        trs = soup.select('form[name=colaApplicationForm] div.box tr')  # extract each table row

        if trs:
            # extract field names
            field_names = soup.select('form[name=colaApplicationForm] div.box tr strong')
            field_names = [field.get_text().strip() for field in field_names]  # convert to list

            # get cleaned version of form, removing blanks and unnecessary chars
            cleaned_form = [re.sub(r'\n|\s{2,}', '', line.get_text().replace(u'\xa0', u' ')) for line in trs]
            cleaned_form[0] = re.sub(r'Printable Version', '', cleaned_form[0])
            cleaned_form = list(filter(None, cleaned_form))  # filter out empty entries

            return [field_names, cleaned_form]
        else:
            return None

    @staticmethod
    def assign_basic_results(field_names, cleaned_form):
        """

        :param field_names: list of field names
        :param cleaned_form: list of table rows
        :return:
        """
        # put things in a queue flipped so that pop now starts us at the top of the table
        remaining_fields = deque(field_names)
        remaining_fields.reverse()
        form = deque(cleaned_form)
        form.reverse()

        curr_field = remaining_fields.pop()
        curr_field_cleaned = re.sub(r'\s|:', '', curr_field)
        last_field = ''

        prog = re.compile(re.escape('{field}'.format(field=curr_field)))

        data = {}

        while form:

            curr_line = form.pop()
            found = prog.match(curr_line)

            if found:
                inline = prog.split(curr_line, maxsplit=1)

                if inline[1]:
                    # there is text on the same line as the label, start by grabbing that
                    data[curr_field_cleaned] = inline[1]
                else:
                    data[curr_field_cleaned] = ''

                try:
                    last_field = curr_field_cleaned
                    curr_field = remaining_fields.pop()
                    curr_field_cleaned = re.sub(r'\s|:', '', curr_field)

                    prog = re.compile(re.escape('{field}'.format(field=curr_field)))

                except IndexError:
                    # no more fields
                    fields_remain = False

            else:
                data[last_field] += curr_line + '\n'

        return data

    def get_basic_form_data(self):
        """Downloads and parses basic form data (publicDisplaySearchBasic)"""
        res = self.publicDisplaySearchBasic_scraping()
        if res:
            form_data = self.assign_basic_results(*res)
        else:
            form_data = None
        return form_data

    def publicFormBasic_scraping(self):
        """
        Scrapes the publicFormBasic results (the pictures)

        :return:
        """

        soup = self.get_soup('publicFormDisplay')

        imgs = soup.select('img[alt*=Label]')  # extract all images with the word labels (ie. exclude signature)

        img_meta = [(img['alt'], r'https://www.ttbonline.gov' + img['src']) for img in imgs]

        return img_meta

    def download_images(self, verbose=True):
        """
        Attempts to download

        :param verbose: prints updates if True
        :return:
        """

        img_meta = self.publicFormBasic_scraping()  # also updates cookie JSESSIONID (needed for downloading imgs)

        if verbose:
            print('Images Found:  {}'.format(len(img_meta)))

        # attempt to download each image
        for name, url in img_meta:
            r = self.session.get(url, stream=True)

            # check status of request
            if r.status_code == 200:
                # write as binary (ie the raw data)
                if verbose:
                    print('Found:  {}'.format(name))

                label_type = re.split(r': ', name)[1]  # remove 'Label Image: '
                label_type = re.sub(r'\(|\)', '', label_type)  # remove parans
                label_type = re.sub(r' ', '-', label_type)  # replace spaces with '-'

                with open('{id}_{label_type}.jpg'.format(id=self.ttb_id, label_type=label_type), 'wb') as f:
                    for chunk in r:
                        f.write(chunk)

    def get_images(self):
        """Returns a list of PIL array images"""

        img_meta = self.publicFormBasic_scraping()  # also updates cookie JSESSIONID (needed for downloading imgs)
        imgs = []

        # attempt to download each image
        for name, url in img_meta:
            r = self.session.get(url)

            # check status of request
            if r.status_code == 200:
                imgs.append(Image.open(io.BytesIO(r.content)))

        return img_meta, imgs


def main():
    """ Main entry point of the app """

    #scraper = TTB_Scraper(17115001000140)  # funky buddah
    scraper = TTB_Scraper(16306001000152)  # blue moon, mango wheat
    data = scraper.get_basic_form_data()
    #scraper.download_images()
    imgs = scraper.get_images()
    print(data)


if __name__ == "__main__":
    """ This is executed when run from the command line """
    main()