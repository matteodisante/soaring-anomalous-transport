"""Verbatim transcription of Vilpellet's ``flight_phase_inference_minimal.py``.

This file exists for one purpose: to prove that
:mod:`soaring.analysis.segmentation.vilpellet` computes what the author's own code
computes. It is a copy of the reference implementation with the ``numba`` decorator
removed, because the decorator changes nothing about the arithmetic and this repository
does not depend on numba.

DO NOT TIDY THIS FILE. Do not rename its variables, do not vectorise its loops, do not
fix its unused arguments, and do not correct the transposed ``regime_map`` of the
original. Every oddity here is deliberate: the moment this stops being a faithful copy,
the equivalence test stops proving anything. The port is where readable code belongs.

The one thing this copy leaves out is the module-level ``get_regime`` call on the
author's own Windows path, which would run at import time.
"""

# ruff: noqa
import numpy as np
import pandas as pd


class HMM:
    def __init__(self, nb_states):
        self.nb_states = nb_states
        self.x_values = np.array([[i, j, k] for i in range(2) for j in range(2) for k in range(2)])

    def emission_prob_vec(self, x, p1, p2, p3):
        indices = (x[:, None, :] == self.x_values[None, :, :]).all(axis=2).argmax(axis=1)
        return np.column_stack((self.p1[indices], self.p2[indices], self.p3[indices]))

    def predict_states_viterbi(self, obs):
        K = len(obs)
        emission_probs = self.emission_prob_vec(obs, self.p1, self.p2, self.p3)
        delta = np.zeros((K, self.nb_states))
        psi = np.zeros((K, self.nb_states), dtype=np.int64)
        states = np.zeros(K, dtype=np.int64)
        return self._viterbi(K, self.nb_states, self.nu, self.A, emission_probs, delta, psi, states)

    @staticmethod
    def _viterbi(K, nb_states, nu, A, emission_probs, delta, psi, states):
        for j in range(nb_states):
            delta[0, j] = nu[j] * emission_probs[0, j]
            psi[0, j] = 0
        for k in range(1, K):
            for j in range(nb_states):
                best_prev = 0
                best_val = delta[k-1, 0] * A[0, j]
                for i in range(1, nb_states):
                    val = delta[k-1, i] * A[i, j]
                    if val > best_val:
                        best_val = val
                        best_prev = i
                psi[k, j] = best_prev
                delta[k, j] = best_val * emission_probs[k, j]
            norm = 0.0
            for j in range(nb_states):
                norm += delta[k, j]
            for j in range(nb_states):
                delta[k, j] /= norm
        last = 0
        best_final = delta[K-1, 0]
        for j in range(1, nb_states):
            if delta[K-1, j] > best_final:
                best_final = delta[K-1, j]
                last = j
        states[K-1] = last
        for k in range(K-2, -1, -1):
            states[k] = psi[k+1, states[k+1]]
        return states


