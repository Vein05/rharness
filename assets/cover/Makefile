PYTHON ?= python3
CHECK ?= $(HOME)/Documents/research/figures/check_svg.py
.PHONY: all check png clean
all: build/cover.png
build/cover.svg: build.py $(wildcard icons/*.svg)
	$(PYTHON) build.py
check: build/cover.svg
	$(PYTHON) $(CHECK) build/cover.svg
build/cover.png: build/cover.svg
	rsvg-convert -f png --zoom 1 -o $@ $<
clean:
	rm -rf build
