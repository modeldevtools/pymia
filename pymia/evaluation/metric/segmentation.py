"""The segmentation module provides metrics to measure image segmentation performance."""
import abc
import math
import warnings

import numpy as np
import SimpleITK as sitk

from .base import (ConfusionMatrixMetric, DistanceMetric, SimpleITKImageMetric, NumpyArrayMetric,
                   NotComputableMetricWarning)


class AreaMetric(SimpleITKImageMetric, abc.ABC):

    def __init__(self, metric: str = 'AREA'):
        """Represents an area metric base class.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    @staticmethod
    def _calculate_area(image: sitk.Image, slice_number: int = -1) -> float:
        """Calculates the area of a slice in a label image.

        Args:
            image (sitk.Image): The 3-D label image.
            slice_number (int): The slice number to calculate the area.
                Defaults to -1, which will calculate the area on the intermediate slice.
        """

        img_arr = sitk.GetArrayFromImage(image)

        if slice_number == -1:
            slice_number = int(img_arr.shape[0] / 2)  # use the intermediate slice

        return img_arr[slice_number, ...].sum() * image.GetSpacing()[0] * image.GetSpacing()[1]


class VolumeMetric(SimpleITKImageMetric, abc.ABC):

    def __init__(self, metric: str = 'VOL'):
        """Represents a volume metric base class.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    @staticmethod
    def _calculate_volume(image: sitk.Image) -> float:
        """Calculates the volume of a label image.

        Args:
            image (sitk.Image): The 3-D label image.
        """

        voxel_volume = np.prod(image.GetSpacing())
        number_of_voxels = sitk.GetArrayFromImage(image).sum()

        return number_of_voxels * voxel_volume


class Accuracy(ConfusionMatrixMetric):

    def __init__(self, metric: str = 'ACURCY'):
        """Represents an accuracy metric.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    def calculate(self):
        """Calculates the accuracy."""

        sum_ = self.confusion_matrix.tp + self.confusion_matrix.tn + self.confusion_matrix.fp + self.confusion_matrix.fn

        if sum_ != 0:
            return (self.confusion_matrix.tp + self.confusion_matrix.tn) / sum_
        else:
            return 0


class AdjustedRandIndex(ConfusionMatrixMetric):

    def __init__(self, metric: str = 'ADJRIND'):
        """Represents an adjusted rand index metric.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    def calculate(self):
        """Calculates the adjusted rand index."""

        tp = self.confusion_matrix.tp
        tn = self.confusion_matrix.tn
        fp = self.confusion_matrix.fp
        fn = self.confusion_matrix.fn
        n = self.confusion_matrix.n

        fp_tn = tn + fp
        tp_fn = fn + tp
        tn_fn = tn + fn
        tp_fp = fp + tp
        nis = tn_fn * tn_fn + tp_fp * tp_fp
        njs = fp_tn * fp_tn + tp_fn * tp_fn
        sum_of_squares = tp * tp + tn * tn + fp * fp + fn * fn

        a = (tp * (tp - 1) + fp * (fp - 1) + tn * (tn - 1) + fn * (fn - 1)) / 2.
        b = (njs - sum_of_squares) / 2.
        c = (nis - sum_of_squares) / 2.
        d = (n * n + sum_of_squares - nis - njs) / 2.

        x1 = a - ((a + c) * (a + b) / (a + b + c + d))
        x2 = ((a + c) + (a + b)) / 2.
        x3 = ((a + c) * (a + b)) / (a + b + c + d)
        denominator = x2 - x3

        if denominator != 0:
            return x1 / denominator
        else:
            return 0


