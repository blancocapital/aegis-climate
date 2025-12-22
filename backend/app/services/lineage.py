from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Breach,
    DriftRun,
    ExposureVersion,
    HazardDataset,
    HazardDatasetVersion,
    HazardOverlayResult,
    RollupConfig,
    RollupResult,
    ThresholdRule,
    Run,
)


class LineageBuilder:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, str]] = []

    def _key(self, type_: str, id_: Any) -> str:
        return f"{type_}:{id_}"

    def _add_node(self, type_: str, id_: Any, label: str = "", created_at=None, created_by=None, run_id=None, checksum=None):
        key = self._key(type_, id_)
        if key not in self.nodes:
            self.nodes[key] = {
                "key": key,
                "type": type_,
                "id": id_,
                "label": label,
                "created_at": created_at.isoformat() if created_at else None,
                "created_by": created_by,
                "run_id": run_id,
                "checksum": checksum,
            }
        return key

    def _add_edge(self, from_type: str, from_id: Any, to_type: str, to_id: Any, relation: str):
        self.edges.append(
            {
                "from": self._key(from_type, from_id),
                "to": self._key(to_type, to_id),
                "relation": relation,
            }
        )

    def build_for_rollup_result(self, rollup_result_id: int):
        rr = self.db.get(RollupResult, rollup_result_id)
        if not rr or rr.tenant_id != self.tenant_id:
            return None
        self._add_node("rollup_result", rr.id, created_at=rr.created_at, run_id=rr.run_id, checksum=rr.checksum)
        if rr.rollup_config_id:
            cfg = self.db.get(RollupConfig, rr.rollup_config_id)
            if cfg and cfg.tenant_id == self.tenant_id:
                self._add_node("rollup_config", cfg.id, label=cfg.name, created_at=cfg.created_at, created_by=cfg.created_by)
                self._add_edge("rollup_result", rr.id, "rollup_config", cfg.id, "DEPENDS_ON")
        if rr.exposure_version_id:
            self._add_node("exposure_version", rr.exposure_version_id)
            self._add_edge("rollup_result", rr.id, "exposure_version", rr.exposure_version_id, "DEPENDS_ON")
        overlay_ids = (rr.hazard_overlay_result_ids_json or [])
        for oid in overlay_ids:
            overlay = self.db.get(HazardOverlayResult, oid)
            if overlay and overlay.tenant_id == self.tenant_id:
                self._add_node("hazard_overlay_result", overlay.id, created_at=overlay.created_at, run_id=overlay.run_id)
                self._add_edge("rollup_result", rr.id, "hazard_overlay_result", overlay.id, "DEPENDS_ON")
                hdv = self.db.get(HazardDatasetVersion, overlay.hazard_dataset_version_id)
                if hdv and hdv.tenant_id == self.tenant_id:
                    self._add_node("hazard_dataset_version", hdv.id, label=hdv.version_label, checksum=hdv.checksum, created_at=hdv.created_at)
                    self._add_edge("hazard_overlay_result", overlay.id, "hazard_dataset_version", hdv.id, "DEPENDS_ON")
                    hd = self.db.get(HazardDataset, hdv.hazard_dataset_id)
                    if hd and hd.tenant_id == self.tenant_id:
                        self._add_node("hazard_dataset", hd.id, label=hd.name, created_at=hd.created_at)
                        self._add_edge("hazard_dataset_version", hdv.id, "hazard_dataset", hd.id, "DEPENDS_ON")
        if rr.run_id:
            run = self.db.get(Run, rr.run_id)
            if run and run.tenant_id == self.tenant_id:
                self._add_node("run", run.id, created_at=run.created_at, created_by=run.created_by, checksum=None)
                self._add_edge("rollup_result", rr.id, "run", run.id, "PRODUCED_BY")
        return self._finalize("rollup_result", rr.id)

    def build_for_breach(self, breach_id: int):
        breach = self.db.get(Breach, breach_id)
        if not breach or breach.tenant_id != self.tenant_id:
            return None
        self._add_node("breach", breach.id, created_at=breach.first_seen_at, run_id=breach.last_eval_run_id)
        self._add_node("threshold_rule", breach.threshold_rule_id)
        self._add_edge("breach", breach.id, "threshold_rule", breach.threshold_rule_id, "DEPENDS_ON")
        self._add_node("rollup_result", breach.rollup_result_id)
        self._add_edge("breach", breach.id, "rollup_result", breach.rollup_result_id, "DEPENDS_ON")
        self._add_node("exposure_version", breach.exposure_version_id)
        self._add_edge("breach", breach.id, "exposure_version", breach.exposure_version_id, "DEPENDS_ON")
        if breach.last_eval_run_id:
            self._add_node("run", breach.last_eval_run_id)
            self._add_edge("breach", breach.id, "run", breach.last_eval_run_id, "PRODUCED_BY")
        return self._finalize("breach", breach.id)

    def build_for_drift(self, drift_run_id: int):
        drift = self.db.get(DriftRun, drift_run_id)
        if not drift or drift.tenant_id != self.tenant_id:
            return None
        self._add_node("drift_run", drift.id, created_at=drift.created_at, run_id=drift.run_id, checksum=drift.checksum)
        self._add_node("exposure_version", drift.exposure_version_a_id)
        self._add_node("exposure_version", drift.exposure_version_b_id)
        self._add_edge("drift_run", drift.id, "exposure_version", drift.exposure_version_a_id, "DEPENDS_ON")
        self._add_edge("drift_run", drift.id, "exposure_version", drift.exposure_version_b_id, "DEPENDS_ON")
        if drift.run_id:
            run = self.db.get(Run, drift.run_id)
            if run and run.tenant_id == self.tenant_id:
                self._add_node("run", run.id, created_at=run.created_at, created_by=run.created_by)
                self._add_edge("drift_run", drift.id, "run", run.id, "PRODUCED_BY")
        return self._finalize("drift_run", drift.id)

    def build_for_exposure_version(self, exposure_version_id: int):
        ev = self.db.get(ExposureVersion, exposure_version_id)
        if not ev or ev.tenant_id != self.tenant_id:
            return None
        self._add_node("exposure_version", ev.id, created_at=ev.created_at)
        rollups = self.db.execute(
            select(RollupResult).where(
                RollupResult.tenant_id == self.tenant_id, RollupResult.exposure_version_id == ev.id
            )
        ).scalars().all()
        for rr in rollups:
            self._add_node("rollup_result", rr.id, checksum=rr.checksum)
            self._add_edge("rollup_result", rr.id, "exposure_version", ev.id, "DEPENDS_ON")
        overlays = self.db.execute(
            select(HazardOverlayResult).where(
                HazardOverlayResult.tenant_id == self.tenant_id, HazardOverlayResult.exposure_version_id == ev.id
            )
        ).scalars().all()
        for ov in overlays:
            self._add_node("hazard_overlay_result", ov.id, created_at=ov.created_at, run_id=ov.run_id)
            self._add_edge("hazard_overlay_result", ov.id, "exposure_version", ev.id, "DEPENDS_ON")
        drifts = self.db.execute(
            select(DriftRun).where(DriftRun.tenant_id == self.tenant_id).where(
                (DriftRun.exposure_version_a_id == ev.id) | (DriftRun.exposure_version_b_id == ev.id)
            )
        ).scalars().all()
        for dr in drifts:
            self._add_node("drift_run", dr.id, checksum=dr.checksum)
            self._add_edge("drift_run", dr.id, "exposure_version", ev.id, "DEPENDS_ON")
        return self._finalize("exposure_version", ev.id)

    def build_for_overlay(self, overlay_result_id: int):
        overlay = self.db.get(HazardOverlayResult, overlay_result_id)
        if not overlay or overlay.tenant_id != self.tenant_id:
            return None
        self._add_node("hazard_overlay_result", overlay.id, created_at=overlay.created_at, run_id=overlay.run_id)
        self._add_node("exposure_version", overlay.exposure_version_id)
        self._add_edge("hazard_overlay_result", overlay.id, "exposure_version", overlay.exposure_version_id, "DEPENDS_ON")
        hdv = self.db.get(HazardDatasetVersion, overlay.hazard_dataset_version_id)
        if hdv and hdv.tenant_id == self.tenant_id:
            self._add_node("hazard_dataset_version", hdv.id, label=hdv.version_label, checksum=hdv.checksum)
            self._add_edge("hazard_overlay_result", overlay.id, "hazard_dataset_version", hdv.id, "DEPENDS_ON")
            hd = self.db.get(HazardDataset, hdv.hazard_dataset_id)
            if hd and hd.tenant_id == self.tenant_id:
                self._add_node("hazard_dataset", hd.id, label=hd.name)
                self._add_edge("hazard_dataset_version", hdv.id, "hazard_dataset", hd.id, "DEPENDS_ON")
        if overlay.run_id:
            run = self.db.get(Run, overlay.run_id)
            if run and run.tenant_id == self.tenant_id:
                self._add_node("run", run.id, created_at=run.created_at, created_by=run.created_by)
                self._add_edge("hazard_overlay_result", overlay.id, "run", run.id, "PRODUCED_BY")
        return self._finalize("hazard_overlay_result", overlay.id)

    def _finalize(self, root_type: str, root_id: Any):
        return {
            "root": {"type": root_type, "id": root_id},
            "nodes": list(self.nodes.values()),
            "edges": self.edges,
        }


