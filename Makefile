.PHONY: build-probe build test-amiga run-probe run replay regression stress validate-data package-amiga

build-probe:
	./scripts/build-amiga-probe.sh

build:
	./scripts/build-amiga.sh

test-amiga:
	python3 scripts/amiga-test.py probe $(ARGS)

run-probe:
	python3 scripts/amiga-test.py probe-interactive $(ARGS)

run:
	python3 scripts/amiga-test.py run $(ARGS)

replay:
	python3 scripts/amiga-test.py replay $(ARGS)

regression:
	python3 scripts/amiga-test.py regression $(ARGS)

stress:
	python3 scripts/amiga-test.py stress $(ARGS)

validate-data:
	python3 scripts/amiga-test.py validate-data $(ARGS)

package-amiga:
	python3 scripts/package-amiga.py $(ARGS)
