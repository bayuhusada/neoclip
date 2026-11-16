import app.models  # noqa: F401  (registers tables)
from app.db import Base
from app.models import Clip, Job, Project, Transcript, Video

EXPECTED_TABLES = {"projects", "videos", "transcripts", "clips", "jobs"}


def test_metadata_has_all_tables():
    assert EXPECTED_TABLES <= set(Base.metadata.tables)


def test_models_are_importable():
    for model in (Project, Video, Transcript, Clip, Job):
        assert model.__tablename__ in EXPECTED_TABLES
