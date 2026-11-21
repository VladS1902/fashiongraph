PY := .venv/bin/python
.PHONY: smoke-free run-free free-plan readiness-free smoke-all run-real publish-results report smoke-docs setup lint test data gold rdf audit mock site slides serve readiness check all
setup:
	python3 -m venv .venv && .venv/bin/pip install -q rdflib pytest ruff requests pyshacl pypdf markdown python-pptx
lint:
	.venv/bin/ruff check . && .venv/bin/ruff format --check .
test:
	$(PY) -m pytest -q
data:        # needs data/raw/cnmi_calendar.html (git-ignored; re-download from the CNMI calendar URL)
	$(PY) data/scripts/parse_cnmi.py data/raw/cnmi_calendar.html data/cnmi_calendar_parsed.jsonl
gold:
	$(PY) data/scripts/build_gold.py && $(PY) -m experiments.inputs
rdf:
	$(PY) -m rdf.build_gold_ttl
audit:
	$(PY) -m rdf.audit
mock:        # deterministic, free; output is MOCK and never publishable
	$(PY) -m experiments.pipeline mock
report:
	$(PY) reports/build_report.py
site: report
	$(PY) site/build.py
check: lint test
all: gold rdf audit mock report site slides check

readiness:   # no network, no paid calls; exit 1 until human gates are resolved
	$(PY) -m experiments.readiness

serve:       # preview the built site at http://127.0.0.1:8765
	$(PY) site/build.py && python3 -m http.server 8765 --directory site/dist --bind 127.0.0.1

slides:
	$(PY) slides/build_slides.py

# ---- real experiment (needs a git-ignored .env with keys and FASHIONGRAPH_APPROVED_SPEND=1; see docs/runbook.md) ----
ENV := set -a; [ -f .env ] && . ./.env; set +a
smoke-all:   # 3 billed calls (about EUR 0.01 in total), one per provider
	@$(ENV); for p in openai gemini mistral; do $(PY) -m experiments.smoke --provider $$p || exit 1; done
run-real:    # 90 calls under the enforced EUR 5 cap; resumable; refuses without approval
	@$(ENV); $(PY) -m experiments.pipeline real --models models.json
publish-results:  # validated, complete, non-mock runs only; then rebuild report, site, slides
	$(PY) -m evaluation.publish outputs/real/metrics.json && $(MAKE) report site slides

# ---- ZERO-COST configuration (models.free.json: Gemini free tier + Groq free plan; nothing is billed) ----
smoke-free:  # 3 live calls (free tier), one per model; stops at the first failure
	@$(ENV); $(PY) -m experiments.smoke --provider gemini --models models.free.json && \
	$(PY) -m experiments.smoke --provider groq --model-id openai/gpt-oss-120b --models models.free.json && \
	$(PY) -m experiments.smoke --provider groq --model-id qwen/qwen3.8-27b --models models.free.json
run-free:    # 90 paced calls under the free quotas (about 20 minutes); resumable
	@$(ENV); $(PY) -m experiments.pipeline real --models models.free.json --out outputs/real
free-plan:   # regenerate docs/free-tier-plan.md from the real prompts
	$(PY) -m experiments.cost_estimate --free --write docs/free-tier-plan.md
readiness-free:
	@$(ENV); $(PY) -m experiments.readiness --models models.free.json