class AreaUnderCurve(ConfusionMatrixMetric):

    def __init__(self, metric: str = 'AUC'):
        """Represents an area under the curve metric.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    def calculate(self):
        """Calculates the area under the curve."""

        specificity = self.confusion_matrix.tn / (self.confusion_matrix.tn + self.confusion_matrix.fp)

        false_positive_rate = 1 - specificity

        if (self.confusion_matrix.tp + self.confusion_matrix.fn) == 0:
            warnings.warn('Unable to compute area under the curve due to division by zero, returning -inf',
                          NotComputableMetricWarning)
            return float('-inf')

        true_positive_rate = self.confusion_matrix.tp / (self.confusion_matrix.tp + self.confusion_matrix.fn)

        return (true_positive_rate - false_positive_rate + 1) / 2


class AverageDistance(SimpleITKImageMetric):

    def __init__(self, metric: str = 'AVGDIST'):
        """Represents an average (Hausdorff) distance metric.

        Calculates the distance between the set of non-zero pixels of two images using the following equation:

        .. math:: AVD(A,B) = max(d(A,B), d(B,A)),

        where

        .. math:: d(A,B) = \\frac{1}{N} \\sum_{a \\in A} \\min_{b \\in B} \\lVert a - b \\rVert

        is the directed Hausdorff distance and :math:`A` and :math:`B` are the set of non-zero pixels in the images.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    def calculate(self):
        """Calculates the average (Hausdorff) distance."""

        if np.count_nonzero(sitk.GetArrayFromImage(self.reference)) == 0:
            warnings.warn('Unable to compute average distance due to empty label mask, returning inf',
                          NotComputableMetricWarning)
            return float('inf')
        if np.count_nonzero(sitk.GetArrayFromImage(self.prediction)) == 0:
            warnings.warn('Unable to compute average distance due to empty segmentation mask, returning inf',
                          NotComputableMetricWarning)
            return float('inf')

        distance_filter = sitk.HausdorffDistanceImageFilter()
        distance_filter.Execute(self.reference, self.prediction)
        return distance_filter.GetAverageHausdorffDistance()


class CohenKappaCoefficient(ConfusionMatrixMetric):

    def __init__(self, metric: str = 'KAPPA'):
        """Represents a Cohen's kappa coefficient metric.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    def calculate(self):
        """Calculates the Cohen's kappa coefficient."""

        tp = self.confusion_matrix.tp
        tn = self.confusion_matrix.tn
        fp = self.confusion_matrix.fp
        fn = self.confusion_matrix.fn

        agreement = tp + tn
        chance0 = (tn + fn) * (tn + fp)
        chance1 = (fp + tp) * (fn + tp)
        sum_ = tn + fn + fp + tp
        chance = (chance0 + chance1) / sum_

        if (sum_ - chance) == 0:
            warnings.warn('Unable to compute Cohen\'s kappa coefficient due to division by zero, returning -inf',
                          NotComputableMetricWarning)
            return float('-inf')

        return (agreement - chance) / (sum_ - chance)


class DiceCoefficient(ConfusionMatrixMetric):

    def __init__(self, metric: str = 'DICE'):
        """Represents a Dice coefficient metric with empty target handling, defined as:

        .. math:: \\begin{cases} 1 & \\left\\vert{y}\\right\\vert = \\left\\vert{\\hat y}\\right\\vert = 0 \\\\ Dice(y,\\hat y) & \\left\\vert{y}\\right\\vert > 0 \\\\ \\end{cases}

        where :math:`\\hat y` is the prediction and :math:`y` the target.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    def calculate(self):
        """Calculates the Dice coefficient."""

        if (self.confusion_matrix.tp == 0) and \
                ((self.confusion_matrix.tp + self.confusion_matrix.fp + self.confusion_matrix.fn) == 0):
            return 1.

        return 2 * self.confusion_matrix.tp / \
               (2 * self.confusion_matrix.tp + self.confusion_matrix.fp + self.confusion_matrix.fn)


class FalseNegative(ConfusionMatrixMetric):

    def __init__(self, metric: str = 'FN'):
        """Represents a false negative metric.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    def calculate(self):
        """Calculates the false negatives."""

        return self.confusion_matrix.fn


class FalsePositive(ConfusionMatrixMetric):

    def __init__(self, metric: str = 'FP'):
        """Represents a false positive metric.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    def calculate(self):
        """Calculates the false positives."""

        return self.confusion_matrix.fp


class Fallout(ConfusionMatrixMetric):

    def __init__(self, metric: str = 'FALLOUT'):
        """Represents a fallout (false positive rate) metric.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    def calculate(self):
        """Calculates the fallout (false positive rate)."""

        specificity = self.confusion_matrix.tn / (self.confusion_matrix.tn + self.confusion_matrix.fp)
        return 1 - specificity


