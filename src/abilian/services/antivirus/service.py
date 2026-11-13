# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

import io
import os
import pathlib

from loguru import logger

from abilian.core.models.blob import Blob
from abilian.services.base import Service

try:
    from clamd import ClamdError, ClamdUnixSocket

    clamd = ClamdUnixSocket()
except ImportError:
    clamd = None

CLAMD_CONF = {"StreamMaxLength": "25M", "MaxFileSize": "25M"}
CLAMD_STREAMMAXLENGTH = 26214400
CLAMD_MAXFILESIZE = 26214400

if clamd:
    conf_path = pathlib.Path("/etc", "clamav", "clamd.conf")
    if conf_path.exists():
        conf_lines = [line.strip() for line in conf_path.open("rt").readlines()]
        CLAMD_CONF = dict(
            line.split(" ", 1) for line in conf_lines if not line.startswith("#")
        )

        def _size_to_int(size_str):
            multiplier = 0
            if not size_str:
                return 0

            unit = size_str[-1].lower()
            if unit in ("k", "m"):
                size_str = size_str[:-1]
                multiplier = 1024
                if unit == "m":
                    multiplier *= 1024

            if not size_str:
                return 0

            size = int(size_str)
            if multiplier:
                size *= multiplier

            return size

        CLAMD_STREAMMAXLENGTH = _size_to_int(CLAMD_CONF["StreamMaxLength"])
        CLAMD_MAXFILESIZE = _size_to_int(CLAMD_CONF["MaxFileSize"])
        del conf_path, conf_lines, _size_to_int


class AntiVirusService(Service):
    """Antivirus service."""

    name = "antivirus"

    def scan(self, file_or_stream):
        """
        :param file_or_stream: :class:`Blob` instance, filename or file object

        :returns: True if file is 'clean', False if a virus is detected, None if
        file could not be scanned.

        If `file_or_stream` is a Blob, scan result is stored in
        Blob.meta['antivirus'].
        """
        if not clamd:
            return None

        res = self._scan(file_or_stream)
        if isinstance(file_or_stream, Blob):
            file_or_stream.meta["antivirus"] = res
        return res

    def _scan(self, file_or_stream):
        content = file_or_stream
        match file_or_stream:
            case Blob():
                try:
                    file_or_stream = bytes(file_or_stream.file)
                except TypeError as e:
                    self.logger.warning(
                        "Error during content scan: {error}", error=str(e)
                    )
                    return None

            case str():
                file_or_stream = file_or_stream.encode(os.fsencode)

        if isinstance(file_or_stream, bytes):
            content = open(file_or_stream, "rb")

        if content.seekable():
            pos = content.tell()
            content.seek(0, io.SEEK_END)
            size = content.tell()
            content.seek(pos)

            if size > CLAMD_STREAMMAXLENGTH:
                logger.error(
                    "Content size exceed antivirus size limit, "
                    "size={size}, limit={limit} "
                    "({max_length})",
                    size=size,
                    limit=CLAMD_STREAMMAXLENGTH,
                    max_length=CLAMD_CONF["StreamMaxLength"].encode("utf8"),
                    extra={"stack": True},
                )
                return None

        # use stream scan. When using scan by filename, clamd runnnig user must have
        # access to file, which we cannot guarantee
        scan = clamd.instream
        try:
            res = scan(content)
        except ClamdError as e:
            self.logger.warning(
                "Error during content scan: {error}",
                error=str(e),
            )
            return None

        if "stream" not in res:
            # may happen if file doesn't exists
            return False

        res = res["stream"]
        return res[0] == "OK"


service = AntiVirusService()
