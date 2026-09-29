#!/bin/bash
# Baut das Segway-Manuskript: Bilder, Rechnung, PDF, DOCX, Prüfprotokoll. Aufruf: bash baue_manuskript.sh [Fassung]
set -e
cd "$(dirname "$0")"
F=${1:-6}
echo "== Bilder zeichnen"; python3 Bilder/erstelle_bilder.py
echo "== Übertragungsfunktion rechnen"; (cd Modell && python3 uebertragungsfunktion.py > /dev/null)
echo "== Bild Hardwaretest"; python3 Einfuehrung/erstelle_einfuehrung.py --manuskriptbild
echo "== PDF"; pandoc MANUSKRIPT_Segway_Gesamt.md -o MANUSKRIPT_Segway_Gesamt.pdf --pdf-engine=xelatex -V geometry:margin=2.2cm \
  -V mainfont="DejaVu Serif" -V sansfont="DejaVu Sans" -V monofont="DejaVu Sans Mono" -V fontsize=10pt --toc --toc-depth=2 --number-sections
echo "== DOCX"; pandoc MANUSKRIPT_Segway_Gesamt.md -o MANUSKRIPT_Segway_Gesamt.docx --toc --toc-depth=2 --number-sections
cp MANUSKRIPT_Segway_Gesamt.pdf MANUSKRIPT_Segway_Gesamt_F$F.pdf; cp MANUSKRIPT_Segway_Gesamt.docx MANUSKRIPT_Segway_Gesamt_F$F.docx
pdfinfo MANUSKRIPT_Segway_Gesamt_F$F.pdf | grep Pages
echo "== Prüfprotokoll"; (cd Modell && python3 pruefe_modellkapitel.py)
echo "== Einführung"; python3 Einfuehrung/erstelle_einfuehrung.py && python3 Einfuehrung/pruefe_einfuehrung.py