class FalseNegativeRate(ConfusionMatrixMetric):

    def __init__(self, metric: str = 'FNR'):
        """Represents a false negative rate metric.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    def calculate(self):
        """Calculates the false negative rate."""

        sensitivity = self.confusion_matrix.tp / (self.confusion_matrix.tp + self.confusion_matrix.fn)
        return 1 - sensitivity


class FMeasure(ConfusionMatrixMetric):

    def __init__(self, beta: float = 1.0, metric: str = 'FMEASR'):
        """Represents a F-measure metric.

        Args:
            beta (float): The beta to trade-off precision and recall.
                Use 0.5 or 2 to calculate the F0.5 and F2 measure, respectively.
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)
        self.beta = beta

    def calculate(self):
        """Calculates the F1 measure."""

        beta_squared = self.beta * self.beta
        precision = Precision()
        precision.confusion_matrix = self.confusion_matrix
        precision = precision.calculate()
        recall = Recall()
        recall.confusion_matrix = self.confusion_matrix
        recall = recall.calculate()

        denominator = beta_squared * precision + recall

        if denominator != 0:
            return (1 + beta_squared) * ((precision * recall) / denominator)
        else:
            return 0


class GlobalConsistencyError(ConfusionMatrixMetric):

    def __init__(self, metric: str = 'GCOERR'):
        """Represents a global consistency error metric.

        Implementation based on Martin 2001. todo(fabianbalsiger): add entire reference

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    def calculate(self):
        """Calculates the global consistency error."""

        tp = self.confusion_matrix.tp
        tn = self.confusion_matrix.tn
        fp = self.confusion_matrix.fp
        fn = self.confusion_matrix.fn

        if (tp + fn) == 0 or (tn + fp) == 0 or (tp + fp) == 0 or (tn + fn) == 0:
            warnings.warn('Unable to compute global consistency error due to division by zero, returning inf',
                          NotComputableMetricWarning)
            return float('inf')

        n = tp + tn + fp + fn
        e1 = (fn * (fn + 2 * tp) / (tp + fn) + fp * (fp + 2 * tn) / (tn + fp)) / n
        e2 = (fp * (fp + 2 * tp) / (tp + fp) + fn * (fn + 2 * tn) / (tn + fn)) / n

        return min(e1, e2)


class GroundTruthArea(AreaMetric):

    def __init__(self, slice_number: int = -1, metric: str = 'GTAREA'):
        """Represents a ground truth area metric.

        Args:
            slice_number (int): The slice number to calculate the area.
                Defaults to -1, which will calculate the area on the intermediate slice.
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)
        self.slice_number = slice_number

    def calculate(self):
        """Calculates the ground truth area on a specified slice in mm2."""

        return self._calculate_area(self.reference, self.slice_number)


