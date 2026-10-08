# Soaring CTRW: 11 slide

[PDF](soaring_ctrw_visual_11slides.pdf) e
[sorgente LaTeX dedicato](soaring_ctrw_visual_11slides.tex), con copertina non
numerata e 11 slide principali (12 pagine in totale), senza appendice.

La versione deriva da `soaring_ctrw_visual_with_appendix.tex` nella cartella
`disante_soaring_ctrw/13_06_26_paper_slides/visual_v3`, ed è stata copiata qui
con le revisioni dell'8 ottobre 2026: definizione esplicita di `G_N` nella
slide 5, separazione dei contributi diffusivo e coerente, e grafico più grande
nella slide 11. Il caso power law con cutoff non compare nell'ultima slide.

## Compilazione

Tutte le figure necessarie sono incluse. Con una distribuzione LaTeX contenente
Beamer, TikZ, Palatino e `latexmk`, dalla cartella del deck:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error soaring_ctrw_visual_11slides.tex
```

Non servono dati esterni per compilare. `make_figures.py` e
`make_search_clock.py` rigenerano le figure analitiche e gli schemi illustrativi
con NumPy, SciPy e Matplotlib. Le figure Monte Carlo e di calibrazione sono
riutilizzate dalla versione originale; questi script non rieseguono le
simulazioni né i fit empirici.
