# Thermal planes: four captures for slide 11

Save four PNG images here:

| File | Region/cell | Height |
| --- | --- | --- |
| `mountain-low.png` | Selected mountain cell | Lower plane |
| `mountain-high.png` | The same mountain cell | Higher plane |
| `plains-low.png` | Selected plains cell | Lower plane |
| `plains-high.png` | The same plains cell | Higher plane |

Use **Thermal planes → View → Horizontal plane only**, then **Full screen**.
Capture the map square rather than the full interface so the point pattern stays
legible. Preserve the same map extent, axes, background and point style within each
pair. Keep dates and segmentation unchanged when moving the height slider.
Use the same two heights for both cells where their supported ranges allow it.
Record the cells, dates, segmentation, reference altitude and contributing flight
counts, and retain relevant map attribution.

Replace `ThermalLower` and `ThermalUpper` in `offsite-2026.tex` with the selected
values, for example `200\,\mathrm{m}` and `600\,\mathrm{m}`. These numbers are
examples, not preselected measurement heights. Rebuild with:

```bash
python3 presentations/offsite2026/build.py
```

The two map pairs support a qualitative comparison of horizontal patterns across
height. The viewer plots climb crossings, not unique thermal centres. Its AGL
reference is a fixed launch-altitude median for each cell, not a local terrain
height at each map position. Similarity across planes does not establish
stationarity in time; pooled dates and changing flight support also affect the
appearance of the clouds.
