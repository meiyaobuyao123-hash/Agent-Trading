"""
ML 配置模块

控制 XGBoost 模型的训练参数、特征列、切换开关等。
通过环境变量 USE_ML_SCORING=1 启用 ML 打分（默认关闭，使用规则打分）。
"""

import os
from typing import List

# ── 开关 ─────────────────────────────────────────────────────
# 环境变量 USE_ML_SCORING=1 启用 ML 打分，否则使用规则打分
USE_ML_SCORING = os.getenv("USE_ML_SCORING", "0").strip() in ("1", "true", "True")

# ── 模型路径 ─────────────────────────────────────────────────
ML_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
ML_MODEL_PATH = os.path.join(ML_MODEL_DIR, "xgb_pump_v1.json")
FEATURE_IMPORTANCE_PATH = os.path.join(ML_MODEL_DIR, "feature_importance.json")

# ── 训练参数 ─────────────────────────────────────────────────
ML_MIN_TRAINING_SAMPLES = 100     # 最少训练样本数，不足则拒绝训练
ML_TRAIN_TEST_SPLIT = 0.8        # 训练集占比（按时间序列排序后前80%训练）
ML_RANDOM_STATE = 42

# ── 自动重训 ───────────────────────────────────────────────
# 每隔多少小时检查是否需要重训（默认每周一次 = 168h）
ML_RETRAIN_INTERVAL_HOURS = int(os.getenv("ML_RETRAIN_HOURS", "168"))
# 新增多少标注样本后才值得重训
ML_RETRAIN_MIN_NEW_SAMPLES = int(os.getenv("ML_RETRAIN_MIN_NEW", "50"))
# 保留最近多少个历史模型版本
ML_MAX_MODEL_VERSIONS = 5

# ── XGBoost 超参数 ───────────────────────────────────────────
XGB_PARAMS = {
    "max_depth": 6,
    "learning_rate": 0.1,
    "n_estimators": 200,
    "eval_metric": "auc",
    "objective": "binary:logistic",
    "tree_method": "hist",         # CPU 友好
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 3,
    "gamma": 0.1,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "use_label_encoder": False,
}

# ── 特征列（与 token_snapshots 表字段对应）──────────────────
FEATURE_COLUMNS = [
    "bc_progress",
    "v_sol",
    "market_cap_sol",
    "buy_count",
    "sell_count",
    "buy_volume_sol",
    "sell_volume_sol",
    "unique_buyers",
    "unique_sellers",
    "buy_sell_ratio_count",
    "buy_sell_ratio_vol",
    "inflow_rate_sol_pm",
    "bc_progress_rate",
    "dev_sold_pct",
    "large_buy_count",
    "reply_count",
    "smart_elite_count",
    "smart_verified_count",
    "smart_watching_count",
    "smart_money_net_sol",
    "social_score",
    "creator_prev_tokens",
    "creator_success_rate",
]  # type: List[str]

# ── 标签列 ───────────────────────────────────────────────────
LABEL_COLUMN = "label_2x"         # boolean -> 0/1，代表72h内是否达到2x涨幅

# ── 特征工程：异常值裁剪上限 ─────────────────────────────────
# key: 特征名, value: 裁剪上限（超过此值截断为该值）
FEATURE_CLIP_MAX = {
    "v_sol": 200.0,
    "market_cap_sol": 500.0,
    "buy_count": 5000,
    "sell_count": 5000,
    "buy_volume_sol": 500.0,
    "sell_volume_sol": 500.0,
    "unique_buyers": 2000,
    "unique_sellers": 2000,
    "buy_sell_ratio_count": 50.0,
    "buy_sell_ratio_vol": 50.0,
    "inflow_rate_sol_pm": 20.0,
    "bc_progress_rate": 100.0,
    "large_buy_count": 100,
    "reply_count": 1000,
    "smart_money_net_sol": 50.0,
    "creator_prev_tokens": 50,
}
