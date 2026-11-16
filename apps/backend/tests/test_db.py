import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (registers tables)
from app.db import Base
from app.models import Clip, Project, Video


@pytest.fixture()
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        yield db
    engine.dispose()


def _video(db, project):
    video = Video(
        project_id=project.id,
        original_filename="talk.mp4",
        stored_path="uploads/talk.mp4",
        size_bytes=1234,
        status="ready",
        duration_sec=612.5,
        width=1920,
        height=1080,
    )
    db.add(video)
    db.commit()
    return video


def test_project_video_clip_roundtrip(session):
    project = Project(name="Podcast")
    session.add(project)
    session.commit()

    video = _video(session, project)
    session.add(
        Clip(
            video_id=video.id,
            title="Hook about pricing",
            start_sec=10.0,
            end_sec=42.5,
            status="candidate",
        )
    )
    session.commit()

    stored = session.scalars(select(Clip)).one()
    assert stored.title == "Hook about pricing"
    assert stored.start_sec < stored.end_sec


def test_clip_rejects_inverted_range(session):
    project = Project(name="Podcast")
    session.add(project)
    session.commit()
    video = _video(session, project)

    session.add(Clip(video_id=video.id, title="Broken", start_sec=50.0, end_sec=10.0))
    with pytest.raises(IntegrityError):
        session.commit()


def test_deleting_project_cascades_to_videos(session):
    project = Project(name="Podcast")
    session.add(project)
    session.commit()
    _video(session, project)

    session.delete(project)
    session.commit()

    assert session.scalars(select(Video)).all() == []
