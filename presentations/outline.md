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
| 8 | Second differences measure changes of interval-mean velocity |
| 9 | Why a slope near two need not identify a Hurst exponent |
| 10 | Finite persistence can produce a crossover without nonstationarity |
| 11 | Third differences also cancel a constant acceleration |
| 12 | Open and closed tasks change the growth of displacements |
| 13 | A circle retains its geometry after second differencing |
| 14 | Observed-path closure needs special care for segmented flights |

**Quantiles and population control**

| Page | Topic |
|---:|---|
| 15 | Scalar vector scaling also constrains east and north |
| 16 | A single displacement scale predicts equal quantile slopes |
| 17 | From displacement windows to one quantile at each lag |
| 18 | Each fitted $H_{j,p}$ is the slope of one log--log quantile curve |
| 19 | Archive quantile curves are the input to the fits |
| 20 | Each point here summarises a separate quantile fit |
| 21 | The archive quantile ratio also reveals changes with lag |
| 22 | The full archive and the fixed cohort answer different questions |
| 23 | The fixed control requires common temporal support |
| 24 | Holding flights fixed does not by itself hold the observations fixed |
| 25 | Membership, flight weights and common origins change the comparison |
| 26 | Relative spread changes, but the change is not monotone |
| 27 | All quantiles can grow while spread relative to the median narrows |
| 28 | Unequal rank exponents can encode that changing shape |

**Vector scaling and dependence**

| Page | Topic |
|---:|---|
| 29 | Anisotropy does not prevent a common scalar rescaling |
| 30 | East, north and radius together still do not identify the joint law |
| 31 | Fixed-population quantiles: east component |
| 32 | Fixed-population quantiles: north component |
| 33 | Fixed-population quantiles: radial displacement |
| 34 | Whole-flight bootstrap preserves pairing across ranks, axes and lags |
| 35 | Paragliders: component and radial exponent estimates |
| 36 | Paragliders: paired rank and directional contrasts |
| 37 | Hang gliders: component and radial exponent estimates |
| 38 | Hang gliders: paired rank and directional contrasts |
| 39 | The collapse exponent shares one slope across four quantile ranks |
| 40 | A common fitted scale depends on the fitted interval |
| 41 | A large density near zero need not carry much probability |
| 42 | Paragliders: marginal collapse for east |
| 43 | Paragliders: marginal collapse for north |
| 44 | Paragliders: marginal collapse for radius |
| 45 | Hang gliders: marginal collapse for east |
| 46 | Hang gliders: marginal collapse for north |
| 47 | Hang gliders: marginal collapse for radius |
| 48 | The joint comparison keeps geographic axes and one scalar scale |
| 49 | Paragliders: signed joint laws (1/3) |
| 50 | Paragliders: signed joint laws (2/3) |
| 51 | Paragliders: signed joint laws (3/3) |
| 52 | Hang gliders: signed joint laws (1/3) |
| 53 | Hang gliders: signed joint laws (2/3) |
| 54 | Hang gliders: signed joint laws (3/3) |
| 55 | One scalar rescaling leaves changes in the signed joint law |
| 56 | One-lag vector laws leave multi-time questions open |

**Time-averaged transport by region and initial altitude**

| Page | Topic |
|---:|---|
| 57 | Compare transport magnitude before its directional structure |
| 58 | Regional TA-MSD: coastal flights travel farther at intermediate lags |
| 59 | Fixing the population changes the apparent long-lag growth |
| 60 | Regional support limits what the fixed control can establish |
| 61 | Initial-altitude groups combine transport and regional composition |
| 62 | The late rise in Plains and Hills is sensitive to population selection |
| 63 | The altitude-band comparison also needs its flight counts |
| 64 | Region and origin altitude are strongly associated in this sample |

**Directional structure and environment**

| Page | Topic |
|---:|---|
| 65 | Regional plots use different clocks, weights and centring |
| 66 | Equal east and north moments do not establish isotropy |
| 67 | Regional position moments differ along east and north |
| 68 | Regional velocity moments show a related directional contrast |
| 69 | Regional uncertainty bands do not match the groups |
| 70 | PCA describes preferred axes; wind needs independent information |
| 71 | Alps: centred principal axes across four lags |
| 72 | Pyrenees: centred principal axes across four lags |
| 73 | Channel Coast: centred principal axes across four lags |
| 74 | A terrain direction measured independently of the flights |
| 75 | Alps: shared sector, with an approximately 18-degree offset |
| 76 | Pyrenees: the long-lag spread follows the highland axis |
| 77 | Channel Coast: the reference height follows the PCA windows |
| 78 | ERA5 wind is interpolated to the measured flight altitude |
| 79 | At flight height, both annual references remain offset from PCA |
| 80 | Height and time checks preserve a broad orientation resemblance |
| 81 | What the environmental comparisons establish |
| 82 | Alps: velocity changes retain a directional structure |
| 83 | Pyrenees: the long-lag change coincides with falling support |
| 84 | Channel Coast: smaller changes at 1000 s, with residual anisotropy |
| 85 | Second-difference ellipses retain orientation after drift cancellation |
| 86 | The regional contrast persists in a common-context control |
| 87 | The ratio between orders changes with the lag |
| 88 | The distribution distinguishes frequent small changes from large events |
| 89 | Order-three support limits the long-lag regional comparison |
| 90 | Alps: C/D/CCC has smaller coordinate-moment imbalance |
| 91 | Pyrenees: the ordering of the two groups reverses |
| 92 | Channel Coast: the late position contrast is pronounced |
| 93 | Poitou-Charente: the group curves cross |
| 94 | Champagne-Lorraine: a late contrast does not keep C/D/CCC at unity |
| 95 | The environmental interpretation remains a hypothesis |
| 96 | Define the target before calling it resistance to wind |

**Duration and equipment composition**

| Page | Topic |
|---:|---|
| 97 | Long flights occur in both equipment groups |
| 98 | Duration and equipment on the common 10--1695 s interval |
| 99 | Fixing equipment proportions removes part of the duration contrast |

**Model comparisons and temporal memory**

| Page | Topic |
|---:|---|
| 100 | The moment spectrum challenges a specific L\'evy-walk benchmark |
| 101 | Non-Gaussian pooled increments can arise from Gaussian mixtures |
| 102 | Velocity memory remains visible after averaging over minutes |
| 103 | Signed correlations retain the long-lag negative values |
| 104 | Finite velocity persistence gives a ballistic-to-diffusive crossover |
| 105 | Which models are challenged, and which remain open? |
| 106 | Phase-conditioned moments must include windows crossing transitions |
| 107 | Three decisions for this meeting |

**Linked representations and sources**

| Page | Topic |
|---:|---|
| 108 | Squared laws transform the same distributional evidence |
| 109 | Sources and the scope of the evidence |
| 110 | Joint laws and environmental interpretation: additional sources |
