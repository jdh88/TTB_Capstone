#!/usr/bin/env python3
"""
TTB Image Processing
"""


from time import time
import numpy as np
import pandas as pd

# basic image handling
from PIL import Image

# image processing stuff
from skimage import morphology
from skimage import filters
from skimage import color as skcolor


# image metrics: kmeans (dominant colors)
from sklearn import cluster
from sklearn.utils import shuffle
from sklearn.metrics import silhouette_score

# visualization
from matplotlib import pyplot as plt
import bokeh.plotting as bkplt


from TTB_scraping import TTB_Scraper

__author__ = "Jonathan Hirokawa"
__version__ = "0.1.0"
__license__ = "MIT"


class CalcImgMetrics(object):

    def __init__(self, img):
        """
        Helper class to run image processing scripts

        :param img: the full size, RGB PIL image
        """
        self.raw = img
        tmp = Image.Image.copy(img)  # silly non-sense work around for PIL (thumbnail is done in place)
        tmp.thumbnail((128, 128))  # TODO: change to skimage scaling
        self.scaled = np.array(tmp)  # scaled down version of the image, storing as np array
        self.img_format = None

        # assert len(self.scaled.shape) <= 2  # at most we should have an RGBA image

        # ascertain the format of the image
        if len(self.scaled.shape) == 2:
            self.img_format = 'GREY'
            self.scaled = np.tile(self.scaled, 3).reshape((*self.scaled.shape, -1))  # replicate to avoid problems in analysis
        else:
            if self.scaled.shape[2] == 4:
                self.img_format = 'RGBA'
                self.scaled = self.scaled[:, :, :3]  # drop the alpha channel in later analysis
            elif self.scaled.shape[2] == 3:
                self.img_format = 'RGB'

    @staticmethod
    def centroid_histogram(clt):
        """
        Calculates the percentage of each dominant color

        Source: pyimagesearch.com

        :param clt: kmeans cluster after fitting
        :return: percentages for each cluster
        """

        # grab the number of different clusters and create a histogram
        # based on the number of pixels assigned to each cluster
        numLabels = len(np.unique(clt.labels_))
        (hist, _) = np.histogram(clt.cluster_centers_, bins=numLabels)

        # normalize the histogram, such that it sums to one
        hist = hist.astype("float")
        hist /= hist.sum()

        # return the histogram (percentage described by each cluster)
        return hist.reshape(numLabels, 1)

    def kmeans_dom_color(self, img, max_colors=10, n_init=25, verbose=False):
        """
        Calculates the dominant colors in an image using kmeans

        :param img: numpy array shape (n,m,3)
        :param max_colors: the maximum number of possible colors to get out
        :param n_init: the number of different starting positions to try for kmeans
        :param verbose: output info when running
        :return hist: fraction of image that each color represents
        :return clusters.cluster_centers_: the 3 tuple values
        """
        t0 = time()

        w, h, d = original_shape = tuple(img.shape)
        assert d == 3
        image_array = np.reshape(img, (w * h, d))

        image_array_sample = shuffle(image_array, random_state=0)[:1000]  # take a random sample of 1000 points

        rand_state = 0  # same random state is used for repeatability

        best_silhouette = 0
        for n_colors in range(2, max_colors):
            clt = cluster.KMeans(n_clusters=n_colors, random_state=rand_state, n_init=n_init)
            clt.fit(image_array_sample)

            # if single color
            if len(np.unique(clt.labels_)) == 1:
                clusters = clt.fit(image_array_sample)
                hist = self.centroid_histogram(clusters)
                return hist, [clusters.cluster_centers_[0]]

            silhouette = silhouette_score(image_array_sample, clt.labels_, metric='euclidean')

            # Find the best one
            if silhouette > best_silhouette:
                best_silhouette = silhouette
                best_nClusters = n_colors
        if verbose:
            print("KMeans completed in: %0.3fs." % (time() - t0))
            print("Optimal number of clusters:  {}".format(best_nClusters))

        clt = cluster.KMeans(n_clusters=best_nClusters, random_state=rand_state, n_init=n_init)
        clusters = clt.fit(image_array_sample)
        hist = self.centroid_histogram(clusters)

        return hist, clusters.cluster_centers_

    @staticmethod
    def total_entropy(img):
        """
        Calculate the sum of the entropy of an image

        :param img: an m x n x 3 numpy array
        """

        img_grey = skcolor.rgb2grey(img)
        ent = filters.rank.entropy(img_grey, morphology.disk(4))
        return np.sum(ent)

    @staticmethod
    def visualize_dom_colors(percentages, colors, img):
        """
        Create a plot of the dominant colors, where size of swatch represents proportion of that color

        Please excuse the horrendous mixing of bokeh and matplotlib
        """

        fig = bkplt.figure()

        x_offset = 0
        for (percentage, color) in zip(percentages, colors):
            print('{}-{}-{}'.format(x_offset, percentage,color))
            fig.quad(left=x_offset, right=x_offset + percentage, top=0.5, bottom=-0.5, fill_color=tuple(color))
            x_offset += percentage[0]

        bkplt.show(fig)
        plt.imshow(img)
        plt.show()

    def calc_all_metrics(self):
        """
        Calls all metrics

        :return: a pandas dataframe
        """

        # kmeans dominant clusters
        percentage, rgb_vals = self.kmeans_dom_color(self.scaled)

        # entropy
        ent = self.total_entropy(self.scaled)

        # must be done with concatination so that pandas expands df appropriately
        df_color = pd.concat([pd.DataFrame(percentage), pd.DataFrame(rgb_vals)], axis=1)
        df_color.columns = ['percentage', 'r', 'g', 'b']

        return df_color, ent


def main():
    """ Main entry point of the app """

    #scraper = TTB_Scraper(16306001000152)  # blue moon, mango wheat
    scraper = TTB_Scraper(16001001000052)  # blue moon, mango wheat

    meta, imgs = scraper.get_images()
    print(meta)
    metric_calculator = CalcImgMetrics(imgs[1])
    colors, entropy = metric_calculator.calc_all_metrics()
    print(colors)
    print(entropy)


if __name__ == "__main__":
    """ This is executed when run from the command line """
    main()