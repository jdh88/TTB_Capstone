#!/usr/bin/env python3
"""
TTB Webscraping
"""

import datetime
import warnings
from time import sleep


import pymongo

from TTB_scraping import TTB_Scraper

__author__ = "Jonathan Hirokawa"
__version__ = "0.1.0"
__license__ = "MIT"


def sequential(start_date, stop_date, skip_tol=3):
    """
    Gather data from TTB sequentially using start and stop dates

    :param start_date:  start date for sequential scraping in format '01/24/2016'
    :param stop_date:  end date for sequential scraping in format '02/25/2017'
    :param skip_tol:  how many skips to tolerate before moving to the next date
    :return:
    """
    f = open('logfile_{start}-{stop}.txt'.format(start=start_date, stop=stop_date), 'w')

    # Set up connection to mongodb
    client = pymongo.MongoClient()  # Connect to default client
    db = client.TTB  # Get a database (note: lazy evaluation)
    TTB = db.TTB  # the actual collection

    # convert dates to datetime format
    date_start = datetime.datetime.strptime(start_date, '%m/%d/%Y')
    date_stop = datetime.datetime.strptime(stop_date, '%m/%d/%Y')

    # iterate over each date
    curr_date = date_start
    while curr_date < date_stop:
        print('Now on:  {}'.format(curr_date.strftime('%m/%d/%Y')))
        # iterate over each recieve code
        curr_reccode = 0
        while curr_reccode <= skip_tol:

            # increment each sequence
            cont_seq = True
            curr_seqnum = 1
            retry_count = 0
            while cont_seq:
                # prep the strings for the ttbid
                jdate = '{year}{day}'.format(year=curr_date.strftime('%y'), day=curr_date.strftime('%j'))
                reccode = '{:03d}'.format(curr_reccode)
                seqnum = '{:06d}'.format(curr_seqnum)

                # prep the query
                ttbid = '{jdate}{reccode}{seqnum}'.format(jdate=jdate, reccode=reccode, seqnum=seqnum)

                query = TTB_Scraper(ttbid)
                parsed_data = query.get_basic_form_data()

                # if we got a valid response
                if parsed_data:
                    query_data = {'_id': ttbid,
                                  'recieve_date': curr_date.strftime('%m/%d/%Y'),
                                  'recieve_code': reccode,
                                  'seq_num': seqnum}

                    # concatenated data we will add to our database
                    output = {**query_data, **parsed_data}

                    curr_seqnum += 1
                    retry_count = 0
                    # Insert result into database
                    try:
                        TTB.insert_one(output)
                        # print('Successfully added: {}'.format(ttbid))
                        f.write('{},1\n'.format(ttbid))
                    except pymongo.errors.DuplicateKeyError:
                        warnings.warn('_id: {ttbid} is already in database, skipping...'.format(ttbid=ttbid))
                else:
                    # stick with this sequence
                    if retry_count < skip_tol:
                        curr_seqnum += 1
                        retry_count += 1
                    else:
                        cont_seq = False
                    f.write('{},0\n'.format(ttbid))

                sleep(0.1)
            curr_reccode += 1
        curr_date += datetime.timedelta(days=1)

    f.close()



def main():
    """ Main entry point of the app """

    sequential('01/01/2016', '01/02/2016')

if __name__ == "__main__":
    """ This is executed when run from the command line """
    main()