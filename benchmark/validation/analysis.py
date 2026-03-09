"""Accuracy analysis and correlation metrics."""
import math
from typing import Dict, List

class AccuracyAnalysis:
    @staticmethod
    def compute_error(measured: List[float], reference: List[float]) -> Dict[str, float]:
        if not measured or not reference:
            return {"mape": 0, "max_error": 0, "rmse": 0}
        errors = []
        for m, r in zip(measured, reference):
            if r > 0:
                errors.append(abs(m - r) / r * 100)
        mape = sum(errors) / len(errors) if errors else 0
        max_error = max(errors) if errors else 0
        squared_errors = [(m - r) ** 2 for m, r in zip(measured, reference)]
        rmse = math.sqrt(sum(squared_errors) / len(squared_errors)) if squared_errors else 0
        return {"mape": mape, "max_error": max_error, "rmse": rmse}

    @staticmethod
    def compute_correlation(x: List[float], y: List[float]) -> Dict[str, float]:
        if len(x) < 2 or len(y) < 2 or len(x) != len(y):
            return {"pearson_r": 0, "spearman_r": 0, "r_squared": 0}
        n = len(x)
        x_mean = sum(x) / n
        y_mean = sum(y) / n
        cov = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y)) / n
        x_std = math.sqrt(sum((xi - x_mean) ** 2 for xi in x) / n)
        y_std = math.sqrt(sum((yi - y_mean) ** 2 for yi in y) / n)
        pearson_r = cov / (x_std * y_std) if x_std > 0 and y_std > 0 else 0
        x_ranks = AccuracyAnalysis._rank(x)
        y_ranks = AccuracyAnalysis._rank(y)
        d_squared = sum((rx - ry) ** 2 for rx, ry in zip(x_ranks, y_ranks))
        spearman_r = 1 - (6 * d_squared) / (n * (n ** 2 - 1)) if n > 1 else 0
        return {"pearson_r": pearson_r, "spearman_r": spearman_r, "r_squared": pearson_r ** 2}

    @staticmethod
    def compute_r_squared(x: List[float], y: List[float]) -> float:
        if len(x) < 2:
            return 0
        n = len(x)
        x_mean = sum(x) / n
        y_mean = sum(y) / n
        ss_tot = sum((yi - y_mean) ** 2 for yi in y)
        if ss_tot == 0:
            return 1.0
        x_sum = sum(x)
        y_sum = sum(y)
        xy_sum = sum(xi * yi for xi, yi in zip(x, y))
        x2_sum = sum(xi ** 2 for xi in x)
        denom = n * x2_sum - x_sum ** 2
        if denom == 0:
            return 0
        slope = (n * xy_sum - x_sum * y_sum) / denom
        intercept = (y_sum - slope * x_sum) / n
        y_pred = [slope * xi + intercept for xi in x]
        ss_res = sum((yi - ypi) ** 2 for yi, ypi in zip(y, y_pred))
        return 1 - ss_res / ss_tot

    @staticmethod
    def _rank(values: List[float]) -> List[float]:
        indexed = sorted(enumerate(values), key=lambda x: x[1])
        ranks = [0.0] * len(values)
        i = 0
        while i < len(indexed):
            j = i
            while j < len(indexed) and indexed[j][1] == indexed[i][1]:
                j += 1
            avg_rank = (i + 1 + j) / 2.0
            for k in range(i, j):
                ranks[indexed[k][0]] = avg_rank
            i = j
        return ranks
