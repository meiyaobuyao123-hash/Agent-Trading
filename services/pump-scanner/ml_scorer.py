"""
ML 预测打分模块

加载训练好的 XGBoost 模型，将 TokenFeatures 转为特征向量，
预测概率并映射到 0-100 分。

支持 SHAP 特征贡献度解释（score_with_detail）。
"""

import os
import logging
from typing import Dict, List, Optional

import numpy as np

from features import TokenFeatures
from ml_config import (
    FEATURE_COLUMNS,
    FEATURE_CLIP_MAX,
    ML_MODEL_PATH,
)

log = logging.getLogger(__name__)


class MLScorer:
    """
    基于 XGBoost 的 ML 打分器。

    用法:
        scorer = MLScorer()                     # 加载默认模型
        score = scorer.score(features)          # 返回 0-100 分
        detail = scorer.score_with_detail(features)  # 含 SHAP 解释
    """

    def __init__(self, model_path: Optional[str] = None):
        """
        初始化 ML 打分器。

        Args:
            model_path: XGBoost 模型文件路径，默认为 ml_config.ML_MODEL_PATH
        """
        self._model = None
        self._explainer = None  # SHAP explainer, 延迟初始化
        self._model_path = model_path or ML_MODEL_PATH
        self._load_model()

    def _load_model(self) -> None:
        """加载 XGBoost 模型"""
        import xgboost as xgb

        if not os.path.exists(self._model_path):
            raise FileNotFoundError(
                f"ML 模型文件不存在: {self._model_path}\n"
                "请先运行 python ml_trainer.py 训练模型。"
            )

        self._model = xgb.XGBClassifier()
        self._model.load_model(self._model_path)
        log.info(f"ML 模型已加载: {self._model_path}")

    def _features_to_vector(self, features: TokenFeatures) -> "np.ndarray":
        """
        将 TokenFeatures dataclass 转为模型输入向量。

        TokenFeatures 字段名与 FEATURE_COLUMNS 的映射：
        - 大部分同名
        - bc_progress_rate 在 snapshot 表中对应 TokenFeatures.bc_speed_pct_per_hour
        """
        # 字段名映射（snapshot 表列名 → TokenFeatures 属性名）
        field_map = {
            "bc_progress": "bc_progress",
            "v_sol": "v_sol",
            "market_cap_sol": "market_cap_sol",
            "buy_count": "buy_count",
            "sell_count": "sell_count",
            "buy_volume_sol": "buy_volume_sol",
            "sell_volume_sol": "sell_volume_sol",
            "unique_buyers": "unique_buyers",
            "unique_sellers": "unique_sellers",
            "buy_sell_ratio_count": "buy_sell_ratio_count",
            "buy_sell_ratio_vol": "buy_sell_ratio_vol",
            "inflow_rate_sol_pm": "inflow_rate_sol_pm",
            "bc_progress_rate": "bc_speed_pct_per_hour",
            "dev_sold_pct": "dev_sold_pct",
            "large_buy_count": "large_buy_count",
            "reply_count": "reply_count",
            "smart_elite_count": "smart_elite_count",
            "smart_verified_count": "smart_verified_count",
            "smart_watching_count": "smart_watching_count",
            "smart_money_net_sol": "smart_money_net_sol",
            "social_score": "social_score",
            "creator_prev_tokens": "creator_prev_tokens",
            "creator_success_rate": "creator_success_rate",
        }  # type: Dict[str, str]

        vec = np.zeros(len(FEATURE_COLUMNS), dtype=np.float32)

        for i, col in enumerate(FEATURE_COLUMNS):
            attr_name = field_map.get(col, col)
            val = getattr(features, attr_name, 0.0)

            if val is None:
                val = 0.0
            val = float(val)

            # NaN / Inf 处理
            if np.isnan(val) or np.isinf(val):
                val = 0.0

            # 异常值裁剪
            clip_max = FEATURE_CLIP_MAX.get(col)
            if clip_max is not None and val > clip_max:
                val = float(clip_max)

            # 负值裁剪（特殊字段除外）
            if col not in ("smart_money_net_sol", "inflow_rate_sol_pm") and val < 0:
                val = 0.0

            vec[i] = val

        return vec

    def score(self, features: TokenFeatures) -> float:
        """
        预测代币达到 2x 的概率，映射到 0-100 分。

        Args:
            features: TokenFeatures 对象

        Returns:
            0-100 的浮点分数
        """
        vec = self._features_to_vector(features)
        X = vec.reshape(1, -1)

        proba = self._model.predict_proba(X)[0, 1]  # type: ignore

        # 概率 → 0-100 分
        # 使用非线性映射：低概率区间压缩，高概率区间放大
        # sigmoid-like: score = 100 * (proba ^ 0.7)
        # 这样 proba=0.5 → score=61.6, proba=0.3 → score=41.1, proba=0.8 → score=86.2
        ml_score = round(100.0 * (proba ** 0.7), 1)
        ml_score = max(0.0, min(100.0, ml_score))

        return ml_score

    def score_with_detail(self, features: TokenFeatures) -> dict:
        """
        预测并返回详细信息，包含 SHAP 特征贡献度。

        Args:
            features: TokenFeatures 对象

        Returns:
            dict 包含:
                - ml_score: 0-100 分
                - probability: 原始概率
                - feature_contributions: {特征名: 贡献值} Top 10
                - top_positive_features: 正向贡献 Top 5
                - top_negative_features: 负向贡献 Top 5
        """
        vec = self._features_to_vector(features)
        X = vec.reshape(1, -1)

        proba = self._model.predict_proba(X)[0, 1]  # type: ignore
        ml_score = round(100.0 * (proba ** 0.7), 1)
        ml_score = max(0.0, min(100.0, ml_score))

        detail = {
            "ml_score": ml_score,
            "probability": round(float(proba), 4),
            "scoring_method": "xgboost",
        }  # type: Dict[str, object]

        # ── SHAP 特征贡献度 ──
        try:
            shap_values = self._get_shap_values(X)
            if shap_values is not None:
                contributions = {}  # type: Dict[str, float]
                for i, col in enumerate(FEATURE_COLUMNS):
                    contributions[col] = round(float(shap_values[0, i]), 4)

                # 按绝对值排序
                sorted_contribs = sorted(
                    contributions.items(),
                    key=lambda x: abs(x[1]),
                    reverse=True,
                )

                detail["feature_contributions"] = dict(sorted_contribs[:10])

                # 正负分离
                positive = [
                    (k, v) for k, v in sorted_contribs if v > 0
                ][:5]
                negative = [
                    (k, v) for k, v in sorted_contribs if v < 0
                ][:5]
                detail["top_positive_features"] = [
                    {"feature": k, "contribution": v} for k, v in positive
                ]
                detail["top_negative_features"] = [
                    {"feature": k, "contribution": v} for k, v in negative
                ]
        except Exception as e:
            log.warning(f"SHAP 解释失败（不影响打分）: {e}")
            detail["shap_error"] = str(e)

        return detail

    def _get_shap_values(self, X: "np.ndarray") -> Optional["np.ndarray"]:
        """
        计算 SHAP 值。延迟初始化 explainer。

        Args:
            X: 输入特征矩阵 (1, n_features)

        Returns:
            SHAP 值矩阵，shape (1, n_features)，失败返回 None
        """
        if self._explainer is None:
            try:
                import shap
                self._explainer = shap.TreeExplainer(self._model)
            except ImportError:
                log.warning(
                    "shap 未安装，跳过特征贡献度解释。"
                    "可选安装: pip install shap>=0.42"
                )
                return None
            except Exception as e:
                log.warning(f"初始化 SHAP explainer 失败: {e}")
                return None

        try:
            shap_values = self._explainer.shap_values(X)
            # 对于二分类，shap_values 可能是 list[ndarray] 或 ndarray
            if isinstance(shap_values, list):
                # 取正类的 SHAP 值
                return shap_values[1] if len(shap_values) > 1 else shap_values[0]
            return shap_values
        except Exception as e:
            log.warning(f"计算 SHAP 值失败: {e}")
            return None

    def is_loaded(self) -> bool:
        """检查模型是否已加载"""
        return self._model is not None
