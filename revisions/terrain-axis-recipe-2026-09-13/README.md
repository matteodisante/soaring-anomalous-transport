# Terrain-axis numerical recipe

The independent ETOPO terrain-axis method is now stated as a seven-step recipe
in Chapter 3: crop the two regional boxes, thin the 15-arc-second grid to one arc
minute, apply the binary elevation threshold, project cell centres to local WGS84
east/north coordinates, apply cosine-latitude area weights, compute the spatial
covariance, and retain its leading eigenvector.

The manuscript then gives the weighted centre and covariance formula, defines the
angle convention, and separates what the construction measures from what it does
not measure. A float barrier prevents an earlier PCA figure from interrupting the
numbered recipe. The final recipe and formula appear together on thesis page 80
(PDF page 84).

All numerical products, ETOPO inputs, thresholds, axes and comparisons are
unchanged. `manuscript-review.json` records the completed 138-page build and its
unchanged numerical parent.
