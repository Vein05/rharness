MAIN = main
.PHONY: all clean
all: $(MAIN).pdf
$(MAIN).pdf: $(MAIN).tex references.bib $(wildcard sections/*.tex)
	latexmk -pdf -interaction=nonstopmode $(MAIN).tex
clean:
	latexmk -C $(MAIN).tex
