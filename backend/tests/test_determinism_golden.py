from app.storage import s3


def test_checksum_deterministic(tmp_path):
    data = b"example row errors"
    first = s3.compute_checksum(data)
    second = s3.compute_checksum(data)
    assert first == second
