"""Write explicit layout-only wrappers; never change the delivered slide source."""
from pathlib import Path
import argparse

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chapter', choices=('2', '3'))
args = parser.parse_args()
src = (BASE/f'chapter{args.chapter}-supervisor-draft.tex').read_text()
src = src.replace('\\input{theme}', '\\input{theme}\n\\newcommand{\\speaker}[1]{\\note{#1}}')
src = src.replace('\\input{data/', '\\input{'+str(ROOT/'thesis/generated')+'/')
src = src.replace('\\input{theme}', '\\renewcommand{\\TalkShort}{Draft layout; final review pending}\n\\input{theme}')
fig = r'\renewcommand{\fig}[2][54mm]{\IfFileExists{'+str(BASE/'draft-layout')+r'/#2}{\includegraphics[width=\linewidth,height=#1,keepaspectratio]{'+str(BASE/'draft-layout')+r'/#2}}{\IfFileExists{'+str(ROOT/'thesis/generated')+r'/#2}{\includegraphics[width=\linewidth,height=#1,keepaspectratio]{'+str(ROOT/'thesis/generated')+r'/#2}}{\IfFileExists{assets/#2}{\includegraphics[width=\linewidth,height=#1,keepaspectratio]{assets/#2}}{\fbox{\parbox[c][#1][c]{.9\linewidth}{\centering Layout placeholder; final full-run panel pending\par\detokenize{#2}}}}}}\par}'
src = src.replace('\\begin{document}', fig+'\n\\begin{document}')
(BASE/f'draft-layout/chapter{args.chapter}-full-draft.tex').write_text(src)