class GroundTruthVolume(VolumeMetric):

    def __init__(self, metric: str = 'GTVOL'):
        """Represents a ground truth volume metric.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    def calculate(self):
        """Calculates the ground truth volume in mm3."""

        return self._calculate_volume(self.reference)


class HausdorffDistance(DistanceMetric):

    def __init__(self, percentile: float = 100.0, metric: str = 'HDRFDST'):
        """Represents a Hausdorff distance metric.

        Calculates the distance between the set of non-zero pixels of two images using the following equation:

        .. math:: H(A,B) = max(h(A,B), h(B,A)),

        where

        .. math:: h(A,B) = \\max_{a \\in A} \\min_{b \\in B} \\lVert a - b \\rVert

        is the directed Hausdorff distance and :math:`A` and :math:`B` are the set of non-zero pixels in the images.

        Args:
            percentile (float): The percentile (0, 100] to compute, i.e. 100 computes the Hausdorff distance and
                95 computes the 95th Hausdorff distance.
            metric (str): The identification string of the metric.

        See Also:
            - Nikolov, S., Blackwell, S., Mendes, R., De Fauw, J., Meyer, C., Hughes, C., … Ronneberger, O. (2018). Deep learning to achieve clinically applicable segmentation of head and neck anatomy for radiotherapy. http://arxiv.org/abs/1809.04430
            - `Original implementation <https://github.com/deepmind/surface-distance>`_
        """
        super().__init__(metric)
        self.percentile = percentile

    def calculate(self):
        """Calculates the Hausdorff distance."""

        if self.distances.distances_gt_to_pred is not None and len(self.distances.distances_gt_to_pred) > 0:
            surfel_areas_cum_gt = np.cumsum(self.distances.surfel_areas_gt) / np.sum(self.distances.surfel_areas_gt)
            idx = np.searchsorted(surfel_areas_cum_gt, self.percentile / 100.0)
            perc_distance_gt_to_pred = self.distances.distances_gt_to_pred[
                min(idx, len(self.distances.distances_gt_to_pred) - 1)]
        else:
            warnings.warn('Unable to compute Hausdorff distance due to empty label mask, returning inf',
                          NotComputableMetricWarning)
            return float('inf')

        if self.distances.distances_pred_to_gt is not None and len(self.distances.distances_pred_to_gt) > 0:
            surfel_areas_cum_pred = (np.cumsum(self.distances.surfel_areas_pred) /
                                     np.sum(self.distances.surfel_areas_pred))
            idx = np.searchsorted(surfel_areas_cum_pred, self.percentile / 100.0)
            perc_distance_pred_to_gt = self.distances.distances_pred_to_gt[
                min(idx, len(self.distances.distances_pred_to_gt) - 1)]
        else:
            warnings.warn('Unable to compute Hausdorff distance due to empty segmentation mask, returning inf',
                          NotComputableMetricWarning)
            return float('inf')

        return max(perc_distance_gt_to_pred, perc_distance_pred_to_gt)


class InterclassCorrelation(NumpyArrayMetric):

    def __init__(self, metric: str = 'ICCORR'):
        """Represents an interclass correlation metric.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    def calculate(self):
        """Calculates the interclass correlation."""

        gt = self.reference.flatten()
        seg = self.prediction.flatten()

        n = gt.size
        mean_gt = gt.mean()
        mean_seg = seg.mean()
        mean = (mean_gt + mean_seg) / 2

        m = (gt + seg) / 2
        ssw = np.power(gt - m, 2).sum() + np.power(seg - m, 2).sum()
        ssb = np.power(m - mean, 2).sum()

        ssw /= n
        ssb = ssb / (n - 1) * 2

        if (ssb + ssw) == 0:
            warnings.warn('Unable to compute interclass correlation due to division by zero, returning -inf',
                          NotComputableMetricWarning)
            return float('-inf')

        return (ssb - ssw) / (ssb + ssw)


class JaccardCoefficient(ConfusionMatrixMetric):

    def __init__(self, metric: str = 'JACRD'):
        """Represents a Jaccard coefficient metric.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    def calculate(self):
        """Calculates the Jaccard coefficient."""

        tp = self.confusion_matrix.tp
        fp = self.confusion_matrix.fp
        fn = self.confusion_matrix.fn

        if (tp + fp + fn) == 0:
            warnings.warn('Unable to compute Jaccard coefficient due to division by zero, returning -inf',
                          NotComputableMetricWarning)
            return float('-inf')

        return tp / (tp + fp + fn)


class MahalanobisDistance(NumpyArrayMetric):

    def __init__(self, metric: str = 'MAHLNBS'):
        """Represents a Mahalanobis distance metric.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    def calculate(self):
        """Calculates the Mahalanobis distance."""

        gt_n = np.count_nonzero(self.reference)
        seg_n = np.count_nonzero(self.prediction)

        if gt_n == 0:
            warnings.warn('Unable to compute Mahalanobis distance due to empty label mask, returning inf',
                          NotComputableMetricWarning)
            return float('inf')
        if seg_n == 0:
            warnings.warn('Unable to compute Mahalanobis distance due to empty segmentation mask, returning inf',
                          NotComputableMetricWarning)
            return float('inf')

        gt_indices = np.flip(np.where(self.reference == 1), axis=0)
        gt_mean = gt_indices.mean(axis=1)
        gt_cov = np.cov(gt_indices)

        seg_indices = np.flip(np.where(self.prediction == 1), axis=0)
        seg_mean = seg_indices.mean(axis=1)
        seg_cov = np.cov(seg_indices)

        # calculate common covariance matrix
        common_cov = (gt_n * gt_cov + seg_n * seg_cov) / (gt_n + seg_n)
        common_cov_inv = np.linalg.inv(common_cov)

        mean = gt_mean - seg_mean
        return math.sqrt(mean.dot(common_cov_inv).dot(mean.T))


