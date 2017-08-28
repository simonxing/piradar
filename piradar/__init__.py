from __future__ import division
import warnings
from pathlib import Path
import numpy as np
from numpy.random import seed,random,normal
import scipy.signal as signal
from matplotlib.pyplot import hist,subplots,sca,figure
try:
    import pygame
except ImportError:
    pygame = None
#
try:
    import stuffr
except ImportError:
    stuffr=None
#
from .delayseq import delayseq
#
c = 299792458 # vacuum speed of light [m/s]


def playaudio(dat, fs:int, ofn:Path=None):
    """
    playback radar data using PyGame audio
    """
    if dat is None:
        return

    fs = int(fs)
# %% rearrange sound array to [N,2] for Numpy playback/writing
    if isinstance(dat.dtype,np.int16):
        odtype = dat.dtype
        fnorm = 32768
    elif isinstance(dat.dtype,np.int8):
        odtype = dat.dtype
        fnorm = 128
    elif dat.dtype in ('complex128','float64'):
        odtype = np.float64
        fnorm = 1.0
    elif dat.dtype in ('complex64', 'float32'):
        odtype = np.float32
        fnorm = 1.0
    else:
        raise TypeError(f'unknown input type {dat.dtype}')

    if np.iscomplexobj(dat):
        snd = np.empty((dat.size,2),dtype=odtype)
        snd[:,0] = dat.real
        snd[:,1] = dat.imag
    else:
        snd = dat  # monaural

    snd = snd * fnorm / snd.max()
# %% optional write wav file
    if ofn:
        ofn = Path(ofn).expanduser()
        if not ofn.is_file():
            import scipy.io.wavfile
            print('writing audio to',ofn)
            scipy.io.wavfile.write(ofn, fs, snd)
        else:
            warnings.warn(f'did NOT overwrite existing {ofn}')
# %% play sound
    if 100e3 > fs > 1e3:
        Nloop = 0
        if pygame is None:
            print('audio playback disabled')
            return

        assert snd.ndim in (1,2), 'mono or stereo Nx2'

        # scale to pygame required int16 format
        fnorm = 32768 / snd.max()
        pygame.mixer.pre_init(fs, size=-16, channels=snd.ndim)
        pygame.mixer.init()
        sound = pygame.sndarray.make_sound((snd * fnorm).astype(np.int16))

        sound.play(loops=Nloop)
    else:
        print(f'skipping playback due to fs={fs} Hz')
# %%
def sim_iono(tx,fs,dist_m,codelen,Nstd,Ajam,station_id,usefilter,outpath,verbose):
    awgn = (normal(scale=Nstd, size=tx.size) + 1j*normal(scale=Nstd, size=tx.size))

    jam = Ajam * waveform_to_file(station_id+1, codelen, filt=usefilter, outpath=outpath,verbose=verbose)

    # delay transmit signal and add undesired signals
    tdelay_sec = 2*dist_m / c
    print(f'refl. height {dist_m/1e3} km -> delay {tdelay_sec:.3e} sec')

    rx = delayseq(tx,tdelay_sec,fs) + awgn + jam

    return rx


def estimate_range(tx,rx,fs,quiet=False):
    """
    tx: the known, noise-free, undelayed transmit signal (bistatic radars agree beforehand on the psuedorandom sequence)
    rx: the noisy, corrupted, interference, jammed signal to estimate distance from
    fs: baseband sample frequency
    """
    Rxy =  np.correlate(tx, rx, 'full')
    lags = np.arange(Rxy.size) - Rxy.size // 2
    pklag = lags[Rxy.argmax()]

    distest_m = -pklag / fs / 2 * c

    mR = abs(Rxy)  # magnitude of complex cross-correlation
    if not quiet:
        ax = figure().gca()
        ax.plot(lags,mR)
        ax.plot(pklag,mR[mR.argmax()], color='red', marker='*')
        ax.set_title('cross-correlation of receive waveform with transmit waveform')
        ax.set_ylabel('$|R_{xy}|$')
        ax.set_xlabel('lags')
        ax.set_xlim(pklag-100,pklag+100)


    return distest_m

def create_pseudo_random_code(clen=10000,rseed=0,verbose=False):
    """
    Create waveform files for hfradar
    Juha Vierinen
    """
    Npt = 200  # number of points to plot, just for plotting, arbitrary
    """
    seed is a way of reproducing the random code without having to store all actual codes.
    the seed can then act as a sort of station_id.
    """
    seed(rseed)

    """
    generate a uniform random phase modulated (complex) signal 'sig".
    It's single precision floating point for SDR, since DAC is typically <= 16 bits!
    """
    sig = np.exp(1j*2.0*np.pi*random(clen)).astype('complex64')

    if stuffr is not None:
        stuffr.plot_cts(sig[:Npt])

    if verbose:
        fg,ax = subplots(3,1)
        sca(ax[0])
        hist(sig.real)#,50)
        sca(ax[1])
        hist(sig.imag)

        #hist(random(clen))

    return sig

def rep_seq(x, rep):
    """
    oversample a phase code by a factor of rep
    """
    L = len(x)*rep
    res = np.empty(L, dtype=x.dtype)
    idx = np.arange(len(x))*rep
    for i in range(rep):
        res[idx+i] = x

    return res

def waveform_to_file(station,clen=10000,oversample=10, filt=False, outpath=None,verbose=False):
    """
    lets use 0.1 s code cycle and coherence assumption
    our transmit bandwidth is 100 kHz, and with a clen=10e3 baud code,
    that is 0.1 seconds per cycle as a coherence assumption.
    furthermore, we use a 1 MHz bandwidth, so we oversample by a factor of 10.

    NOTE: this writing method doesn't store any metadata - have to know the sample rate
    """

    a = rep_seq(create_pseudo_random_code(clen,station,verbose), rep=oversample)

    if filt == True:
        w = np.zeros([oversample*clen], dtype='complex64') # yes, zeros for zero-padded
        fl = int(oversample+(0.1*oversample))

        w[:fl]= signal.blackmanharris(fl) # W[fl:] \equiv 0

        aa = np.fft.ifft(np.fft.fft(w) * np.fft.fft(a))

        a = (aa/abs(aa).max()).astype('complex64') #normalized, single prec complex

    if outpath:
        p = Path(outpath).expanduser()
        p.mkdir(parents=True, exist_ok=True)

        ofn = p / f"code-l{clen}-b{oversample}-{station:06d}.bin"
        print('writing',ofn)

        # https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.tofile.html
        a.tofile(ofn) # this binary format is OK for GNU Radio to read

    return a