def build_lineage(db: Session, tenant_id: str, entity_type: str, entity_id: int):
    builder = LineageBuilder(db, tenant_id)
    if entity_type == "rollup_result":
        return builder.build_for_rollup_result(entity_id)
    if entity_type == "hazard_overlay_result":
        return builder.build_for_overlay(entity_id)
    if entity_type == "hazard_dataset_version":
        hdv = db.get(HazardDatasetVersion, entity_id)
        if not hdv or hdv.tenant_id != tenant_id:
            return None
        builder._add_node("hazard_dataset_version", hdv.id, label=hdv.version_label, checksum=hdv.checksum, created_at=hdv.created_at)
        if hdv.hazard_dataset_id:
            hd = db.get(HazardDataset, hdv.hazard_dataset_id)
            if hd and hd.tenant_id == tenant_id:
                builder._add_node("hazard_dataset", hd.id, label=hd.name)
                builder._add_edge("hazard_dataset_version", hdv.id, "hazard_dataset", hd.id, "DEPENDS_ON")
        return builder._finalize("hazard_dataset_version", entity_id)
    if entity_type == "breach":
        return builder.build_for_breach(entity_id)
    if entity_type == "drift_run":
        return builder.build_for_drift(entity_id)
    if entity_type == "exposure_version":
        return builder.build_for_exposure_version(entity_id)
    return None
