"""Tests for consistency profile workspace model contracts."""
from __future__ import annotations

import pytest

from zhihu_fiction.workspace.models import ConsistencyProfile


def test_consistency_profile_round_trips_structured_fields():
    profile = ConsistencyProfile(
        id="profile_1",
        project_id="project_1",
        session_id="deepagent_1",
        source_version_ids=["version_script_1", "version_plot_1"],
        characters=[
            {"name": "林晚", "age": 28, "traits": ["冷静", "敏锐"]},
        ],
        world_facts=[
            {"key": "setting", "value": "山西小城"},
        ],
        visual_style={"palette": ["black", "amber"], "avoid": ["现代豪宅"]},
        narrative_constraints=["主角不能提前知道真相", "异味线索必须逐步升级"],
        asset_bindings={"林晚": {"ref_image": "asset_character_linwan"}},
        created_at="2026-06-15T09:00:00+00:00",
        updated_at="2026-06-15T10:00:00+00:00",
    )

    payload = profile.to_dict()
    restored = ConsistencyProfile.from_dict(payload)

    assert payload == {
        "id": "profile_1",
        "project_id": "project_1",
        "session_id": "deepagent_1",
        "source_version_ids": ["version_script_1", "version_plot_1"],
        "characters": [
            {"name": "林晚", "age": 28, "traits": ["冷静", "敏锐"]},
        ],
        "world_facts": [
            {"key": "setting", "value": "山西小城"},
        ],
        "visual_style": {"palette": ["black", "amber"], "avoid": ["现代豪宅"]},
        "narrative_constraints": ["主角不能提前知道真相", "异味线索必须逐步升级"],
        "asset_bindings": {"林晚": {"ref_image": "asset_character_linwan"}},
        "created_at": "2026-06-15T09:00:00+00:00",
        "updated_at": "2026-06-15T10:00:00+00:00",
    }
    assert restored == profile


@pytest.mark.parametrize("project_id, session_id", [("", "deepagent_1"), ("project_1", "")])
def test_consistency_profile_requires_project_and_session(project_id, session_id):
    with pytest.raises(ValueError):
        ConsistencyProfile(
            id="profile_1",
            project_id=project_id,
            session_id=session_id,
        )
