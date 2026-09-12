# Chapter decks and discussion map

The decks follow the reviewed manuscript and have no prescribed duration. Page numbers include the title page.

## Chapter 2

| Page | Topic |
|---:|---|
| 1 | Title |

**Archive, records and population**

| Page | Topic |
|---:|---|
| 2 | The archive contains recorded cross-country flights |
| 3 | Acquisition preserves the declarations and their recorded tracks |
| 4 | An IGC fix contains two altitude fields and a validity declaration |
| 5 | Equipment classes and scoring labels describe different things |

**Processing contract and altitude evidence**

| Page | Topic |
|---:|---|
| 6 | The processing order determines what each cut acts on |
| 7 | GNSS supplies altitude; pressure has a separate witness role |
| 8 | Recorded altitude traces combine flight motion and channel behaviour |
| 9 | The paired PSD comparison uses raw valid intervals |
| 10 | Similar typical PSD floors can conceal different upper tails |
| 11 | GNSS availability is a separate flight-level selection |
| 12 | A common altitude channel does not resolve its vertical datum |

**Fix-level decisions**

| Page | Topic |
|---:|---|
| 13 | Timestamp and coordinate bookkeeping precede geometric decisions |
| 14 | A Hampel flag describes a departure; the reach/rejoin rule removes it |
| 15 | The identifier's scale is a convention, not a false-alarm probability |
| 16 | An isolated unreachable fix has an immediate reachable rejoin |
| 17 | A moderate offset can become reachable within the block horizon |
| 18 | Without a reachable rejoin, the scan imposes a boundary |
| 19 | A frozen-position candidate is removed and split |
| 20 | The complete frozen-position witness |
| 21 | The vertical-speed threshold is 10 m/s |
| 22 | Two window medians determine one altitude decision |
| 23 | Altitude invalidation precedes the full-trajectory support decision |
| 24 | An isolated altitude spike can leave a populated-window median low |
| 25 | Sustained excess raises both neighbouring window statistics |
| 26 | An unreturned altitude step remains an unresolved case |

**Trimming and flight selection**

| Page | Topic |
|---:|---|
| 27 | Outer trimming uses a sustained horizontal-speed criterion |
| 28 | Time removed before onset and after landing has a long tail |
| 29 | Interior ground intervals require joint speed and barometric evidence |
| 30 | Interior excisions affect a small part of the full trimming census |
| 31 | Flight-level gates define the study population |

**Coordinates and supported segments**

| Page | Topic |
|---:|---|
| 32 | Convert geographic coordinates before measuring horizontal motion |
| 33 | The local basis uses the origin's geodetic coordinates |
| 34 | Rotated Up and the recorded altitude are different coordinates |
| 35 | Recorder cadence varies across the raw archive |
| 36 | The same duration bound governs horizontal and vertical support |
| 37 | Long altitude holes split the full trajectory |
| 38 | A segment boundary preserves the flight clock and coordinate origin |
| 39 | Segment acceptance requires duration and complete local support |
| 40 | Quality flags describe support; every retained coordinate is smoothed |

**Smoothing and differentiation**

| Page | Topic |
|---:|---|
| 41 | One local polynomial estimates position and derivatives |
| 42 | The nominal 5-s timescale does not mean a 5-s window for every logger |
| 43 | The value filter changes the contribution of position noise |
| 44 | Smoothing modifies the measured displacement variance |

**Retained archive and checks**

| Page | Topic |
|---:|---|
| 45 | The complete first-failure census |
| 46 | Elapsed record span and observed path use different gap conventions |
| 47 | Retained cadences define the available temporal resolution |
| 48 | Participation and available tracks change across seasons |
| 49 | Similar aggregate retention can conceal different selection |
| 50 | The duration of retained records also changes with season |
| 51 | Geographic coverage is part of the sampling problem |
| 52 | La R\'eunion and other sites broaden the observed population |
| 53 | Logged starting altitude does not measure local terrain relief |
| 54 | What has been checked, and what still needs empirical validation? |
| 55 | Inspect one of the records together |
| 56 | Which cleaning uncertainties should we resolve first? |
| 57 | Transport plots must retain explicit support and populations |
| 58 | Methods and provenance |

## Chapter 3

| Page | Topic |
|---:|---|
| 1 | Title |

**Displacement, support and growth**

| Page | Topic |
|---:|---|
| 2 | What motion should a stochastic model reproduce? |
| 3 | Launch, segment and flight averages use different weights |
| 4 | Launch averages and time averages use different populations |
| 5 | Local slopes must be read together with falling support |
| 6 | The MSD grows faster than linearly on the measured interval |
| 7 | Constant velocity cancels; an intrinsic $H$ remains open |
| 8 | Open and closed tasks change the growth of displacements |
| 9 | A circle retains its geometry after second differencing |
| 10 | Observed-path closure needs special care for segmented flights |