class MutualInformation(ConfusionMatrixMetric):

    def __init__(self, metric: str = 'MUTINF'):
        """Represents a mutual information metric.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    def calculate(self):
        """Calculates the mutual information."""

        tp = self.confusion_matrix.tp
        tn = self.confusion_matrix.tn
        fp = self.confusion_matrix.fp
        fn = self.confusion_matrix.fn
        n = self.confusion_matrix.n

        fn_tp = fn + tp
        fp_tp = fp + tp

        if fn_tp == 0 or fn_tp / n == 1 or fp_tp == 0 or fp_tp / n == 1:
            warnings.warn('Unable to compute mutual information due to log2 of 0, returning -inf',
                          NotComputableMetricWarning)
            return float('-inf')

        h1 = -((fn_tp / n) * math.log2(fn_tp / n) + (1 - fn_tp / n) * math.log2(1 - fn_tp / n))
        h2 = -((fp_tp / n) * math.log2(fp_tp / n) + (1 - fp_tp / n) * math.log2(1 - fp_tp / n))

        p00 = 1 if tn == 0 else (tn / n)
        p01 = 1 if fn == 0 else (fn / n)
        p10 = 1 if fp == 0 else (fp / n)
        p11 = 1 if tp == 0 else (tp / n)

        h12 = -((tn / n) * math.log2(p00) +
                (fn / n) * math.log2(p01) +
                (fp / n) * math.log2(p10) +
                (tp / n) * math.log2(p11))

        mi = h1 + h2 - h12
        return mi


class Precision(ConfusionMatrixMetric):

    def __init__(self, metric: str = 'PRCISON'):
        """Represents a precision metric.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    def calculate(self):
        """Calculates the precision."""

        sum_ = self.confusion_matrix.tp + self.confusion_matrix.fp

        if sum_ != 0:
            return self.confusion_matrix.tp / sum_
        else:
            return 0


class ProbabilisticDistance(NumpyArrayMetric):

    def __init__(self, metric: str = 'PROBDST'):
        """Represents a probabilistic distance metric.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    def calculate(self):
        """Calculates the probabilistic distance."""

        gt = self.reference.flatten().astype(np.int8)
        seg = self.prediction.flatten().astype(np.int8)

        probability_difference = np.absolute(gt - seg).sum()
        probability_joint = (gt * seg).sum()

        if probability_joint != 0:
            return probability_difference / (2. * probability_joint)
        else:
            return -1


class RandIndex(ConfusionMatrixMetric):

    def __init__(self, metric: str = 'RNDIND'):
        """Represents a rand index metric.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    def calculate(self):
        """Calculates the rand index."""

        tp = self.confusion_matrix.tp
        tn = self.confusion_matrix.tn
        fp = self.confusion_matrix.fp
        fn = self.confusion_matrix.fn
        n = self.confusion_matrix.n

        fp_tn = tn + fp
        tp_fn = fn + tp
        tn_fn = tn + fn
        tp_fp = fp + tp
        nis = tn_fn * tn_fn + tp_fp * tp_fp
        njs = fp_tn * fp_tn + tp_fn * tp_fn
        sum_of_squares = tp * tp + tn * tn + fp * fp + fn * fn

        a = (tp * (tp - 1) + fp * (fp - 1) + tn * (tn - 1) + fn * (fn - 1)) / 2.
        b = (njs - sum_of_squares) / 2.
        c = (nis - sum_of_squares) / 2.
        d = (n * n + sum_of_squares - nis - njs) / 2.

        return (a + d) / (a + b + c + d)


