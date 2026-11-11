# -*- coding: utf-8 -*-
"""Extraccion de rasgos acusticos (Praat + librosa) a 16 kHz mono. Requiere ffmpeg en el PATH."""
import os, subprocess, tempfile, warnings
import numpy as np
import pandas as pd
import soundfile as sf
import librosa
import parselmouth
from parselmouth.praat import call
from scipy.signal import find_peaks
from scipy.stats import skew, kurtosis

warnings.filterwarnings("ignore")
SR = 16000                    # todos los audios se llevan a 16 kHz mono
EXT = (".m4a", ".wav", ".mp3", ".flac", ".mp4", ".ogg")


def cargar(path):
    """Lee cualquier formato a 16 kHz mono usando ffmpeg (robusto con .m4a)."""
    with tempfile.TemporaryDirectory() as d:
        tmp = os.path.join(d, "x.wav")
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-ac", "1", "-ar", str(SR), tmp],
                           capture_output=True)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.decode(errors="ignore")[:200])
        y, sr = sf.read(tmp, dtype="float32")
    return y, sr


def prosodicos(y, sr):
    """Jitter, shimmer (fracciones) y variabilidad de F0 (coef. de variacion) con Praat."""
    snd = parselmouth.Sound(y, sampling_frequency=sr)
    pitch = snd.to_pitch(time_step=0.01, pitch_floor=75, pitch_ceiling=500)
    f0 = pitch.selected_array["frequency"]
    f0 = f0[f0 > 0]
    if len(f0) < 20:                       # casi sin voz detectada
        return dict(jitter=np.nan, shimmer=np.nan, f0_var=np.nan, f0_mean=np.nan, voiced_ratio=len(f0) / max(1, len(pitch.selected_array["frequency"])))
    pp = call(snd, "To PointProcess (periodic, cc)", 75, 500)
    jit = call(pp, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)
    shi = call([snd, pp], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
    return dict(jitter=jit, shimmer=shi, f0_var=float(np.std(f0) / np.mean(f0)), f0_mean=float(np.mean(f0)),
                voiced_ratio=len(f0) / len(pitch.selected_array["frequency"]))


def espectrales(y, sr):
    S = np.abs(librosa.stft(y, n_fft=512, hop_length=160)) ** 2           # potencia
    freqs = librosa.fft_frequencies(sr=sr, n_fft=512)
    flat = float(np.mean(librosa.feature.spectral_flatness(S=np.sqrt(S))))
    cent = float(np.mean(librosa.feature.spectral_centroid(S=np.sqrt(S), sr=sr)))
    total = S.sum() + 1e-12
    hf = float(S[freqs >= 4000].sum() / total)                            # proporcion de energia >= 4 kHz
    mel = librosa.feature.melspectrogram(S=S, sr=sr, n_mels=64)
    logmel = librosa.power_to_db(mel + 1e-10)
    m = logmel.mean(axis=1)                                               # espectro medio (dB)
    plateau = float(np.mean(np.abs(np.diff(m)) < 1.0))                    # fraccion de bandas "planas" (<1 dB)
    peaks, _ = find_peaks(m, prominence=3.0)                              # picos (prominencia >= 3 dB)
    v = logmel.ravel()
    return dict(spectral_flatness=flat, spectral_centroid=cent, hf_energy=hf, plateau_ratio=plateau,
                peak_count=int(len(peaks)), mel_mean=float(v.mean()), mel_std=float(v.std()),
                mel_skew=float(skew(v)), mel_kurt=float(kurtosis(v)))


def extraer(path, label=None):
    """Devuelve el diccionario de rasgos de un audio (mismas columnas que rasgos.csv)."""
    y, sr = cargar(path)
    y = y / (np.max(np.abs(y)) + 1e-9)
    row = dict(file=os.path.basename(path), label=label, duration_s=round(len(y) / sr, 2))
    row.update(prosodicos(y, sr)); row.update(espectrales(y, sr))
    return row
