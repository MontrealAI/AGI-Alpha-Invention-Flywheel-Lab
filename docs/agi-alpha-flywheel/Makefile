SHELL := /bin/bash
BUILD := build
PAPER := $(BUILD)/paper.pdf

.PHONY: all check clean
all: $(PAPER)

$(PAPER): paper.tex references.bib $(wildcard figures/*.tex)
	mkdir -p $(BUILD)
	latexmk -pdf -pdflatex='pdflatex -no-shell-escape %O %S' -interaction=nonstopmode -halt-on-error -file-line-error -outdir=$(BUILD) paper.tex

check: $(PAPER)
	python3 verify_publication.py --build-only

clean:
	latexmk -C -outdir=$(BUILD) paper.tex
