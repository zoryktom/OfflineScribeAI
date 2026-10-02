PYTHON := $(shell if [ -x "$(CURDIR)/backend/.venv/bin/python" ]; then echo "$(CURDIR)/backend/.venv/bin/python"; else command -v python3; fi)

.PHONY: install test lint eval eval-full annotate paper release test-ui

install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest tests -q
	cd backend && $(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check src tests

eval:
	$(PYTHON) -m offlinescribe.cli eval run --config experiments/configs/pilot.yaml
	cd backend && STUB_MODE=1 $(PYTHON) -m pytest -m eval -q -o addopts=
	cd backend && STUB_MODE=1 $(PYTHON) -m app.eval_harness

eval-full:
	$(PYTHON) -m offlinescribe.cli eval run --config experiments/configs/ablation_v1.yaml

annotate:
	$(PYTHON) -m offlinescribe.cli annotate --encounter E001 --condition baseline --annotator A1 --non-interactive

paper:
	@echo "paper/main.tex is a skeleton. Compile with pdflatex when TeX is installed."
	@echo "Do not treat stub metrics as results."

release:
	@echo "Tag a release locally, then create a Zenodo archive from that tag."

test-ui:
	cd desktop-app && npm test