class Recall(ConfusionMatrixMetric):

    def __init__(self, metric: str = 'RECALL'):
        """Represents a recall metric.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    def calculate(self):
        """Calculates the recall."""

        sum_ = self.confusion_matrix.tp + self.confusion_matrix.fn

        if sum_ != 0:
            return self.confusion_matrix.tp / sum_
        else:
            return 0


class SegmentationArea(AreaMetric):

    def __init__(self, slice_number: int = -1, metric: str = 'SEGAREA'):
        """Represents a segmentation area metric.

        Args:
            slice_number (int): The slice number to calculate the area.
                Defaults to -1, which will calculate the area on the intermediate slice.
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)
        self.slice_number = slice_number

    def calculate(self):
        """Calculates the segmentation area on a specified slice in mm2."""

        return self._calculate_area(self.prediction, self.slice_number)


class SegmentationVolume(VolumeMetric):

    def __init__(self, metric: str = 'SEGVOL'):
        """Represents a segmentation volume metric.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    def calculate(self):
        """Calculates the segmented volume in mm3."""

        return self._calculate_volume(self.prediction)


class Sensitivity(ConfusionMatrixMetric):

    def __init__(self, metric: str = 'SNSVTY'):
        """Represents a sensitivity (true positive rate or recall) metric.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    def calculate(self):
        """Calculates the sensitivity (true positive rate)."""

        if (self.confusion_matrix.tp + self.confusion_matrix.fn) == 0:
            warnings.warn('Unable to compute sensitivity due to division by zero, returning -inf',
                          NotComputableMetricWarning)
            return float('-inf')

        return self.confusion_matrix.tp / (self.confusion_matrix.tp + self.confusion_matrix.fn)


class Specificity(ConfusionMatrixMetric):

    def __init__(self, metric: str = 'SPCFTY'):
        """Represents a specificity metric.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    def calculate(self):
        """Calculates the specificity."""

        return self.confusion_matrix.tn / (self.confusion_matrix.tn + self.confusion_matrix.fp)


class SurfaceDiceOverlap(DistanceMetric):

    def __init__(self, tolerance: float = 1, metric: str = 'SURFDICE'):
        """Represents a surface Dice coefficient overlap metric.

        Args:
            tolerance (float): The tolerance of the surface distance in mm.
            metric (str): The identification string of the metric.

        See Also:
            - Nikolov, S., Blackwell, S., Mendes, R., De Fauw, J., Meyer, C., Hughes, C., … Ronneberger, O. (2018). Deep learning to achieve clinically applicable segmentation of head and neck anatomy for radiotherapy. http://arxiv.org/abs/1809.04430
            - `Original implementation <https://github.com/deepmind/surface-distance>`_
        """
        super().__init__(metric)
        self.tolerance = tolerance

    def calculate(self):
        """Calculates the surface Dice coefficient overlap."""

        if self.distances.surfel_areas_pred is None:
            warnings.warn('Unable to compute surface Dice coefficient overlap due to empty segmentation mask, returning -inf',
                          NotComputableMetricWarning)
            return float('-inf')

        if self.distances.surfel_areas_gt is None:
            warnings.warn('Unable to compute surface Dice coefficient overlap due to empty label mask, returning -inf',
                          NotComputableMetricWarning)
            return float('-inf')

        overlap_gt = np.sum(self.distances.surfel_areas_gt[self.distances.distances_gt_to_pred <= self.tolerance])
        overlap_pred = np.sum(self.distances.surfel_areas_pred[self.distances.distances_pred_to_gt <= self.tolerance])
        surface_dice = (overlap_gt + overlap_pred) / \
                       (np.sum(self.distances.surfel_areas_gt) + np.sum(self.distances.surfel_areas_pred))
        return float(surface_dice)


class SurfaceOverlap(DistanceMetric):

    def __init__(self, tolerance: float = 1.0, prediction_to_label: bool = True, metric: str = 'SURFOVLP'):
        """Represents a surface overlap metric.

        Computes the overlap of the ground truth surface with the predicted surface and vice versa allowing a
        specified tolerance (maximum surface-to-surface distance that is regarded as overlapping).
        The overlapping fraction is computed by correctly taking the area of each surface element into account.

        Args:
            tolerance (float): The tolerance of the surface distance in mm.
            prediction_to_label (bool): Computes the prediction to labels if `True`, otherwise the label to prediction.
            metric (str): The identification string of the metric.

        See Also:
            - Nikolov, S., Blackwell, S., Mendes, R., De Fauw, J., Meyer, C., Hughes, C., … Ronneberger, O. (2018). Deep learning to achieve clinically applicable segmentation of head and neck anatomy for radiotherapy. http://arxiv.org/abs/1809.04430
            - `Original implementation <https://github.com/deepmind/surface-distance>`_
        """
        super().__init__(metric)
        self.tolerance = tolerance
        self.prediction_to_label = prediction_to_label

    def calculate(self):
        """Calculates the surface overlap."""

        if self.prediction_to_label:
            if self.distances.surfel_areas_pred is not None and np.sum(self.distances.surfel_areas_pred) > 0:
                return float(
                    np.sum(self.distances.surfel_areas_pred[self.distances.distances_pred_to_gt <= self.tolerance])
                    / np.sum(self.distances.surfel_areas_pred))
            else:
                warnings.warn('Unable to compute surface overlap due to empty segmentation mask, returning -inf',
                              NotComputableMetricWarning)
                return float('-inf')
        else:
            if self.distances.surfel_areas_gt is not None and np.sum(self.distances.surfel_areas_gt) > 0:
                return float(
                    np.sum(self.distances.surfel_areas_gt[self.distances.distances_gt_to_pred <= self.tolerance])
                    / np.sum(self.distances.surfel_areas_gt))
            else:
                warnings.warn('Unable to compute surface overlap due to empty label mask, returning -inf',
                              NotComputableMetricWarning)
                return float('-inf')


class TrueNegative(ConfusionMatrixMetric):

    def __init__(self, metric: str = 'TN'):
        """Represents a true negative metric.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    def calculate(self):
        """Calculates the true negatives."""

        return self.confusion_matrix.tn


