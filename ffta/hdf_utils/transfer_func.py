# -*- coding: utf-8 -*-
"""
Created on Mon Aug 19 12:10:38 2019

@author: Raj
"""

import pyUSID as usid

from igor import binarywave as bw
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from scipy import signal as sg

def transfer_function(h5_file, tf_file = '', params_file = '', 
                      psd_freq=1e6, offset = 0.0016, plot=False):
    '''
    Reads in the transfer function .ibw, then creates two datasets within
    a parent folder 'Transfer_Function'
    
    This will destructively overwrite an existing Transfer Function in there
    
    1) TF (transfer function)
    2) Freq (frequency axis for computing Fourier Transforms)
    
    tf_file : ibw
        Transfer Function .ibw File
        
    params_file : string
        The filepath in string format for the parameters file containing
            Q, AMPINVOLS, etc.
    
    psd_freq : float
        The maximum range of the Power Spectral Density.
        For Asylum Thermal Tunes, this is often 1 MHz on MFPs and 2 MHz on Cyphers
        
    offset : float
        To avoid divide-by-zero effects since we will divide by the transfer function
            when generating GKPFM data
            
    Returns:
        h5_file['Transfer_Function'] : the Transfer Function group
    '''
    if not any(tf_file):
        tf_file = usid.io_utils.file_dialog(caption='Select Transfer Function file ',
                                            file_filter='IBW Files (*.ibw)')
    data = bw.load(tf_file)
    tf = data.get('wave').get('wData')
    
    if 'Transfer_Function' in h5_file:
        del h5_file['/Transfer_Function']
    h5_file.create_group('Transfer_Function')
    h5_file['Transfer_Function'].create_dataset('TF', data = tf)
    
    freq = np.linspace(0, psd_freq, len(tf))
    h5_file['Transfer_Function'].create_dataset('Freq', data = freq)
    
    parms = params_list(params_file, psd_freq=psd_freq)
    
    for k in parms:
        h5_file['Transfer_Function'].attrs[k] = float(parms[k])

    tfnorm = float(parms['Q']) * (tf - np.min(tf))/ (np.max(tf) - np.min(tf)) 
    tfnorm += 0.0016
    h5_file['Transfer_Function'].create_dataset('TFnorm', data = tfnorm)
    
    if plot:
        plt.figure()
        plt.plot(freq, tf)
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Amplitude (m)')
        plt.yscale('log')
        plt.title('Transfer Function')
    
    return h5_file['Transfer_Function']

def resample_tf(h5_file, psd_freq = 1e6, sample_freq = 10e6):
    '''
    Resamples the Transfer Function based on the desired target frequency
    
    This is important for dividing the transfer function elements together
    
    psd_freq : float
        The maximum range of the Power Spectral Density.
        For Asylum Thermal Tunes, this is often 1 MHz on MFPs and 2 MHz on Cyphers
        
    sample_freq : float
        The desired output sampling. This should match your data.   
    
    '''
    TFN = h5_file['Transfer_Function/TFnorm'][()]
    #FQ = h5_file['Transfer_Function/Freq'][()]
    
    # Generate the iFFT from the thermal tune data
    tfn = np.fft.ifft(TFN)
    #tq = np.linspace(0, 1/np.abs(FQ[1] - FQ[0]), len(tfn))
    
    # Resample
    scale = int(sample_freq / psd_freq)
    tfn_rs = sg.resample(tfn, len(tfn)*scale)  # from 1 MHz to 10 MHz
    TFN_RS = np.fft.fft(tfn_rs)
    FQ_RS = np.linspace(0, sample_freq, len(tfn_rs))
    
    h5_file['Transfer_Function'].create_dataset('TFnorm_resampled', data = TFN_RS)
    h5_file['Transfer_Function'].create_dataset('Freq_resampled', data = FQ_RS)
    
    return h5_file['Transfer_Function']

def params_list(path = '', psd_freq=1e6, lift=50):
    '''
    Reads in a Parameters file as saved in Igor as a dictionary
    
    For use in creating attributes of transfer Function
    
    '''
    if not any(path):
        path = usid.io.io_utils.file_dialog(caption='Select Parameters Files ',
                                            file_filter='Text (*.txt)')
    
    df = pd.read_csv(path, sep='\t', header=1)
    df = df.set_index(df['Unnamed: 0'])
    df = df.drop(columns='Unnamed: 0')
    
    parm_dict = df.to_dict()['Initial']
    parm_dict['PSDFreq'] = psd_freq
    parm_dict['Lift'] = lift
    
    return parm_dict