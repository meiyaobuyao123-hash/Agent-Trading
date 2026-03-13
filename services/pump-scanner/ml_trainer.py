"""
XGBoost 训练管线

从 Supabase 拉取 token_snapshots + token_outcomes 数据，
训练二分类模型预测代币是否能达到 2x 涨幅。

用法:
    python ml_trainer.py              # 训练并保存模型
    python ml_trainer.py --dry-run    # 只输出数据统计，不训练
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np

from database import get_db
from ml_config import (
    FEATURE_COLUMNS,
    LABEL_COLUMN,
    FEATURE_CLIP_MAX,
    ML_MODEL_PATH,
    ML_MODEL_DIR,
    FEATURE_IMPORTANCE_PATH,
    ML_MIN_TRAINING_SAMPLES,
    ML_TRAIN_TEST_SPLIT,
    ML_RANDOM_STATE,
    ML_RETRAIN_MIN_NEW_SAMPLES,
    ML_MAX_MODEL_VERSIONS,
    XGB_PARAMS,
)

log = logging.getLogger(__name__)


def fetch_training_data() -> List[dict]:
    """
    从 Supabase 拉取训练数据。
    JOIN token_snapshots + token_outcomes (on mint)。
    每个 mint 取最新的一条 snapshot（bc_progress 最大的）。
    返回包含特征 + 标签的 dict 列表。
    """
    db = get_db()

    # ── 1. 拉取所有 token_outcomes（已标注的代币）──
    log.info("正在拉取 token_outcomes ...")
    outcomes_res = db.table("token_outcomes").select(
        "mint, label_2x, label_10x, peak_multiplier, labeled_at"
    ).execute()
    outcomes = outcomes_res.data
    log.info(f"  token_outcomes 共 {len(outcomes)} 条")

    if not outcomes:
        log.warning("没有任何标注数据，无法训练")
        return []

    outcome_map = {}  # type: Dict[str, dict]
    for o in outcomes:
        outcome_map[o["mint"]] = o

    labeled_mints = list(outcome_map.keys())

    # ── 2. 分批拉取这些 mint 的 snapshots ──
    log.info("正在拉取 token_snapshots ...")
    all_snapshots = []  # type: List[dict]
    batch_size = 50

    for i in range(0, len(labeled_mints), batch_size):
        batch_mints = labeled_mints[i:i + batch_size]
        try:
            snap_res = (
                db.table("token_snapshots")
                .select("*")
                .in_("mint", batch_mints)
                .order("snapshot_at", desc=True)
                .execute()
            )
            all_snapshots.extend(snap_res.data)
        except Exception as e:
            log.error(f"拉取 snapshots batch {i} 失败: {e}")

    log.info(f"  token_snapshots 共 {len(all_snapshots)} 条")

    # ── 3. 每个 mint 只保留最新（bc_progress 最大的）snapshot ──
    best_snap = {}  # type: Dict[str, dict]
    for snap in all_snapshots:
        mint = snap["mint"]
        if mint not in best_snap:
            best_snap[mint] = snap
        else:
            # snapshot_at DESC 已经排序，第一条就是最新的
            pass

    # ── 4. 合并特征 + 标签 ──
    merged = []  # type: List[dict]
    for mint, snap in best_snap.items():
        outcome = outcome_map.get(mint)
        if outcome is None:
            continue

        row = {}  # type: Dict[str, object]
        row["mint"] = mint
        row["snapshot_at"] = snap.get("snapshot_at", "")

        # 特征列
        for col in FEATURE_COLUMNS:
            val = snap.get(col)
            if val is None:
                row[col] = 0.0
            else:
                try:
                    row[col] = float(val)
                except (ValueError, TypeError):
                    row[col] = 0.0

        # 标签
        label_val = outcome.get(LABEL_COLUMN, False)
        row[LABEL_COLUMN] = 1 if label_val else 0

        # 额外标签（用于分析，不参与训练）
        row["label_10x"] = 1 if outcome.get("label_10x", False) else 0
        row["peak_multiplier"] = outcome.get("peak_multiplier")

        merged.append(row)

    log.info(f"  合并后有效样本: {len(merged)} 条")
    return merged


def clean_features(
    data: List[dict],
) -> Tuple["np.ndarray", "np.ndarray", List[str]]:
    """
    特征清洗：fillna + 异常值裁剪。
    返回 (X, y, mints)
    """
    n = len(data)
    p = len(FEATURE_COLUMNS)

    X = np.zeros((n, p), dtype=np.float32)
    y = np.zeros(n, dtype=np.int32)
    mints = []  # type: List[str]

    for i, row in enumerate(data):
        mints.append(str(row.get("mint", "")))
        y[i] = int(row.get(LABEL_COLUMN, 0))

        for j, col in enumerate(FEATURE_COLUMNS):
            val = row.get(col, 0.0)
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

            # 负值裁剪（除了 smart_money_net_sol 和 inflow_rate_sol_pm 可以为负）
            if col not in ("smart_money_net_sol", "inflow_rate_sol_pm") and val < 0:
                val = 0.0

            X[i, j] = val

    return X, y, mints


def time_series_split(
    data: List[dict],
    X: "np.ndarray",
    y: "np.ndarray",
    train_ratio: float = ML_TRAIN_TEST_SPLIT,
) -> Tuple["np.ndarray", "np.ndarray", "np.ndarray", "np.ndarray"]:
    """
    按 snapshot_at 时间排序后做前后分割（非随机），
    保证训练集是过去的数据，验证集是未来的数据。
    """
    # 按 snapshot_at 排序
    sorted_indices = sorted(
        range(len(data)),
        key=lambda i: data[i].get("snapshot_at", ""),
    )

    split_idx = int(len(sorted_indices) * train_ratio)
    train_idx = sorted_indices[:split_idx]
    val_idx = sorted_indices[split_idx:]

    X_train = X[train_idx]
    y_train = y[train_idx]
    X_val = X[val_idx]
    y_val = y[val_idx]

    return X_train, y_train, X_val, y_val


def train_model(
    X_train: "np.ndarray",
    y_train: "np.ndarray",
    X_val: "np.ndarray",
    y_val: "np.ndarray",
) -> object:
    """
    训练 XGBoost 二分类模型。
    返回训练好的 XGBClassifier。
    """
    import xgboost as xgb

    # 计算正负样本比例，用于 scale_pos_weight
    n_pos = int(y_train.sum())
    n_neg = len(y_train) - n_pos
    scale_pos_weight = n_neg / max(1, n_pos)

    log.info(f"训练集: {len(y_train)} 样本 (正样本 {n_pos}, 负样本 {n_neg})")
    log.info(f"验证集: {len(y_val)} 样本 (正样本 {int(y_val.sum())})")
    log.info(f"scale_pos_weight = {scale_pos_weight:.2f}")

    params = dict(XGB_PARAMS)
    params["scale_pos_weight"] = scale_pos_weight
    params["random_state"] = ML_RANDOM_STATE

    model = xgb.XGBClassifier(**params)

    model.fit(
        X_train,
        y_train,
        eval_set=[(X_train, y_train), (X_val, y_val)],
        verbose=True,
    )

    return model


def evaluate_model(
    model: object,
    X_val: "np.ndarray",
    y_val: "np.ndarray",
) -> dict:
    """
    评估模型性能。返回评估指标 dict。
    """
    from sklearn.metrics import (
        roc_auc_score,
        precision_score,
        recall_score,
        f1_score,
        confusion_matrix,
        classification_report,
    )

    y_pred_proba = model.predict_proba(X_val)[:, 1]  # type: ignore
    y_pred = (y_pred_proba >= 0.5).astype(int)

    auc = roc_auc_score(y_val, y_pred_proba) if len(set(y_val)) > 1 else 0.0
    precision = precision_score(y_val, y_pred, zero_division=0)
    recall = recall_score(y_val, y_pred, zero_division=0)
    f1 = f1_score(y_val, y_pred, zero_division=0)
    cm = confusion_matrix(y_val, y_pred).tolist()

    report = classification_report(y_val, y_pred, zero_division=0)

    metrics = {
        "auc": round(float(auc), 4),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "confusion_matrix": cm,
        "n_val_samples": len(y_val),
        "n_val_positive": int(y_val.sum()),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }

    log.info("=" * 60)
    log.info("模型评估结果:")
    log.info(f"  AUC       = {metrics['auc']}")
    log.info(f"  Precision = {metrics['precision']}")
    log.info(f"  Recall    = {metrics['recall']}")
    log.info(f"  F1        = {metrics['f1']}")
    log.info(f"  混淆矩阵  = {cm}")
    log.info("")
    log.info(report)
    log.info("=" * 60)

    return metrics


def save_model(model: object, metrics: dict) -> None:
    """保存模型和特征重要性到 models/ 目录，并保留历史版本"""
    os.makedirs(ML_MODEL_DIR, exist_ok=True)

    # ── 版本化：先将旧模型重命名为带时间戳的版本 ──
    if os.path.exists(ML_MODEL_PATH):
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        versioned = ML_MODEL_PATH.replace(".json", "_v{}.json".format(ts))
        os.rename(ML_MODEL_PATH, versioned)
        log.info(f"旧模型已归档: {versioned}")
        _cleanup_old_versions()

    # 保存 XGBoost 模型（原生 JSON 格式）
    model.save_model(ML_MODEL_PATH)  # type: ignore
    log.info(f"模型已保存: {ML_MODEL_PATH}")

    # 保存特征重要性
    importance = model.feature_importances_  # type: ignore
    feat_imp = {}  # type: Dict[str, float]
    for col, imp in zip(FEATURE_COLUMNS, importance):
        feat_imp[col] = round(float(imp), 6)

    # 按重要性降序排列
    feat_imp_sorted = dict(
        sorted(feat_imp.items(), key=lambda x: x[1], reverse=True)
    )

    output = {
        "feature_importance": feat_imp_sorted,
        "metrics": metrics,
        "feature_columns": FEATURE_COLUMNS,
        "label_column": LABEL_COLUMN,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "xgb_params": {k: v for k, v in XGB_PARAMS.items()},
    }

    with open(FEATURE_IMPORTANCE_PATH, "w", encoding="utf-8") as fp:
        json.dump(output, fp, indent=2, ensure_ascii=False)
    log.info(f"特征重要性已保存: {FEATURE_IMPORTANCE_PATH}")

    # 打印 Top 10 特征
    log.info("Top 10 特征重要性:")
    for i, (col, imp) in enumerate(feat_imp_sorted.items()):
        if i >= 10:
            break
        bar = "#" * int(imp * 100)
        log.info(f"  {i+1:2d}. {col:30s} {imp:.4f} {bar}")


def run_training(dry_run: bool = False) -> Optional[dict]:
    """
    完整训练流程。

    Args:
        dry_run: True 时只输出数据统计，不训练模型

    Returns:
        训练成功时返回评估指标 dict，失败返回 None
    """
    log.info("=" * 60)
    log.info("XGBoost 训练管线启动")
    log.info("=" * 60)

    # ── 1. 拉取数据 ──
    data = fetch_training_data()
    if not data:
        log.error("无训练数据，退出")
        return None

    n_total = len(data)
    n_positive = sum(1 for d in data if d.get(LABEL_COLUMN, 0) == 1)
    n_negative = n_total - n_positive

    log.info(f"数据统计:")
    log.info(f"  总样本数:   {n_total}")
    log.info(f"  正样本(2x): {n_positive} ({n_positive/n_total*100:.1f}%)")
    log.info(f"  负样本:     {n_negative} ({n_negative/n_total*100:.1f}%)")

    if n_total < ML_MIN_TRAINING_SAMPLES:
        log.warning(
            f"样本数 {n_total} < 最低要求 {ML_MIN_TRAINING_SAMPLES}，"
            "暂不训练。请等待更多标注数据。"
        )
        return None

    if n_positive == 0:
        log.warning("没有正样本（无任何代币达到 2x），无法训练二分类模型")
        return None

    if dry_run:
        log.info("(dry-run 模式，跳过训练)")
        return None

    # ── 2. 特征清洗 ──
    X, y, mints = clean_features(data)
    log.info(f"特征矩阵: {X.shape}")

    # ── 3. 时间序列分割 ──
    X_train, y_train, X_val, y_val = time_series_split(data, X, y)
    log.info(
        f"训练集: {len(y_train)} 样本, 验证集: {len(y_val)} 样本"
    )

    if len(y_val) == 0:
        log.error("验证集为空，无法评估")
        return None

    # ── 4. 训练 ──
    model = train_model(X_train, y_train, X_val, y_val)

    # ── 5. 评估 ──
    metrics = evaluate_model(model, X_val, y_val)

    # ── 6. 保存 ──
    save_model(model, metrics)

    log.info("训练管线完成!")
    return metrics


def _cleanup_old_versions() -> None:
    """保留最近 N 个历史模型版本，删除更早的"""
    import glob
    pattern = os.path.join(ML_MODEL_DIR, "xgb_pump_v1_v*.json")
    versions = sorted(glob.glob(pattern))
    if len(versions) > ML_MAX_MODEL_VERSIONS:
        for old in versions[:-ML_MAX_MODEL_VERSIONS]:
            os.remove(old)
            log.info(f"清理旧版本: {old}")


def _get_last_train_sample_count() -> int:
    """读取上次训练时的样本数（从 feature_importance.json）"""
    if not os.path.exists(FEATURE_IMPORTANCE_PATH):
        return 0
    try:
        with open(FEATURE_IMPORTANCE_PATH, "r") as f:
            info = json.load(f)
        metrics = info.get("metrics", {})
        # 验证集 + 训练集 ≈ 总样本
        n_val = metrics.get("n_val_samples", 0)
        return int(n_val / (1 - ML_TRAIN_TEST_SPLIT)) if n_val else 0
    except Exception:
        return 0


def should_retrain(current_sample_count: int) -> bool:
    """
    判断是否需要重训。

    条件：新增样本数 >= ML_RETRAIN_MIN_NEW_SAMPLES
    """
    last_count = _get_last_train_sample_count()
    new_samples = current_sample_count - last_count
    if new_samples >= ML_RETRAIN_MIN_NEW_SAMPLES:
        log.info(
            f"新增 {new_samples} 个标注样本 (上次 {last_count}, 当前 {current_sample_count})，"
            f"触发重训 (阈值 {ML_RETRAIN_MIN_NEW_SAMPLES})"
        )
        return True
    log.info(
        f"新增 {new_samples} 个样本，不足 {ML_RETRAIN_MIN_NEW_SAMPLES}，跳过重训"
    )
    return False


async def auto_retrain_if_needed() -> Optional[dict]:
    """
    自动重训入口（由调度器定期调用）。

    检查是否有足够的新数据，有则重训模型。
    返回评估指标或 None。
    """
    import asyncio

    # 在线程池中执行（训练是 CPU 密集型）
    return await asyncio.to_thread(_auto_retrain_sync)


def _auto_retrain_sync() -> Optional[dict]:
    """同步版本的自动重训"""
    data = fetch_training_data()
    if not data:
        return None

    if not should_retrain(len(data)):
        return None

    log.info("开始自动重训...")
    return run_training(dry_run=False)


def main():
    parser = argparse.ArgumentParser(description="XGBoost 训练管线")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只输出数据统计，不训练模型",
    )
    parser.add_argument(
        "--check-retrain",
        action="store_true",
        help="检查是否需要重训（新增样本够多时自动训练）",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.check_retrain:
        metrics = _auto_retrain_sync()
        if metrics:
            log.info(f"重训完成，AUC = {metrics['auc']}")
        else:
            log.info("无需重训")
        sys.exit(0)

    metrics = run_training(dry_run=args.dry_run)
    if metrics:
        log.info(f"最终 AUC = {metrics['auc']}")
        sys.exit(0)
    else:
        log.warning("训练未完成（数据不足或 dry-run 模式）")
        sys.exit(1)


if __name__ == "__main__":
    main()