class TruePositive(ConfusionMatrixMetric):

    def __init__(self, metric: str = 'TP'):
        """Represents a true positive metric.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    def calculate(self):
        """Calculates the true positives."""

        return self.confusion_matrix.tp


class VariationOfInformation(ConfusionMatrixMetric):

    def __init__(self, metric: str = 'VARINFO'):
        """Represents a variation of information metric.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    def calculate(self):
        """Calculates the variation of information."""

        tp = self.confusion_matrix.tp
        tn = self.confusion_matrix.tn
        fp = self.confusion_matrix.fp
        fn = self.confusion_matrix.fn
        n = self.confusion_matrix.n

        fn_tp = fn + tp
        fp_tp = fp + tp

        if fn_tp == 0 or fn_tp / n == 1 or fp_tp == 0 or fp_tp / n == 1:
            warnings.warn('Unable to compute variation of information due to log2 of 0, returning -inf',
                          NotComputableMetricWarning)
            return float('-inf')

        h1 = -((fn_tp / n) * math.log2(fn_tp / n) + (1 - fn_tp / n) * math.log2(1 - fn_tp / n))
        h2 = -((fp_tp / n) * math.log2(fp_tp / n) + (1 - fp_tp / n) * math.log2(1 - fp_tp / n))

        p00 = 1 if tn == 0 else (tn / n)
        p01 = 1 if fn == 0 else (fn / n)
        p10 = 1 if fp == 0 else (fp / n)
        p11 = 1 if tp == 0 else (tp / n)

        h12 = -((tn / n) * math.log2(p00) +
                (fn / n) * math.log2(p01) +
                (fp / n) * math.log2(p10) +
                (tp / n) * math.log2(p11))

        mi = h1 + h2 - h12

        vi = h1 + h2 - 2 * mi
        return vi


class VolumeSimilarity(ConfusionMatrixMetric):

    def __init__(self, metric: str = 'VOLSMTY'):
        """Represents a volume similarity metric.

        Args:
            metric (str): The identification string of the metric.
        """
        super().__init__(metric)

    def calculate(self):
        """Calculates the volume similarity."""

        tp = self.confusion_matrix.tp
        fp = self.confusion_matrix.fp
        fn = self.confusion_matrix.fn

        if (tp + fn + fp) == 0:
            warnings.warn('Unable to compute volume similarity due to division by zero, returning -inf',
                          NotComputableMetricWarning)
            return float('-inf')

        return 1 - abs(fn - fp) / (2 * tp + fn + fp)
