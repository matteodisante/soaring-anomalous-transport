"""Preview vector panel crops while the numerical recovery is running.

Reads only completed Chapter 2 and regional products; preserves curves, bands and
their original axis labels. These previews are not final presentation assets.
"""
from pathlib import Path
import hashlib
import json

from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import RectangleObject

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / 'draft-layout'
PANELS = {
    'msd-growth': ('msd', (0, 0, 1, .525), None),
    'msd-support': ('msd', (0, .525, 1, 1), None),
    'retained-duration-path': ('prelim_ensemble', (0, 0, 1, .5), None),
    'retained-cadence': ('prelim_ensemble', (0, .5, 1, 1), None),
    'seasons-counts': ('dataset_seasons', (0, 0, 1, .303), (.89, 1)),
    'seasons-retention': ('dataset_seasons', (0, .305, 1, .60), (.89, 1)),
    'seasons-duration': ('dataset_seasons', (0, .603, 1, 1), None),
    'closed-loop-variations': ('closed_loop_schematic', (0, .427, 1, 1), None),
    'quantile-example-laws': ('quantile_scaling_schematic', (0, 0, 1, .5), None),
    'quantile-example-slopes': ('quantile_scaling_schematic', (0, .5, 1, 1), None),
    'altitude-psd-panel': ('altitude_noise', (0, .495, .495, 1), None),
    'altitude-traces': ('altitude_noise', (0, 0, 1, .49), None),
    'altitude-availability': ('altitude_noise', (.50, .495, 1, 1), None),
    'equipment-alps-both': ('kinematic_isotropy_terrain_level', (0, 0, 1, .315), (.949, 1)),
    'equipment-pyrenees-both': ('kinematic_isotropy_terrain_level', (0, .318, 1, .634), (.949, 1)),
    'equipment-coast-both': ('kinematic_isotropy_terrain_level', (0, .636, 1, 1), None),
    'equipment-poitou-both': ('kinematic_isotropy_flat_level', (0, .318, 1, .634), (.949, 1)),
    'equipment-champagne-both': ('kinematic_isotropy_flat_level', (0, .636, 1, 1), None),
}



def crop(source, target, bounds, axis):
    page = PdfReader(source).pages[0]
    width, height = float(page.mediabox.width), float(page.mediabox.height)
    left, top, right, bottom = bounds
    box = RectangleObject((width*left, height*(1-bottom), width*right, height*(1-top)))
    page.cropbox = box
    writer = PdfWriter()
    strip_h = 0 if axis is None else height*(axis[1]-axis[0])
    output = writer.add_blank_page(width=width*(right-left), height=height*(bottom-top)+strip_h)
    output.merge_transformed_page(page, Transformation().translate(-width*left, -height*(1-bottom)+strip_h))
    if axis is not None:
        strip = PdfReader(source).pages[0]
        strip.cropbox = RectangleObject((width*left, height*(1-axis[1]), width*right, height*(1-axis[0])))
        output.merge_transformed_page(strip, Transformation().translate(-width*left, -height*(1-axis[1])))
    writer.write(target)


if __name__ == '__main__':
    OUT.mkdir(exist_ok=True)
    records = {}
    for name, (original, bounds, strip) in PANELS.items():
        source = ROOT / 'thesis/generated' / (original+'.pdf')
        target = OUT / (name+'.pdf')
        crop(source, target, bounds, strip)
        records[name] = {'source': str(source.relative_to(ROOT)),
                         'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                         'bounds': bounds, 'appended_original_axis_strip': strip,
                         'output_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    (OUT/'panel-preview-manifest.json').write_text(json.dumps(records, indent=2)+'\n')
    print(f'Prepared {len(records)} vector panel previews; visual review required.')
