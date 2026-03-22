"""
Data Governance / Research Quality Engine — Tracks data freshness,
source reliability, coverage gaps, and research quality metrics.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DataSourceStatus:
    name: str
    source: str
    last_updated: str | None = None
    freshness: str = "unknown"  # live | stale | expired | unknown
    quality_score: float = 0.0  # 0-100
    coverage_pct: float = 0.0  # % of fields populated
    warnings: list[str] = field(default_factory=list)


@dataclass
class DataGovernanceSnapshot:
    """Data governance and quality dashboard."""
    sources: list[DataSourceStatus] = field(default_factory=list)

    # Aggregate metrics
    overall_quality_score: float = 50.0
    overall_freshness_score: float = 50.0
    overall_coverage_pct: float = 0.0

    # Staleness
    stale_sources: list[str] = field(default_factory=list)
    expired_sources: list[str] = field(default_factory=list)

    # Coverage gaps
    missing_data_points: list[str] = field(default_factory=list)
    critical_gaps: list[str] = field(default_factory=list)

    # Research quality
    signal_count: int = 0
    confirmed_signals: int = 0
    signal_accuracy_pct: float = 0.0

    # Overfitting / false edge warnings
    overfitting_warnings: list[str] = field(default_factory=list)
    data_snooping_risk: float = 0.0  # 0-100

    # Recommendations
    recommendations: list[str] = field(default_factory=list)

    # Score
    data_governance_score: float = 50.0


class DataGovernanceEngine:
    """Monitors data quality, freshness, and research integrity."""

    def analyze(
        self,
        data_sources: dict | None = None,
        analysis_metadata: dict | None = None,
    ) -> DataGovernanceSnapshot:
        snap = DataGovernanceSnapshot()

        sources_config = data_sources or self._default_sources()
        now = dt.datetime.now(dt.timezone.utc)

        for src_cfg in sources_config:
            src = DataSourceStatus(
                name=src_cfg["name"],
                source=src_cfg.get("source", "unknown"),
                last_updated=src_cfg.get("last_updated"),
                quality_score=src_cfg.get("quality_score", 50),
                coverage_pct=src_cfg.get("coverage_pct", 70),
            )

            # Freshness
            if src.last_updated:
                try:
                    updated = dt.datetime.fromisoformat(src.last_updated.replace("Z", "+00:00"))
                    age_minutes = (now - updated).total_seconds() / 60
                    max_age = src_cfg.get("max_age_minutes", 60)
                    if age_minutes < max_age:
                        src.freshness = "live"
                    elif age_minutes < max_age * 3:
                        src.freshness = "stale"
                        snap.stale_sources.append(src.name)
                        logger.warning(
                            "Data source '%s' is stale (%.0f min old, max %d min)",
                            src.name, age_minutes, max_age,
                        )
                    else:
                        src.freshness = "expired"
                        snap.expired_sources.append(src.name)
                        logger.error(
                            "Data source '%s' has EXPIRED (%.0f min old, max %d min)",
                            src.name, age_minutes, max_age,
                        )
                except (ValueError, TypeError):
                    src.freshness = "unknown"
                    logger.warning(
                        "Data source '%s' has unparseable last_updated: %r",
                        src.name, src.last_updated,
                    )
            else:
                src.freshness = "unknown"
                logger.warning("Data source '%s' has no last_updated timestamp", src.name)

            if src.quality_score < 30:
                src.warnings.append(f"Very low quality: {src.quality_score}")
                logger.warning("Data source '%s' quality critically low: %.1f", src.name, src.quality_score)
            if src.coverage_pct < 50:
                src.warnings.append(f"Low coverage: {src.coverage_pct}%")
                logger.info("Data source '%s' coverage below 50%%: %.1f%%", src.name, src.coverage_pct)
            snap.sources.append(src)

        # Aggregate
        if snap.sources:
            snap.overall_quality_score = round(
                sum(s.quality_score for s in snap.sources) / len(snap.sources), 1)
            fresh = sum(1 for s in snap.sources if s.freshness == "live")
            snap.overall_freshness_score = round(fresh / len(snap.sources) * 100, 1)
            snap.overall_coverage_pct = round(
                sum(s.coverage_pct for s in snap.sources) / len(snap.sources), 1)

        # Coverage gaps
        snap.missing_data_points = self._find_gaps(snap.sources)
        snap.critical_gaps = [g for g in snap.missing_data_points if "price" in g.lower() or "funding" in g.lower()]

        # Research quality
        if analysis_metadata:
            snap.signal_count = analysis_metadata.get("signal_count", 0)
            snap.confirmed_signals = analysis_metadata.get("confirmed_signals", 0)
            if snap.signal_count > 0:
                snap.signal_accuracy_pct = round(snap.confirmed_signals / snap.signal_count * 100, 1)

        # Overfitting check
        snap.overfitting_warnings = self._overfitting_check(analysis_metadata)
        snap.data_snooping_risk = self._snooping_risk(analysis_metadata)

        # Recommendations
        snap.recommendations = self._generate_recommendations(snap)

        snap.data_governance_score = self._compute_score(snap)
        return snap

    def _find_gaps(self, sources: list[DataSourceStatus]) -> list[str]:
        gaps = []
        required = {"Price Data", "Options Chain", "Short Interest", "Macro Indicators", "News/Sentiment"}
        found = {s.name for s in sources}
        for req in required:
            if req not in found:
                gaps.append(f"Missing: {req}")
        for s in sources:
            if s.coverage_pct < 50:
                gaps.append(f"Low coverage: {s.name} ({s.coverage_pct}%)")
        return gaps

    def _overfitting_check(self, metadata: dict | None) -> list[str]:
        warnings = []
        if not metadata:
            return warnings
        params = metadata.get("model_parameters", 0)
        data_points = metadata.get("data_points", 252)
        if params > data_points / 10:
            warnings.append(f"High parameter-to-data ratio: {params}/{data_points}")
        if metadata.get("in_sample_sharpe", 0) > 3.0:
            warnings.append("Suspiciously high in-sample Sharpe (>3.0)")
        if metadata.get("lookback_tested", 0) > 20:
            warnings.append(f"Tested {metadata['lookback_tested']} lookback periods — data mining risk")
        return warnings

    def _snooping_risk(self, metadata: dict | None) -> float:
        if not metadata:
            return 20.0
        risk = 20.0
        if metadata.get("strategies_tested", 0) > 50:
            risk += 30
        if metadata.get("in_sample_sharpe", 0) > 2.5:
            risk += 20
        if metadata.get("out_of_sample_decay", 0) > 0.5:
            risk += 20
        return round(min(100, risk), 1)

    def _generate_recommendations(self, snap: DataGovernanceSnapshot) -> list[str]:
        recs = []
        if snap.stale_sources:
            recs.append(f"Refresh stale sources: {', '.join(snap.stale_sources)}")
        if snap.expired_sources:
            recs.append(f"URGENT: Expired sources: {', '.join(snap.expired_sources)}")
        if snap.overall_coverage_pct < 70:
            recs.append("Improve data coverage — several sources below 70%")
        if snap.data_snooping_risk > 50:
            recs.append("High data snooping risk — validate with out-of-sample testing")
        if snap.overfitting_warnings:
            recs.append("Review overfitting warnings — reduce model complexity")
        return recs

    def _compute_score(self, snap: DataGovernanceSnapshot) -> float:
        score = snap.overall_quality_score * 0.35 + snap.overall_freshness_score * 0.35 + snap.overall_coverage_pct * 0.30
        score -= len(snap.critical_gaps) * 5
        score -= len(snap.overfitting_warnings) * 5
        score -= snap.data_snooping_risk * 0.1
        return round(max(0, min(100, score)), 2)

    def _default_sources(self) -> list[dict]:
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        return [
            {"name": "Price Data", "source": "yahoo/polygon", "last_updated": now,
             "quality_score": 85, "coverage_pct": 95, "max_age_minutes": 15},
            {"name": "Options Chain", "source": "yahoo/tradier", "last_updated": now,
             "quality_score": 75, "coverage_pct": 80, "max_age_minutes": 30},
            {"name": "Short Interest", "source": "fintel/ortex", "last_updated": now,
             "quality_score": 70, "coverage_pct": 75, "max_age_minutes": 1440},
            {"name": "Macro Indicators", "source": "fred", "last_updated": now,
             "quality_score": 90, "coverage_pct": 85, "max_age_minutes": 2880},
            {"name": "News/Sentiment", "source": "newsapi", "last_updated": now,
             "quality_score": 60, "coverage_pct": 65, "max_age_minutes": 360},
            {"name": "Fundamentals", "source": "sec/yahoo", "last_updated": now,
             "quality_score": 80, "coverage_pct": 70, "max_age_minutes": 43200},
        ]
