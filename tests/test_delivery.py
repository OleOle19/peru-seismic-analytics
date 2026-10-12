import io
from argparse import Namespace
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from seismic import pipeline


def test_sql_failure_keeps_published_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    published = tmp_path / "data" / "processed"
    published.mkdir(parents=True)
    (published / "events.csv").write_text("previous snapshot", encoding="utf-8")
    feature = {
        "id": "a",
        "geometry": {"type": "Point", "coordinates": [-77, -12, 30]},
        "properties": {
            "mag": 4.5,
            "time": 1704067200000,
            "updated": 1704153600000,
            "type": "earthquake",
        },
    }
    monkeypatch.setattr(pipeline, "download", lambda *a: ([feature], []))

    def fail(*a):
        raise RuntimeError("SQL unavailable")

    monkeypatch.setattr(pipeline, "load_sql", fail)
    args = Namespace(
        start="2024-01-01",
        end="2025-01-01",
        min_magnitude=3.5,
        from_raw=None,
        no_sql=False,
        upload_s3=False,
    )
    with pytest.raises(RuntimeError, match="SQL unavailable"):
        pipeline.run(args)
    assert (published / "events.csv").read_text() == "previous snapshot"


class Body(io.BytesIO):
    def iter_chunks(self, chunk_size):
        while chunk := self.read(chunk_size):
            yield chunk


@pytest.mark.parametrize("corrupt", [False, True])
def test_s3_verifies_remote_content(tmp_path, monkeypatch, corrupt):
    import boto3

    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    monkeypatch.setenv("AWS_S3_BUCKET", "example-test-bucket")
    path = tmp_path / "public.csv"
    path.write_bytes(b"event_id\na\n")

    class Client:
        def upload_file(self, *a, **kw):
            assert kw["ExtraArgs"]["ServerSideEncryption"] == "AES256"

        def get_object(self, **kw):
            return {
                "Body": Body(b"corrupt" if corrupt else path.read_bytes()),
                "ServerSideEncryption": "AES256",
            }

    class Session:
        def __init__(self, **kw):
            pass

        def client(self, name):
            assert name == "s3"
            return Client()

    monkeypatch.setattr(boto3, "Session", Session)
    if corrupt:
        with pytest.raises(ValueError, match="integrity"):
            pipeline.upload_s3([path], "test")
    else:
        pipeline.upload_s3([path], "test")
