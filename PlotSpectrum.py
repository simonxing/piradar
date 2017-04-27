#!/usr/bin/env python
"""
Plot time & frequency spectrum of a GNU Radio received file.
Also attempts to playback sound from file (optionally, write .wav file)

CW Example
./PlotSpectrum.py ~/Dropbox/piradar/data/MH_exercise.bin 100e3 -t 2 3 -flim 0 600 -fx0 -9700

FMCW Example
./PlotSpectrum.py ~/Dropbox/piradar/data/B200_5GHz_FMCW.bin 10e6 -t 1 1.1

Reference:
http://www.trondeau.com/examples/2010/9/12/basic-filtering.html
https://www.csun.edu/~skatz/katzpage/sdr_project/sdr/grc_tutorial4.pdf
http://www.ece.uvic.ca/~elec350/grc_doc/ar01s12s08.html
"""
from pathlib import Path
from matplotlib.pyplot import show,figure
#
from piradar import loadbin,playaudio
from piradar.plots import spec

fsaudio = 8e3 # [Hz] arbitrary sound card  8e3,16e3, etc.


if __name__ == '__main__':
    from argparse import ArgumentParser
    p = ArgumentParser()
    p.add_argument('fn',help='.bin file to process')
    p.add_argument('fs',help='sample rate of .bin file [Hz]',type=float) #float to allow 100e3
    p.add_argument('-t','--tlim',help='start stop [seconds] to load',type=float,nargs=2,default=(0,None))
    p.add_argument('-flim',help='min max frequency [Hz] to plot',nargs=2,type=float)
    p.add_argument('-vlim',help='min max amplitude [dB] to plot',nargs=2,type=float)
    p.add_argument('-fx0',help='center frequency (downshift to) [Hz]',type=float)
    p = p.parse_args()

    fn=Path(p.fn).expanduser()

    fs = int(p.fs) # to allow 100e3 on command line
    decim = int(fs//fsaudio)

    dat,t = loadbin(fn, fs, p.tlim, p.fx0, decim)
    fs //= decim
#%%
    if dat.size<1e6: # plots will crash if too many points
        ax = figure().gca()
        ax.plot(t, dat.real[:])
        ax.set_title(fn.name)
        ax.set_xlabel('time [sec]')
        ax.set_ylabel('amplitude')

        spec(dat, fs, p.flim, vlim=p.vlim)
    else:
        print('skipped plotting, too many points:',dat.size)

# %% play sound
    playaudio(dat,fs)
    show()
