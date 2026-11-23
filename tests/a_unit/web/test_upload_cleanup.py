# Copyright (c) 2012-2024, Abilian SAS

"""The hourly cleanup of uploads: stalled files go, and one gone already is no
error, as when two cleanups run at once."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from abilian.web.uploads.extension import remove_if_stalled

if TYPE_CHECKING:
    from pathlib import Path


def test_a_stalled_upload_is_removed(tmp_path: Path) -> None:
    upload = tmp_path / "upload"
    upload.write_bytes(b"x")

    remove_if_stalled(upload, minimum_age=time.time() + 60)

    assert not upload.exists()


def test_a_recent_upload_is_kept(tmp_path: Path) -> None:
    upload = tmp_path / "upload"
    upload.write_bytes(b"x")

    remove_if_stalled(upload, minimum_age=time.time() - 60)

    assert upload.exists()


def test_an_upload_removed_meanwhile_is_no_error(tmp_path: Path) -> None:
    remove_if_stalled(tmp_path / "gone", minimum_age=time.time() + 60)

    assert list(tmp_path.iterdir()) == []
