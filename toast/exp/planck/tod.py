# Copyright (c) 2015 by the parties listed in the AUTHORS file.
# All rights reserved.  Use of this source code is governed by 
# a BSD-style license that can be found in the LICENSE file.


from mpi4py import MPI

import unittest

import numpy as np

from scipy.constants import degree, arcmin, arcsec, c

import quaternionarray as qa

import healpy as hp

from toast.dist import distribute_det_samples

from toast.tod import TOD

from .utilities import load_ringdb, count_samples, read_eff, write_eff, load_RIMO, bolos_by_freq


xaxis = np.array( [1,0,0], dtype=np.float64 )
yaxis = np.array( [0,1,0], dtype=np.float64 )
zaxis = np.array( [0,0,1], dtype=np.float64 )

spinangle = 85.0 * degree

spinrot = qa.rotation( yaxis, np.pi/2 - spinangle )

cinv = 1e3 / c # Inverse light speed in km / s ( the assumed unit for velocity )


class Exchange(TOD):
    """
    Provide pointing and detector timestreams for Planck Exchange File Format data.

    Args:
        mpicomm (mpi4py.MPI.Comm): the MPI communicator over which the data is distributed.
        timedist (bool): if True, the data is distributed by time, otherwise by
                  detector.
        detectors (list): list of names to use for the detectors. Must match the names in the FITS HDUs.
        ringdb: Path to an SQLite database defining ring boundaries.
        effdir: directory containing the exchange files
        obt_range: data span in TAI seconds, overrides ring_range
        ring_range: data span in pointing periods, overrides od_range
        od_range: data span in operational days
    """

    def __init__(self, mpicomm=MPI.COMM_WORLD, detectors=None, ringdb=None, effdir=None, obt_range=None, ring_range=None, od_range=None, freq=None, RIMO=None, coord='G', deaberrate=True, obtmask=0, flagmask=0):

        if ringdb is None:
            raise ValueError('You must provide a path to the ring database')

        if effdir is None:
            raise ValueError('You must provide a path to the exchange files')
        
        if freq is None:
            raise ValueError('You must specify the frequency to run on')

        if RIMO is None:
            raise ValueError('You must specify which RIMO to use')

        self.ringdb_path = ringdb
        self.ringdb = load_ringdb( self.ringdb_path, mpicomm )

        self.RIMO_path = RIMO
        self.RIMO = load_RIMO( self.RIMO_path, mpicomm )

        self.eff_cache = {}

        self.freq = freq

        self.coord = coord

        self.deaberrate = deaberrate

        rank = mpicomm.rank

        self.globalstart = 0.0
        self.globalfirst = 0
        self.allsamp = 0
        self.allrings = []
        
        if rank == 0:
            self.globalstart, self.globalfirst, self.allsamp, self.allrings = count_samples( self.ringdb, self.freq, obt_range, ring_range, od_range )
        
        self.globalstart = mpicomm.bcast(self.globalstart, root=0)
        self.globalfirst = mpicomm.bcast(self.globalfirst, root=0)
        self.allsamp = mpicomm.bcast(self.allsamp, root=0)
        self.allrings = mpicomm.bcast(self.allrings, root=0)
        
        if detectors is None:
            detectors = bolos_by_freq(self.freq)

        # for data distribution, we need the contiguous sample
        # ranges based on the ring starts.

        ringstarts = [ x.first for x in self.allrings ]

        ringsizes = [ (y - x) for x, y in zip(ringstarts[:-1], ringstarts[1:]) ]
        ringsizes.append( self.allrings[-1].last - self.allrings[-1].first + 1 )

        super().__init__(mpicomm=mpicomm, timedist=True, detectors=detectors, samples=self.allsamp, sizes=ringsizes)

        self.effdir = effdir
        self.obtmask = obtmask
        self.flagmask = flagmask

        self.satobtmask = 1
        self.satquatmask = 1
        self.satvelmask = 1

        if self.coord == 'E':
            self.coordmatrix = None
            self.coordquat = None
        else:
            self.coordmatrix, do_conv, normcoord = hp.rotator.get_coordconv_matrix( ['E', self.coord] )
            self.coordquat = qa.from_rotmat( self.coordmatrix )

    def purge_eff_cache( self ):
        del self.eff_cache
        self.eff_cache = {}

    @property
    def valid_intervals(self):
        return self.allrings


    @property
    def rimo(self):
        return self.RIMO


    def _get(self, detector, flavor, local_start, n):

        data, flag = read_eff(local_start, n, self.globalfirst, self.local_offset, self.ringdb, self.ringdb_path, self.freq, self.effdir, detector.lower(), self.obtmask, self.flagmask, eff_cache=self.eff_cache)

        return (data, flag)


    def _put(self, detector, flavor, local_start, data, flags):

        result = write_eff(local_start, data, flags, self.globalfirst, self.local_offset, self.ringdb, self.ringdb_path, self.freq, self.effdir, detector.lower(), self.flagmask)
        # FIXME: should we check the result here?
        # We should NOT return result, since the return needs to be empty
        return


    def _get_pntg(self, detector, local_start, n):

        epsilon = self.RIMO[ detector ].epsilon
        eta = (1 - epsilon) / (1 + epsilon)
        detquat = self.RIMO[ detector ].quat        

        # Get the satellite attitude

        quats, flag = read_eff(local_start, n, self.globalfirst, self.local_offset, self.ringdb, self.ringdb_path, self.freq, self.effdir, 'attitude', self.satobtmask, self.satquatmask, eff_cache=self.eff_cache)
        quats = quats.T.copy()

        # Mask out samples that have unreliable pointing (interpolated across interval ends)
        
        start = self.globalfirst + self.local_offset + local_start
        stop = start + n
        ind = np.arange( start, stop )
        for interval_before, interval_after in zip( self.allrings[:-1], self.allrings[1:] ):
            gap_start = interval_before.last
            gap_stop = interval_after.first
            if gap_start <= stop and gap_stop >= start:
                flag[ np.logical_and( ind>gap_start, ind<gap_stop) ] = True

        # Get the satellite velocity

        if self.deaberrate:        
            satvel, flag2 = read_eff(local_start, n, self.globalfirst, self.local_offset, self.ringdb, self.ringdb_path, self.freq, self.effdir, 'velocity', self.satobtmask, self.satvelmask, eff_cache=self.eff_cache)
            flag |= flag2
            satvel = satvel.T.copy()

        # Rotate into detector frame and convert to desired format

        quats = qa.mult(qa.norm(quats), detquat)

        if self.deaberrate:
            # Correct for aberration
            vec = qa.rotate(quats, zaxis)
            abvec = np.cross(vec, satvel)
            lens = np.linalg.norm(abvec, axis=1)
            ang = lens * cinv
            abvec /= np.tile(lens, (3,1)).T # Normalize for direction
            abquat = qa.rotation(abvec, -ang)
            quats = qa.mult(abquat, quats)

        if self.coordquat is not None:
            quats = qa.mult(self.coordquat, quats)

        # Return
        return (quats.flatten(), flag)
    

    def _put_pntg(self, detector, local_start, start, data, flags):

        result = write_eff(local_start, data, flags, self.globalfirst, self.local_offset, self.ringdb, self.ringdb_path, self.freq, self.effdir, 'attitude', self.flagmask)
        # FIXME: should we check the result here?
        # We should NOT return result, since the return needs to be empty
        return


    def _get_times(self, local_start, n):
        data, flag = read_eff(local_start, n, self.globalfirst, self.local_offset, self.ringdb, self.ringdb_path, self.freq, self.effdir, 'obt', 0, 0, eff_cache=self.eff_cache)
        return data


    def _put_times(self, local_start, stamps):
        result = write_eff(local_start, stamps, np.zeros(stamps.shape[0], dtype=np.uint8), self.globalfirst, self.local_offset, self.ringdb, self.ringdb_path, self.freq, self.effdir, 'obt', 0)
        return

