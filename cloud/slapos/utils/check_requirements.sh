#!/bin/sh

# local repository of SlapOS containing a SBE configuration for SlapOS
SLAPOS="~/dev/abi/gits/hox/slapos"
VERSIONS="${SLAPOS}/software/abilian-sbe/versions.cfg"

# requirements of SBE app
REQS="requirements_no_dev.txt"

# extract SBE requirements
uv export --no-dev --no-hashes --format requirements-txt > ${REQS}

# show analysis of differences
python diff_reqs_soft_vers.py "${REQS}" "${VERSIONS}"