**Quantiles and population control**

| Page | Topic |
|---:|---|
| 11 | A single displacement scale predicts equal quantile slopes |
| 12 | The full archive and the fixed cohort answer different questions |
| 13 | The fixed control requires common temporal support |
| 14 | Holding flights fixed does not by itself hold the observations fixed |
| 15 | Membership, flight weights and common origins change the comparison |
| 16 | Relative spread changes, but the change is not monotone |
| 17 | All quantiles can grow while spread relative to the median narrows |
| 18 | Unequal rank exponents can encode that changing shape |

**Vector scaling and dependence**

| Page | Topic |
|---:|---|
| 19 | Anisotropy does not prevent a common scalar rescaling |
| 20 | East, north and radius together still do not identify the joint law |
| 21 | Fixed-population quantiles: east component |
| 22 | Fixed-population quantiles: north component |
| 23 | Fixed-population quantiles: radial displacement |
| 24 | Whole-flight bootstrap preserves pairing across ranks, axes and lags |
| 25 | Paragliders: component and radial exponent estimates |
| 26 | Paragliders: paired rank and directional contrasts |
| 27 | Hang gliders: component and radial exponent estimates |
| 28 | Hang gliders: paired rank and directional contrasts |
| 29 | A common fitted scale depends on the fitted interval |
| 30 | A large density near zero need not carry much probability |
| 31 | Paragliders: marginal collapse for east |
| 32 | Paragliders: marginal collapse for north |
| 33 | Paragliders: marginal collapse for radius |
| 34 | Hang gliders: marginal collapse for east |
| 35 | Hang gliders: marginal collapse for north |
| 36 | Hang gliders: marginal collapse for radius |
| 37 | The joint comparison keeps geographic axes and one scalar scale |
| 38 | Paragliders: signed joint laws (1/3) |
| 39 | Paragliders: signed joint laws (2/3) |
| 40 | Paragliders: signed joint laws (3/3) |
| 41 | Hang gliders: signed joint laws (1/3) |
| 42 | Hang gliders: signed joint laws (2/3) |
| 43 | Hang gliders: signed joint laws (3/3) |
| 44 | One scalar rescaling leaves changes in the signed joint law |
| 45 | One-lag vector laws leave multi-time questions open |

**Directional structure and environment**

| Page | Topic |
|---:|---|
| 46 | Regional plots use different clocks, weights and centring |
| 47 | Equal east and north moments do not establish isotropy |
| 48 | Regional position moments differ along east and north |
| 49 | Regional velocity moments show a related directional contrast |
| 50 | Regional uncertainty bands do not match the groups |
| 51 | PCA describes preferred axes; wind needs independent information |
| 52 | Alps: centred principal axes across four lags |
| 53 | Pyrenees: centred principal axes across four lags |
| 54 | Channel Coast: centred principal axes across four lags |
| 55 | Alps: C/D/CCC has smaller coordinate-moment imbalance |
| 56 | Pyrenees: the ordering of the two groups reverses |
| 57 | Channel Coast: the late position contrast is pronounced |
| 58 | Poitou-Charente: the group curves cross |
| 59 | Champagne-Lorraine: a late contrast does not keep C/D/CCC at unity |
| 60 | The environmental interpretation remains a hypothesis |
| 61 | Define the target before calling it resistance to wind |

**Duration and equipment composition**

| Page | Topic |
|---:|---|
| 62 | Long flights occur in both equipment groups |
| 63 | Duration and equipment on the common 10--1695 s interval |
| 64 | Fixing equipment proportions removes part of the duration contrast |

**Model comparisons and temporal memory**

| Page | Topic |
|---:|---|
| 65 | The moment spectrum challenges a specific L\'evy-walk benchmark |
| 66 | Non-Gaussian pooled increments can arise from Gaussian mixtures |
| 67 | Velocity memory remains visible after averaging over minutes |
| 68 | Signed correlations retain the long-lag negative values |
| 69 | Finite velocity persistence gives a ballistic-to-diffusive crossover |
| 70 | Which models are challenged, and which remain open? |
| 71 | Phase-conditioned moments must include windows crossing transitions |
| 72 | Three decisions for this meeting |

**Linked representations and sources**

| Page | Topic |
|---:|---|
| 73 | Squared laws transform the same distributional evidence |
| 74 | Sources and the scope of the evidence |
| 75 | Joint laws and environmental interpretation: additional sources |
