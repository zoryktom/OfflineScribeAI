.PHONY: test eval test-ui

test:
	cd backend && .venv/bin/python -m pytest

eval:
	cd backend && .venv/bin/python -m pytest -m eval -o addopts=
	cd backend && .venv/bin/python -m app.eval_harness

test-ui:
	cd desktop-app && npm test
