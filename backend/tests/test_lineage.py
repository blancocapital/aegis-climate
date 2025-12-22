from datetime import datetime

from app.models import (
    Breach,
    DriftRun,
    ExposureVersion,
    HazardDataset,
    HazardDatasetVersion,
    HazardOverlayResult,
    RollupConfig,
    RollupResult,
    Run,
)
from app.services.lineage import build_lineage


class FakeResult:
    def __init__(self, items):
        self.items = items

    def scalars(self):
        return self

    def all(self):
        return self.items

    def first(self):
        return self.items[0] if self.items else None

    def scalar(self):
        return self.items[0] if self.items else None

    def scalar_one_or_none(self):
        return self.items[0] if self.items else None


class FakeSession:
    def __init__(self, objects, collections):
        self.objects = objects
        self.collections = collections

    def get(self, model, key):
        return self.objects.get((model, key))

    def execute(self, query):
        entity = None
        if hasattr(query, "column_descriptions"):
            desc = query.column_descriptions
            if desc and "entity" in desc[0]:
                entity = desc[0]["entity"]
        items = self.collections.get(entity, [])
        return FakeResult(items)


def test_rollup_lineage_graph():
    tenant = "t1"
    now = datetime.utcnow()
    ev = ExposureVersion(id=1, tenant_id=tenant, name="ev", created_at=now)
    rc = RollupConfig(id=3, tenant_id=tenant, name="cfg", version=1, created_at=now)
    overlay = HazardOverlayResult(
        id=4,
        tenant_id=tenant,
        exposure_version_id=1,
        hazard_dataset_version_id=5,
        created_at=now,
        run_id=None,
    )
    hdv = HazardDatasetVersion(
        id=5,
        tenant_id=tenant,
        hazard_dataset_id=6,
        version_label="v1",
        checksum="chk",
        created_at=now,
    )
    hd = HazardDataset(id=6, tenant_id=tenant, name="ds", peril="wind", created_at=now)
    run = Run(id=9, tenant_id=tenant, run_type=None, status=None, created_at=now)
    rr = RollupResult(
        id=2,
        tenant_id=tenant,
        exposure_version_id=1,
        rollup_config_id=3,
        hazard_overlay_result_ids_json=[4],
        checksum="abc",
        created_at=now,
        run_id=9,
    )
    objects = {
        (ExposureVersion, 1): ev,
        (RollupConfig, 3): rc,
        (HazardOverlayResult, 4): overlay,
        (HazardDatasetVersion, 5): hdv,
        (HazardDataset, 6): hd,
        (Run, 9): run,
        (RollupResult, 2): rr,
    }
    collections = {RollupResult: [rr], HazardOverlayResult: [overlay], DriftRun: [], Breach: []}
    session = FakeSession(objects, collections)
    lineage = build_lineage(session, tenant, "rollup_result", 2)
    assert lineage
    node_types = {n["type"] for n in lineage["nodes"]}
    assert {"rollup_result", "rollup_config", "exposure_version", "hazard_overlay_result", "hazard_dataset_version", "hazard_dataset", "run"}.issubset(node_types)
    edge_relations = {(e["from"], e["to"], e["relation"]) for e in lineage["edges"]}
    assert ("rollup_result:2", "hazard_overlay_result:4", "DEPENDS_ON") in edge_relations
    assert ("hazard_dataset_version:5", "hazard_dataset:6", "DEPENDS_ON") in edge_relations
    assert ("rollup_result:2", "run:9", "PRODUCED_BY") in edge_relations
