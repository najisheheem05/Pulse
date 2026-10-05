.PHONY: run demo test sim reset clean vendor

run:
	PYTHONPATH=. uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

demo:
	SCENARIO=$(SCENARIO) bash scripts/demo.sh

test:
	pytest -q

sim:
	python3 -m src.simulator.emitter --help

reset:
	curl -s -X POST http://localhost:8000/api/sim/reset | head -c 500; echo

clean:
	rm -f hospital.db
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true

vendor:
	mkdir -p public/vendor
	curl -sL https://cdn.jsdelivr.net/npm/cytoscape@3.28.1/dist/cytoscape.min.js -o public/vendor/cytoscape.min.js || echo "offline: CDN fallback will be used"
	curl -sL https://cdn.jsdelivr.net/npm/htmx.org@1.9.12/dist/htmx.min.js -o public/vendor/htmx.min.js || echo "offline: CDN fallback will be used"
	ls -la public/vendor || true
