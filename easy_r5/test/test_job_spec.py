"""Job spec validation. Pure Python — run: py -m pytest easy_r5/test/test_job_spec.py -v"""

import json

import pytest

from easy_r5.core.job_spec import (
    JobSpecError,
    build_info_job,
    parse_percentiles,
    validate_percentiles,
    write_job,
)


def test_percentiles_ok_single():
    assert validate_percentiles([50]) == [50]


def test_percentiles_ok_five():
    assert validate_percentiles([10, 25, 50, 75, 90]) == [10, 25, 50, 75, 90]


def test_percentiles_six_raises():
    with pytest.raises(JobSpecError, match="at most 5"):
        validate_percentiles([10, 25, 50, 75, 85, 95])


def test_percentiles_not_ascending_raises():
    with pytest.raises(JobSpecError, match="ascending"):
        validate_percentiles([50, 25])


def test_percentiles_equal_not_strict_raises():
    with pytest.raises(JobSpecError, match="ascending"):
        validate_percentiles([50, 50])


@pytest.mark.parametrize("bad", [[0], [100], [-1]])
def test_percentiles_out_of_range_raises(bad):
    with pytest.raises(JobSpecError, match="range"):
        validate_percentiles(bad)


def test_percentiles_bool_rejected():
    with pytest.raises(JobSpecError):
        validate_percentiles([True])


def test_parse_percentiles_string():
    assert parse_percentiles("25, 50 ,75") == [25, 50, 75]


def test_parse_percentiles_rejects_duplicates():
    with pytest.raises(JobSpecError):
        parse_percentiles("25,50,50")


def test_parse_percentiles_rejects_words():
    with pytest.raises(JobSpecError):
        parse_percentiles("median")


def test_build_info_job():
    assert build_info_job("C:/x/network.dat") == {
        "command": "info",
        "network": "C:/x/network.dat",
    }


def test_build_info_job_empty_raises():
    with pytest.raises(JobSpecError):
        build_info_job("  ")


def test_write_job_roundtrip(tmp_path):
    job = {"command": "info", "network": "C:/x/network.dat"}
    path = write_job(job, tmp_path)
    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert json.loads(text) == job
    assert path.parent == tmp_path
