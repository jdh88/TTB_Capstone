#!/usr/bin/env python3
"""
TTB Webscraping
"""

import datetime
import warnings
from time import sleep
import logging

import re
import pymongo
import pandas as pd

from tqdm import tqdm

from TTB_scraping import TTB_Scraper
from Image_Processing import CalcImgMetrics

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
    #f = open('logfile_{start}-{stop}.txt'.format(start=start_date, stop=stop_date), 'w')

    logging.basicConfig(filename='Form_Scrape {}.log'.format(datetime.datetime.now()), level=logging.ERROR)
    logger = logging.getLogger(__name__)  # having set the logging level to error for all modules
    logger.setLevel(logging.DEBUG)  # we now set the logging level to debug for our module


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
                        #f.write('{},1\n'.format(ttbid))
                        logger.info('Successfully added:  {ttbid}'.format(ttbid=ttbid))
                    except pymongo.errors.DuplicateKeyError:
                        #warnings.warn('_id: {ttbid} is already in database, skipping...'.format(ttbid=ttbid))
                        logger.warning('TTBID already in database, skipping:  {ttbid}'.format(ttbid=ttbid))
                else:
                    # stick with this sequence
                    if retry_count < skip_tol:
                        curr_seqnum += 1
                        retry_count += 1
                    else:
                        cont_seq = False
                    #f.write('{},0\n'.format(ttbid))
                    logger.info('No data found for:  {ttbid}'.format(ttbid=ttbid))

                sleep(0.1)
            curr_reccode += 1
        curr_date += datetime.timedelta(days=1)

    #f.close()


def image_scrape(ttbid_list):
    logging.basicConfig(filename='Img_Scrape {}.log'.format(datetime.datetime.now()), level=logging.ERROR)
    logger = logging.getLogger(__name__)  # having set the logging level to error for all modules
    logger.setLevel(logging.DEBUG)  # we now set the logging level to debug for our module

    # Set up connection to mongodb
    client = pymongo.MongoClient()  # Connect to default client
    db = client.TTB  # Get a database (note: lazy evaluation)

    COLORS = db.COLORS  # the actual collection
    IMG_META = db.IMG_META
    IMG_SUP = db.IMG_SUP

    for curr_id in tqdm(ttbid_list):
        query = TTB_Scraper(curr_id)
        [meta, imgs] = query.get_images()

        if imgs:

            for im_num, (metadata, img) in enumerate(zip(meta, imgs)):

                # calculate our image metrics
                metrics = CalcImgMetrics(img)
                df_color, sum_entropy = metrics.calc_all_metrics()

                # convert things into pandas tables since its easier than futzing with dicts
                # add the ttbid id and some additional meta information so we can join tables better in the future
                n_rows = df_color.shape[0]
                df_color['TTBID'] = [str(curr_id)] * n_rows # add column with ttbid
                df_color['img_num'] = [str(im_num)] * n_rows

                df_img_meta = pd.DataFrame()
                df_img_meta['LabelName'] = [re.sub('Label Image: ', '', metadata[0])]
                df_img_meta['URL'] = [metadata[1]]
                df_img_meta['TTBID'] = [str(curr_id)] * df_img_meta.shape[0]
                df_img_meta['ImgType'] = [metrics.img_format]

                df_sup = pd.DataFrame()
                df_sup['TTBID'] = [str(curr_id)]
                df_sup['EntropySum'] = [sum_entropy]

                # COLOR collection
                try:
                    COLORS.insert_many(df_color.to_dict('records'))
                    logger.info('Successfully added data to COLORS. TTBID: {ttbid} IMG: {im_num}'.format(ttbid=curr_id, im_num=im_num))
                except pymongo.errors.DuplicateKeyError:
                    logger.warning('Failed to add data to COLORS. TTBID: {ttbid} IMG: {im_num} already present'.format(ttbid=curr_id, im_num=im_num))

                # IMG_META collection
                try:
                    IMG_META.insert_many(df_img_meta.to_dict('records'))
                    logger.info('Successfully added data to IMG_META. TTBID: {ttbid} IMG: {im_num}'.format(ttbid=curr_id, im_num=im_num))
                except pymongo.errors.DuplicateKeyError:
                    logger.warning('Failed to add data to IMG_META. TTBID: {ttbid} IMG: {im_num} already present'.format(ttbid=curr_id, im_num=im_num))

                # IMG_SUP collection
                try:
                    IMG_SUP.insert_many(df_sup.to_dict('records'))
                    logger.info('Successfully added data to IMG_SUP. TTBID: {ttbid} IMG: {im_num}'.format(ttbid=curr_id, im_num=im_num))
                except pymongo.errors.DuplicateKeyError:
                    logger.warning('Failed to add data to IMG_SUP. TTBID: {ttbid} IMG: {im_num} already present'.format(ttbid=curr_id, im_num=im_num))

        else:
            logger.warning('Skipping {ttbid}, unable to access images'.format(ttbid=curr_id))


def main():
    """ Main entry point of the app """

    #sequential('01/01/2016', '01/02/2016')  # main form data
    image_scrape([16306001000152])

if __name__ == "__main__":
    """ This is executed when run from the command line """
    main()