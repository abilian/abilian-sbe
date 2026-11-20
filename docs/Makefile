# Documentation, built with Zensical (https://zensical.org/).
#
# Zensical is in the repository's `doc` dependency group, so `--project ..` runs
# it from the repository's venv rather than needing one in here.

.PHONY: all preprocess build serve preview check shots clean

ZENSICAL = uv run --project .. zensical

all: build

# The French edition's config and assets: see preprocess.py. Each edition
# builds to its own site/<lang>/, English from zensical.toml and French from
# the generated zensical.fr.toml; then the chooser goes at the root.
preprocess:
	uv run --project .. python preprocess.py

SITE_ROOT = uv run --project .. python preprocess.py --site-root
EACH_EDITION = for config in zensical.*.toml; do $(ZENSICAL) build $(1) -f $$config || exit 1; done

build: preprocess
	$(ZENSICAL) build
	@$(call EACH_EDITION)
	$(SITE_ROOT)

# Live-reloading, one edition at a time: `make serve EDITION=fr` for French.
serve: preprocess
	$(ZENSICAL) serve $(if $(EDITION),-f zensical.$(EDITION).toml)

preview: build
	python3 -m http.server -d site 8000

# Fail on warnings: a broken cross-reference is a broken build.
check: preprocess
	$(ZENSICAL) build --strict
	@$(call EACH_EDITION,--strict)
	$(SITE_ROOT)

# The screenshots, from a throwaway instance with demo data, in both
# languages. Needs redis-server, a browser and a few minutes; see shots.py.
shots:
	uv run --project .. --with playwright==$$(cat ../e2e_playwright/playwright-version) python shots.py

clean:
	rm -rf site .cache i18n/*/assets zensical.*.toml
