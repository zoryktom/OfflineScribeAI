PYTHON := $(shell if [ -x "$(CURDIR)/backend/.venv/bin/python" ]; then echo "$(CURDIR)/backend/.venv/bin/python"; else command -v python3; fi)

.PHONY: install test eval eval-full paper test-ui

install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest tests -q
	cd backend && $(PYTHON) -m pytest -q

eval:
	$(PYTHON) -m offlinescribe.cli eval run --config experiments/configs/sample.yaml
	cd backend && STUB_MODE=1 $(PYTHON) -m pytest -m eval -q -o addopts=
	cd backend && STUB_MODE=1 $(PYTHON) -m app.eval_harness

eval-full:
	$(PYTHON) -m offlinescribe.cli eval run --config experiments/configs/ablation_v1.yaml

paper:
	@echo "paper/main.tex is a skeleton. Compile with pdflatex when TeX is installed."
	@echo "Do not treat stub metrics as results."

test-ui:
	cd desktop-app && npm test