class FactoryDataHMM:
    def get_data_hmm(self, raw_data, window_smooth_data=6, alpha_straight_rad=0.2, window_persitence=90, beta_persistence=0.9):
        df = raw_data.copy()
        df = self.add_time_column(df)
        df = self.get_cartesian_coordinates(df, window_smooth_data)
        obs = self.get_features(df, window_smooth_data=window_smooth_data, window_persitence=window_persitence,
                                alpha_straight_rad=alpha_straight_rad, beta_persistence=beta_persistence)
        self.data = df
        return obs

    def get_cartesian_coordinates(self, df, window_smooth_data):
        df[["x", "y", "z"]] = self.geo_to_cart(lat=df["Lat"].to_numpy(), long=df["Long"].to_numpy(), alt=df["AltGNSS"].to_numpy())
        df["x"] = self.smooth_raw_data(df["x"], window_smooth_data)
        df["y"] = self.smooth_raw_data(df["y"], window_smooth_data)
        df["z"] = self.smooth_raw_data(df["z"], window_smooth_data)
        return df

    def get_features(self, df, window_smooth_data, window_persitence, alpha_straight_rad, beta_persistence):
        x_pre, x_now, x_post = df["x"].shift(1).to_numpy(), df["x"].to_numpy(), df["x"].shift(-1).to_numpy()
        y_pre, y_now, y_post = df["y"].shift(1).to_numpy(), df["y"].to_numpy(), df["y"].shift(-1).to_numpy()
        df["radius_curvature_lat_long_sgn"] = self.compute_signed_radius(x1=x_pre, x2=x_now, x3=x_post, y1=y_pre, y2=y_now, y3=y_post)
        df["radius_curvature_lat_long_sgn"] = df["radius_curvature_lat_long_sgn"].rolling(window=6, center=True, min_periods=1).mean()
        df['vertical_speed'] = (df['z'] - df['z'].shift(1))/(df['time'] - df['time'].shift(1))
        df["vertical_speed_mean"] = df["vertical_speed"].rolling(window=window_persitence, center=True, min_periods=1).mean()
        df["radius_straight_indic"] = np.where((df["radius_curvature_lat_long_sgn"] < alpha_straight_rad) &
                                               (df["radius_curvature_lat_long_sgn"] > -alpha_straight_rad), 1, 0)
        df["persistence_radius_straight_indic"] = np.where((df["radius_straight_indic"].rolling(window=window_persitence, center=True, min_periods=1).mean() > beta_persistence), 1, 0)
        df["persistence_vertical_speed_indic"] = np.where((df["vertical_speed_mean"] > 0), 1, 0)
        df["persistence_radius_sgn_indic"] = self.sliding_window_sign_check(column=df["radius_curvature_lat_long_sgn"], window_size=window_persitence, beta_persistence=beta_persistence)
        df = df.ffill()
        return df[["persistence_radius_straight_indic", "persistence_vertical_speed_indic", "persistence_radius_sgn_indic"]].values

    @staticmethod
    def add_time_column(df):
        df["time_diff"] = (df['time'] - df['time'].min())
        df["time_min_sec"] = (df['time_diff'] // 60).astype(int).astype(str) + ':' + (df['time_diff'] % 60).astype(int).astype(str)
        return df

    @staticmethod
    def smooth_raw_data(data, window_smooth_data):
        std = window_smooth_data/6
        return data.rolling(window=window_smooth_data, win_type='gaussian', center=True).mean(std=std)

    @staticmethod
    def geo_to_cart(lat, long, alt):
        a = 6378137.0
        f = 1 / 298.257223563
        e2 = f * (2 - f)
        phi = np.deg2rad(lat); lam = np.deg2rad(long)
        sinp = np.sin(phi); cosp = np.cos(phi)
        N = a / np.sqrt(1 - e2 * sinp**2)
        x = (N + alt) * cosp * np.cos(lam)
        y = (N + alt) * cosp * np.sin(lam)
        z = (N * (1 - e2) + alt) * sinp
        ecef = np.stack((x, y, z), axis=-1)
        ref_ecef = ecef[0]
        d = ecef - ref_ecef
        phi0 = np.deg2rad(lat[0]); lam0 = np.deg2rad(long[0])
        sp0, cp0 = np.sin(phi0), np.cos(phi0)
        sl0, cl0 = np.sin(lam0), np.cos(lam0)
        R = np.array([[-sl0, cl0, 0],
                      [-sp0*cl0, -sp0*sl0, cp0],
                      [cp0*cl0, cp0*sl0, sp0]])
        return d.dot(R.T)

    @staticmethod
    def compute_signed_radius(x1, x2, x3, y1, y2, y3):
        theta1 = np.arctan2(y2 - y1, x2 - x1)
        theta2 = np.arctan2(y3 - y2, x3 - x2)
        return (theta2 - theta1 + np.pi) % (2 * np.pi) - np.pi

    @staticmethod
    def sliding_window_sign_check(column, window_size, beta_persistence):
        half_window = window_size // 2
        column_padded = np.pad(column, (half_window, half_window), mode='reflect')
        shape = (column.size, window_size)
        strides = (column_padded.strides[0], column_padded.strides[0])
        windows = np.lib.stride_tricks.as_strided(column_padded, shape=shape, strides=strides)
        abs_windows = np.abs(windows)
        partition_indices = np.argpartition(-abs_windows, kth=half_window-1, axis=1)[:, :half_window]
        row_indices = np.arange(windows.shape[0])[:, None]
        selected_values = windows[row_indices, partition_indices]
        signs = np.sign(selected_values)
        positive_counts = np.sum(signs > 0, axis=1)
        negative_counts = np.sum(signs < 0, axis=1)
        max_counts = np.maximum(positive_counts, negative_counts)
        threshold = np.ceil(beta_persistence * half_window)
        return (max_counts >= threshold).astype(int)


def roll_majority(series, w):
    codes, uniques = pd.factorize(series, sort=True)
    s = pd.Series(codes, index=series.index)
    K = len(uniques); N = len(s)
    counts = np.empty((N, K), dtype=np.int32)
    vals = s.values
    for k in range(K):
        arr = (vals == k).astype(np.int8)
        counts[:, k] = pd.Series(arr, index=series.index).rolling(window=w, center=True, min_periods=1).sum().to_numpy()
    mode_idx = counts.argmax(axis=1)
    out = pd.Series(uniques[mode_idx], index=series.index)
    try:
        out = out.astype(series.dtype)
    except Exception:
        pass
    return out


factory_data_HMM = FactoryDataHMM()
window_smooth_data = 6
window_persitence = 30
beta_persistence = 0.9

hmm = HMM(nb_states=3)
hmm.p1 = np.array([1.54243294e-11, 5.07106916e-04, 8.72065952e-05, 9.98979845e-01, 8.52234426e-21, 1.25568196e-12, 7.85199401e-13, 4.25841826e-04])
hmm.p2 = np.array([3.25680580e-01, 1.77503496e-01, 4.95899060e-01, 7.21547291e-04, 6.96932383e-05, 1.93093305e-05, 1.06025552e-04, 2.89805651e-07])
hmm.p3 = np.array([6.93534587e-06, 1.04473011e-08, 2.91554932e-06, 1.93493842e-10, 7.38362033e-01, 1.40643862e-02, 2.41340621e-01, 6.22309818e-03])
hmm.A = np.array([[0.98961359, 0.00346214, 0.00692427],
                  [0.00666667, 0.99, 0.00333333],
                  [0.00099934, 0.00712054, 0.99188012]])
hmm.nu = np.array([5.66075578e-02, 9.43392442e-01, 5.88699965e-29])

ALPHA = {"paraglide": 0.20960958, "deltaplane": 0.17398039, "planeur": 0.1}


def get_regime(track, glider="paraglide"):
    obs = factory_data_HMM.get_data_hmm(raw_data=track, window_smooth_data=window_smooth_data,
                                        alpha_straight_rad=ALPHA[glider],
                                        window_persitence=window_persitence,
                                        beta_persistence=beta_persistence)
    df = factory_data_HMM.data
    df["regime_"] = hmm.predict_states_viterbi(obs)
    df["regime"] = roll_majority(df["regime_"], 90)
    return df, obs
