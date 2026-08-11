"""Adaptive trade-quality models — champion/challenger, calibrated probabilities."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np

from agent.learning.dataset import FEATURE_COLS, numeric_matrix


@dataclass
class QualityPrediction:
    predicted_win_probability: float
    expected_r: float
    prediction_confidence: str  # low | medium | high
    sample_support: int
    feature_quality_flags: list[str] = field(default_factory=list)
    model_version: str = "none"
    calibrated: bool = False
    brier_val: float | None = None
    # Separate heads (spec §7) — not derived from global_score
    p_target_before_stop: float | None = None
    p_plus_1r_before_stop: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ModelBundle:
    version: str
    kind: str
    feature_names: list[str]
    coefficients: dict[str, float] | None
    importances: dict[str, float] | None
    intercept: float | None
    calibrated: bool
    brier_score: float | None
    train_n: int
    val_n: int
    created_at: str
    # serialized sklearn via joblib path
    artifact_path: str | None = None
    # fallback: mean prior when model unavailable
    prior_win_rate: float = 0.5
    prior_expectancy_r: float = 0.0


class AdaptiveTradeQualityModel:
    """Estimates P(win) / expected R from entry-time features.

    Does not invent probabilities from global score.
    """

    def __init__(
        self,
        *,
        models_dir: str | Path = "data/learning/models",
        champion_name: str = "trade_quality_champion",
        challenger_name: str = "trade_quality_challenger",
    ):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.champion_name = champion_name
        self.challenger_name = challenger_name
        self._champion: ModelBundle | None = None
        self._challenger: ModelBundle | None = None
        self._sk_models: dict[str, Any] = {}
        self.reload()

    def _meta_path(self, name: str) -> Path:
        return self.models_dir / f"{name}.json"

    def _artifact_path(self, name: str) -> Path:
        return self.models_dir / f"{name}.joblib"

    def reload(self) -> None:
        self._champion = self._load_bundle(self.champion_name)
        self._challenger = self._load_bundle(self.challenger_name)

    def _load_bundle(self, name: str) -> ModelBundle | None:
        mp = self._meta_path(name)
        if not mp.exists():
            return None
        meta = json.loads(mp.read_text(encoding="utf-8"))
        bundle = ModelBundle(**{k: meta[k] for k in ModelBundle.__dataclass_fields__ if k in meta})
        art = self._artifact_path(name)
        if art.exists():
            try:
                import joblib

                self._sk_models[name] = joblib.load(art)
            except Exception:
                self._sk_models.pop(name, None)
        return bundle

    def save_bundle(self, name: str, bundle: ModelBundle, estimator: Any | None = None) -> None:
        if estimator is not None:
            import joblib

            path = self._artifact_path(name)
            joblib.dump(estimator, path)
            bundle.artifact_path = str(path)
        self._meta_path(name).write_text(json.dumps(asdict(bundle), indent=2), encoding="utf-8")
        if name == self.champion_name:
            self._champion = bundle
            if estimator is not None:
                self._sk_models[name] = estimator
        if name == self.challenger_name:
            self._challenger = bundle
            if estimator is not None:
                self._sk_models[name] = estimator

    @property
    def champion(self) -> ModelBundle | None:
        return self._champion

    @property
    def challenger(self) -> ModelBundle | None:
        return self._challenger

    def predict_row(
        self,
        row: dict[str, Any],
        *,
        which: str = "champion",
    ) -> QualityPrediction:
        bundle = self._champion if which == "champion" else self._challenger
        name = self.champion_name if which == "champion" else self.challenger_name
        flags: list[str] = []
        if bundle is None:
            return QualityPrediction(
                predicted_win_probability=0.5,
                expected_r=0.0,
                prediction_confidence="low",
                sample_support=0,
                feature_quality_flags=["NO_MODEL"],
                model_version="none",
                calibrated=False,
            )
        est = self._sk_models.get(name)
        # Feature coverage
        present = sum(1 for c in FEATURE_COLS if row.get(c) is not None)
        if present < 8:
            flags.append("SPARSE_FEATURES")
        proba = float(bundle.prior_win_rate)
        exp_r = float(bundle.prior_expectancy_r)
        if est is not None:
            import pandas as pd

            df = pd.DataFrame([row])
            X, names = numeric_matrix(df)
            # Align columns to training feature order
            if bundle.feature_names:
                # rebuild with zeros for missing
                work = pd.DataFrame(X, columns=names)
                for fn in bundle.feature_names:
                    if fn not in work.columns:
                        work[fn] = 0.0
                X = work[bundle.feature_names].to_numpy(dtype=float)
            try:
                if hasattr(est, "predict_proba"):
                    proba = float(est.predict_proba(X)[0][1])
                else:
                    proba = float(est.predict(X)[0])
                proba = min(max(proba, 0.01), 0.99)
            except Exception:
                flags.append("PREDICT_FALLBACK_PRIOR")
                proba = float(bundle.prior_win_rate)
        # Expected R proxy from prior + probability tilt
        exp_r = float(bundle.prior_expectancy_r) + (proba - 0.5) * 0.8
        conf = "low"
        if bundle.calibrated and bundle.train_n >= 80 and "SPARSE_FEATURES" not in flags:
            conf = "high" if bundle.train_n >= 150 else "medium"
        elif bundle.train_n >= 40:
            conf = "medium"
        # Secondary heads: approximate from same classifier until dedicated heads trained
        p_target = proba
        p_1r = min(0.99, max(0.01, proba + 0.05))
        return QualityPrediction(
            predicted_win_probability=proba,
            expected_r=exp_r,
            prediction_confidence=conf,
            sample_support=int(bundle.train_n),
            feature_quality_flags=flags,
            model_version=bundle.version,
            calibrated=bool(bundle.calibrated),
            brier_val=bundle.brier_score,
            p_target_before_stop=p_target,
            p_plus_1r_before_stop=p_1r,
        )

    def promote_challenger_to_champion(self, *, new_version: str) -> bool:
        if self._challenger is None:
            return False
        # Copy challenger artifacts to champion
        chall = self._challenger
        est = self._sk_models.get(self.challenger_name)
        promoted = ModelBundle(**{**asdict(chall), "version": new_version})
        self.save_bundle(self.champion_name, promoted, estimator=est)
        # journal
        journal = self.models_dir / "promotions.jsonl"
        with journal.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "from": chall.version,
                        "to": new_version,
                        "brier": chall.brier_score,
                    }
                )
                + "\n"
            )
        return True


def train_baseline_models(
    train_df,
    val_df,
    *,
    target: str = "target_before_stop",
) -> dict[str, Any]:
    """Train logistic / ridge logistic / shallow tree; return metrics + feature effects."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import brier_score_loss, roc_auc_score
    from sklearn.tree import DecisionTreeClassifier

    y_col = target if target in train_df.columns else "win"
    # Drop rows without label
    tr = train_df.dropna(subset=[y_col]) if y_col in train_df.columns else train_df
    va = val_df.dropna(subset=[y_col]) if y_col in val_df.columns else val_df
    if len(tr) < 20 or tr[y_col].nunique() < 2:
        return {"ok": False, "reason": f"insufficient_train n={len(tr)}"}

    Xtr, names = numeric_matrix(tr)
    ytr = tr[y_col].astype(int).to_numpy()
    Xva, _ = numeric_matrix(va)
    # Align val columns
    import pandas as pd

    Xtr_df = pd.DataFrame(Xtr, columns=names)
    Xva_df = pd.DataFrame(numeric_matrix(va)[0], columns=numeric_matrix(va)[1])
    for c in names:
        if c not in Xva_df.columns:
            Xva_df[c] = 0.0
    Xva = Xva_df[names].to_numpy(dtype=float)
    yva = va[y_col].astype(int).to_numpy() if len(va) else np.array([])

    out: dict[str, Any] = {"ok": True, "feature_names": names, "models": {}}

    # Logistic
    logit = LogisticRegression(max_iter=2000, solver="lbfgs")
    logit.fit(Xtr, ytr)
    out["models"]["logistic"] = _eval_clf(logit, Xtr, ytr, Xva, yva, names, coef=True)

    # Regularized
    ridge = LogisticRegression(max_iter=2000, C=0.5, solver="lbfgs")
    ridge.fit(Xtr, ytr)
    out["models"]["logistic_l2"] = _eval_clf(ridge, Xtr, ytr, Xva, yva, names, coef=True)

    tree = DecisionTreeClassifier(max_depth=3, min_samples_leaf=max(5, len(tr) // 20), random_state=42)
    tree.fit(Xtr, ytr)
    out["models"]["shallow_tree"] = _eval_clf(tree, Xtr, ytr, Xva, yva, names, importance=True)

    out["estimators"] = {"logistic_l2": ridge, "shallow_tree": tree, "logistic": logit}
    return out


def train_nonlinear_models(train_df, val_df, *, target: str = "target_before_stop") -> dict[str, Any]:
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier

    y_col = target if target in train_df.columns else "win"
    tr = train_df.dropna(subset=[y_col])
    va = val_df.dropna(subset=[y_col])
    if len(tr) < 25 or tr[y_col].nunique() < 2:
        return {"ok": False, "reason": f"insufficient_train n={len(tr)}"}
    Xtr, names = numeric_matrix(tr)
    ytr = tr[y_col].astype(int).to_numpy()
    import pandas as pd

    Xva_df = pd.DataFrame(numeric_matrix(va)[0], columns=numeric_matrix(va)[1])
    for c in names:
        if c not in Xva_df.columns:
            Xva_df[c] = 0.0
    Xva = Xva_df[names].to_numpy(dtype=float)
    yva = va[y_col].astype(int).to_numpy() if len(va) else np.array([])

    out: dict[str, Any] = {"ok": True, "feature_names": names, "models": {}, "estimators": {}}
    rf = RandomForestClassifier(
        n_estimators=120, max_depth=4, min_samples_leaf=max(3, len(tr) // 25), random_state=42
    )
    rf.fit(Xtr, ytr)
    out["models"]["random_forest"] = _eval_clf(rf, Xtr, ytr, Xva, yva, names, importance=True)
    out["estimators"]["random_forest"] = rf

    gb = GradientBoostingClassifier(
        n_estimators=80, max_depth=2, learning_rate=0.05, random_state=42
    )
    gb.fit(Xtr, ytr)
    out["models"]["gradient_boosting"] = _eval_clf(gb, Xtr, ytr, Xva, yva, names, importance=True)
    out["estimators"]["gradient_boosting"] = gb
    return out


def _eval_clf(est, Xtr, ytr, Xva, yva, names, *, coef=False, importance=False) -> dict[str, Any]:
    from sklearn.metrics import brier_score_loss, roc_auc_score

    def _pack(X, y):
        if len(y) < 5 or len(np.unique(y)) < 2:
            return {"n": int(len(y)), "brier": None, "auc": None}
        p = est.predict_proba(X)[:, 1]
        return {
            "n": int(len(y)),
            "brier": float(brier_score_loss(y, p)),
            "auc": float(roc_auc_score(y, p)),
            "pred_mean": float(p.mean()),
            "actual_wr": float(y.mean()),
        }

    res = {"train": _pack(Xtr, ytr), "val": _pack(Xva, yva)}
    if coef and hasattr(est, "coef_"):
        coefs = {names[i]: float(est.coef_[0][i]) for i in range(len(names))}
        res["coefficients"] = dict(sorted(coefs.items(), key=lambda kv: abs(kv[1]), reverse=True)[:40])
        res["intercept"] = float(est.intercept_[0])
    if importance and hasattr(est, "feature_importances_"):
        imps = {names[i]: float(est.feature_importances_[i]) for i in range(len(names))}
        res["importances"] = dict(sorted(imps.items(), key=lambda kv: kv[1], reverse=True)[:40])
    return res


def calibration_bins(y_true: np.ndarray, y_prob: np.ndarray) -> list[dict[str, Any]]:
    edges = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 1.01]
    labels = ["50-55", "55-60", "60-65", "65-70", "70-75", "75-80", "80+"]
    out = []
    for i, lab in enumerate(labels):
        lo, hi = edges[i], edges[i + 1]
        mask = (y_prob >= lo) & (y_prob < hi)
        n = int(mask.sum())
        if n == 0:
            out.append({"bin": lab, "n": 0, "pred_avg": None, "actual_wr": None})
            continue
        out.append(
            {
                "bin": lab,
                "n": n,
                "pred_avg": float(y_prob[mask].mean()),
                "actual_wr": float(y_true[mask].mean()),
            }
        )
    return out


def is_calibrated_enough(bins: list[dict[str, Any]], *, min_bin_n: int = 8, max_abs_gap: float = 0.12) -> bool:
    usable = [b for b in bins if (b.get("n") or 0) >= min_bin_n]
    if len(usable) < 2:
        return False
    for b in usable:
        gap = abs(float(b["pred_avg"]) - float(b["actual_wr"]))
        if gap > max_abs_gap:
            return False
    return True
