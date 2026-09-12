"""Render readable supervisor panels from completed full-archive report arrays.

No
trajectory reads, fitted parameters, resampling or changed numerical estimators.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np

NAMES = {'paragliders': 'Paragliders', 'hang gliders': 'Hang gliders'}
TAGS = {'paragliders': 'para', 'hang gliders': 'hang'}
VARIABLES = (r'$|X_E|$', r'$|X_N|$', r'$R$')
COORDINATES = ('east', 'north', 'radial')
RANKS = (0.25, 0.50, 0.75, 0.90)
RANK_COLORS = ('#482878', '#31688E', '#26828E', '#35A779')
COMPONENT_COLORS = ('#2E7D8A', '#A9629E', '#4A4A4A')
LAG_COLORS = ('#440154', '#414487', '#2A788E', '#22A884', '#7AD151', '#AD9D00')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def axes(ncols=2):
    fig, axs = plt.subplots(1, ncols, figsize=(7.6 if ncols==2 else 10.0, 3.05), layout='constrained')
    for ax in axs:
        ax.spines[['top', 'right']].set_visible(False)
        ax.tick_params(direction='out')
    return fig, axs


def render(data, out):
    paths = [data / n for n in ('ch3_revision.json.gz', 'ch3_self_similarity.json.gz')]
    overview, scaling = [json.loads(gzip.decompress(p.read_bytes())) for p in paths]
    if overview['measurement_contract']['scope'] != 'full eligible archive':
        raise ValueError('Full-archive results are required for the supervisor deck')
    if scaling['identity']['source_contract'] != overview['measurement_contract']:
        raise ValueError('The two reports refer to different measurement contracts')
    results = scaling['results']
    if set(results) != set(NAMES):
        raise ValueError('Both disciplines are required')
    for name, result in results.items():
        if result['n_flights'] != overview['results'][name]['n_fixed']:
            raise ValueError('Fixed-cohort counts disagree')
        if len(result['joint']['laws']) != 6:
            raise ValueError('The complete six-lag joint diagnostic is required')
    out.mkdir(parents=True, exist_ok=True)
    outputs = {}
    plt.rcParams.update({
        'font.family': 'serif', 'font.serif': ['STIXGeneral'],
        'mathtext.fontset': 'stix', 'font.size': 13, 'axes.labelsize': 14,
        'axes.titlesize': 13, 'legend.fontsize': 10, 'lines.linewidth': 1.7,
        'pdf.fonttype': 42,
    })

    def save(fig, name):
        path = out / (name + '.pdf')
        fig.savefig(path, bbox_inches='tight', pad_inches=.04,
                    metadata={'CreationDate': None, 'Creator': 'soaring supervisor panels'})
        plt.close(fig)
        outputs[path.name] = digest(path)

    fig, axs = axes()
    controls = ('Changing pool', 'Fixed flights; pooled origins',
                'Equal flight weights', 'Same weights and origins')
    control_colors = ('#8C8C8C', '#2E7D8A', '#A9629E', '#4E8A5B')
    for ax, (name, result) in zip(axs, overview['results'].items(), strict=True):
        h = np.asarray(result['quantile_control']['exponents'])[:, 2, :]
        for values, label, color in zip(h, controls, control_colors, strict=True):
            ax.plot(np.arange(4), values, 'o-', label=label, color=color, ms=4)
        ax.set(title=NAMES[name], xticks=np.arange(4),
               xticklabels=['25th','50th','75th','90th'],
               xlabel='Radial quantile rank', ylabel='Fitted exponent')
    handles, labels = axs[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='outside lower center', ncol=2, frameon=False,
               fontsize=10)
    save(fig, 'supervisor-population-controls')

    fit_keys = ('full', 'intermediate', 'late_intermediate')
    fit_labels = []
    for key in fit_keys:
        lags = next(iter(results.values()))['fits'][key]['lags_s']
        fit_labels.append(f'{lags[0]:g}–{lags[-1]:g} s')
    fig, axs = axes()
    for ax, (name, result) in zip(axs, results.items(), strict=True):
        for k, color in enumerate(COMPONENT_COLORS):
            x = np.arange(3)+(k-1)*.16
            estimates = [result['fits'][key]['common_h'][k] for key in fit_keys]
            bounds = np.array([result['fits'][key]['common_h_ci95'] for key in fit_keys])
            ax.vlines(x, bounds[:, 0, k], bounds[:, 1, k], color=color)
            ax.plot(x, estimates, 'o', color=color, label=VARIABLES[k], ms=4)
        ax.set(title=NAMES[name], xticks=np.arange(3), xticklabels=fit_labels,
               xlabel='Actual fitted lag interval', ylabel='Common slope across ranks')
        ax.tick_params(axis='x', labelsize=10)
        ax.legend(ncol=3, frameon=False, fontsize=10)
    save(fig, 'supervisor-range-sensitivity')

    for name, result in results.items():
        fig, axs = axes()
        for k, color in enumerate(COMPONENT_COLORS):
            x = np.arange(3)+(k-1)*.16
            contrasts = [result['fits'][key]['contrasts']['p90_minus_p25'] for key in fit_keys]
            estimates = [row['estimate'][k] for row in contrasts]
            bounds = np.array([row['ci95'] for row in contrasts])
            axs[0].vlines(x, bounds[:, 0, k], bounds[:, 1, k], color=color)
            axs[0].plot(x, estimates, 'o', color=color, label=VARIABLES[k], ms=4)
        axs[0].set(title='Paired rank contrast', xticks=np.arange(3),
                   xticklabels=fit_labels, xlabel='Actual fitted lag interval',
                   ylabel=r'$H_{0.90}-H_{0.25}$')
        axs[0].tick_params(axis='x', labelsize=10)
        axs[0].legend(ncol=3, frameon=False, fontsize=10)
        c = result['fits']['full']['contrasts']['north_minus_east']
        axs[1].vlines(np.arange(4), c['ci95'][0], c['ci95'][1], color='#A9629E')
        axs[1].plot(np.arange(4), c['estimate'], 'o', color='#A9629E', ms=4)
        axs[1].set(title='Paired directional contrast; full range',
                   xticks=np.arange(4), xticklabels=['25th','50th','75th','90th'],
                   xlabel='Quantile rank', ylabel=r'$H_N-H_E$')
        for ax in axs:
            ax.axhline(0, color='.5', linestyle='--', linewidth=.7)
        save(fig, f'supervisor-contrasts-{TAGS[name]}')

    # One coordinate per slide, with the two disciplines side by side.
    for k, coordinate in enumerate(COORDINATES):
        fig, axs = axes()
        for ax, (name, result) in zip(axs, results.items(), strict=True):
            q = np.asarray(result['quantiles_m'])
            for j, (rank, color) in enumerate(zip(RANKS, RANK_COLORS, strict=True)):
                ax.loglog(result['lags_s'], q[:, k, j], color=color, label=f'p={rank:g}')
            ax.set(title=f"{NAMES[name]}; N={result['n_flights']:,}",
                   xlabel=r'Lag $\tau$ [s]', ylabel=f'{VARIABLES[k]} quantile [m]')
            ax.legend(ncol=2, loc='upper left', frameon=False)
        save(fig, f'supervisor-quantiles-{coordinate}')

    # Keep the exact saved percentile endpoints, without refitting the curves.
    for name, result in results.items():
        fig, ax = plt.subplots(figsize=(6.8, 3.0), layout='constrained')
        fit = result['fits']['full']
        h = np.asarray(fit['h'])
        ci = np.asarray(fit['h_ci95'])
        for k, color in enumerate(COMPONENT_COLORS):
            x = np.arange(4) + (k-1)*.15
            ax.vlines(x, ci[0, k], ci[1, k], color=color, linewidth=1.8)
            ax.plot(x, h[k], 'o', color=color, label=VARIABLES[k], ms=5)
        ax.set(xticks=np.arange(4), xticklabels=['25th', '50th', '75th', '90th'],
               xlabel='Quantile rank', ylabel='Fitted exponent', title=NAMES[name])
        ax.spines[['top', 'right']].set_visible(False)
        ax.legend(ncol=3, frameon=False)
        save(fig, f'supervisor-exponents-{TAGS[name]}')

    for name, result in results.items():
        tag = TAGS[name]
        tau = np.asarray(result['lags_s'])
        selected = result['display_lag_indexes']
        q = np.asarray(result['quantiles_m'])
        dense = np.asarray(result['dense_quantiles_m'])
        for k, coordinate in enumerate(COORDINATES):
            law = result['laws'][k]
            edges = np.asarray(law['edges_m'])
            centers = np.sqrt(edges[:-1]*edges[1:])
            fig, axs = axes(3)
            exponent = result['fits']['full']['common_h'][k]
            for i, j in enumerate(selected):
                mass = np.asarray(law['mass'][i])
                density = np.where(mass > 0, mass/np.diff(edges), np.nan)
                scale = (tau[j]/1000.0)**exponent
                color = LAG_COLORS[i]
                axs[0].loglog(centers, density, color=color,
                              label=f'{tau[j]:g} s')
                axs[1].loglog(centers/scale, scale*density, color=color)
                axs[2].semilogx(dense[j, k]/q[j, k, 1], result['dense_probabilities'],
                               color=color)
            axs[0].set(title=f'Recorded {VARIABLES[k]}',xlabel='Displacement [m]',ylabel='Density')
            axs[1].set(title=f'Power rescaling; H={exponent:.3f}',
                       xlabel=r'$y/[\tau/(1000\,\mathrm{s})]^H$ [m]', ylabel='Rescaled density')
            axs[2].set(title='Median normalization', xlabel=r'$y/Q_{0.50}(\tau)$',
                       ylabel='Quantile rank', ylim=(0, 1))
            handles,labels=axs[0].get_legend_handles_labels()
            fig.legend(handles,labels,loc='outside lower center',ncol=6,frameon=False,fontsize=12)
            maximum_zero=100*max(law['zero_mass'])
            if maximum_zero>0:
                fig.suptitle(f'Zero mass up to {maximum_zero:.2g}% (included in empirical-CDF distances)',fontsize=12)
            save(fig, f'supervisor-collapse-{tag}-{coordinate}')

        joint = result['joint']
        maximum = max(np.max(law['mass']) for law in joint['laws'])
        norm = LogNorm(vmin=max(1e-6, maximum*1e-4), vmax=maximum)
        # All six original lags, two per slide, with one shared discipline scale.
        for pair in range(3):
            fig, axs = axes()
            for ax, law in zip(axs, joint['laws'][pair*2:pair*2+2], strict=True):
                mass = np.asarray(law['mass'])
                im = ax.pcolormesh(joint['interior_edges'], joint['interior_edges'],
                                  mass[1:-1, 1:-1].T, norm=norm, cmap='viridis',
                                  rasterized=True)
                ax.set(title=f"{law['lag_s']} s; outside {100*law['tail_mass']:.1f}%",
                       xlabel=r'Rescaled $X_E$', ylabel=r'Rescaled $X_N$', aspect='equal')
            fig.colorbar(im, ax=axs, label='Probability per cell', shrink=.85)
            save(fig, f'supervisor-joint-{tag}-{pair+1}')

    theta = np.linspace(0, 2*np.pi, 241)
    circle = np.array([np.cos(theta), np.sin(theta)])
    for region, tag in [('Alps', 'alps'), ('Pyrenees', 'pyrenees'), ('Channel Coast', 'coast')]:
        rows = [r for r in overview['results']['paragliders']['pca'] if r['region'] == region]
        fig, axs = axes()
        for row, color in zip(rows, LAG_COLORS, strict=False):
            covariance = np.asarray(row['covariance'])
            eigenvalues, eigenvectors = np.linalg.eigh(covariance/np.trace(covariance))
            ellipse = eigenvectors @ np.diag(np.sqrt(eigenvalues)) @ circle
            axs[0].plot(*ellipse, color=color, label=f"{row['lag_s']} s; N={row['n_flights']:,}")
            axs[1].plot(row['lag_s'], row['ratio'], 'o', color=color)
            axs[1].annotate(f"{row['angle_deg']:.0f}°", (row['lag_s'], row['ratio']),
                            xytext=(0, 9), textcoords='offset points', ha='center', fontsize=11)
        axs[0].set(xlim=(-1.05, 1.05), ylim=(-1.05, 1.05), aspect='equal',
                   xlabel='East / centred RMS radius', ylabel='North / centred RMS radius')
        axs[0].axhline(0, color='.8', lw=.6); axs[0].axvline(0, color='.8', lw=.6)
        axs[1].semilogx([r['lag_s'] for r in rows], [r['ratio'] for r in rows], color='.55', zorder=0)
        axs[1].set(xlabel=r'Lag $\tau$ [s]', ylabel=r'$\lambda_1/\lambda_2$',
                   ylim=(1, max(r['ratio'] for r in rows)*1.3), xlim=(6, 17000))
        axs[0].legend(frameon=False, fontsize=8, loc='lower left')
        save(fig, f'supervisor-pca-{tag}')

    manifest = {
        'operation': 'Redraw saved full-report arrays; no trajectory reads, new fits or resampling',
        'inputs': {p.name: digest(p) for p in paths},
        'script_sha256': digest(Path(__file__)), 'outputs': outputs,
        'notes': [
            'Joint plots keep all six lags, original bins, overflow accounting and shared discipline colour scale.',
            'Median-normalized displays use recorded 1st--99th quantile ranks, not an interpolated claim about the tails.',
            'Logarithmic marginal panels show positive values; any point mass at zero is reported separately. Median panels show all positive recorded dense quantiles instead of fixing x limits at 0.01--10.',
            'PCA panels display all four reported lags; only three ellipses were drawn in the original multi-panel figure.',
            'Confidence segments use the exact saved percentile endpoints; they are not simultaneous intervals.',
        ],
    }
    (out.parent/'supervisor-panel-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(f'Rendered {len(outputs)} supervisor panels')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=Path(__file__).resolve().parent/'data')
    parser.add_argument('--out', type=Path, default=Path(__file__).resolve().parent/'assets')
    args = parser.parse_args()
    render(args.data, args.out)
