.PHONY: all check clean
all:
	latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build paper.tex
check: all
	python3 -m unittest discover -s . -p 'test_companion.py' -v
	python3 verify.py --build-only
clean:
	latexmk -C -outdir=build paper.tex
