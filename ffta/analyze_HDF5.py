# -*- coding: utf-8 -*-
"""
Created on Thu Feb 22 13:16:05 2018

@author: Raj
"""

import os
import numpy as np
import badpixels
import h5py

from matplotlib import pyplot as plt

from ffta.utils import hdf_utils
import pycroscopy as px

from pycroscopy.core.io.io_utils import get_time_stamp
from pycroscopy.io.write_utils import build_ind_val_dsets, Dimension
"""
Analyzes an HDF_5 format trEFM data set and writes the result into that file
"""

def find_FF(h5_path):
    
    parameters = hdf_utils.get_params(h5_path)
    h5_gp = hdf_utils._which_h5_group(h5_path)
    
    return h5_gp, parameters

def process(h5_file, ds = 'FF_Raw', ref='', clear_filter = False, verbose=True):
    """
    Processes FF_Raw dataset in the HDF5 file
    
    This then saves within the h5 file in FF_Group-processed
    
    This uses the dataset in this priority:
        *A relative path specific by ref, e.g. '/FF_Group/FF_Avg/FF_Avg'
        *A dataset specified by ds, returning the last found, e.g. 'FF_Raw'
        *FF_Group/FF_Raw found via searching from hdf_utils folder
    
    Typical usage:
    >> import pycroscopy as px
    >> h5_file = px.io.HDFwriter('path_to_h5_file.h5').file
    >> from ffta import analyze_HDF5
    >> tfp, shift, inst_freq = analyze_HDF5.process(h5_file, ref = '/FF_Group/FF_Avg/FF_Avg')
    
    
    h5_file : h5Py file or str
        Path to a specific h5 file on the disk or an hdf.file
        
    ds : str, optional
        The Dataset to search for in the file
        
    ref : str, optional
        A path to a specific dataset in the file.
        e.g. h5_file['/FF_Group/FF_Avg/FF_Avg']
        
    clear_filter : bool, optional
        For data already filtered, calls Line's clear_filter function to 
            skip FIR/windowing steps
    
    verbose : bool, optional,
        Whether to write data to the command line
    
    Returns
    -------
    tfp : ndarray
        time-to-first-peak image array
    shift : ndarray
        frequency shift image array
    inst_freq : ndarray (2D)
        instantaneous frequency array, an N x p array of N=rows*cols points
            and where p = points_per_signal (e.g. 16000 for 1.6 ms @10 MHz sampling)
    """
#    logging.basicConfig(filename='error.log', level=logging.INFO)
    ftype = str(type(h5_file))
    
    if ('str' in ftype) or ('File' in ftype) or ('Dataset' in ftype):
        
        h5_file = px.io.HDFwriter(h5_file).file
    
    else:

        raise TypeError('Must be string path, e.g. E:\Test.h5')
    
    # Looks for a ref first before searching for ds, h5_ds is group to process
    if any(ref):
        h5_ds = h5_file[ref]
        parameters = px.hdf_utils.get_attributes(h5_ds)
        
        if 'trigger' not in parameters:
            parameters = hdf_utils.get_params(h5_ds)
    
    elif ds != 'FF_Raw':
        h5_ds = px.hdf_utils.find_dataset(h5_file, ds)[-1]
        parameters = hdf_utils.get_params(h5_ds)
    
    else:
        h5_ds, parameters = find_FF(h5_file)

    if isinstance(h5_ds, h5py.Dataset):
        h5_gp = h5_ds.parent

    # Initialize file and read parameters
    num_cols = parameters['num_cols']
    num_rows = parameters['num_rows']
    pnts_per_pixel = parameters['pnts_per_pixel']
    pnts_per_avg = parameters['pnts_per_avg']

    if verbose:
        print('Recombination: ', parameters['recombination'])
        print( 'ROI: ', parameters['roi'])

    # Initialize arrays.
    tfp = np.zeros([num_rows, num_cols])
    shift = np.zeros([num_rows, num_cols])
    inst_freq = np.zeros([num_rows*num_cols, pnts_per_avg])

    # Initialize plotting.
    plt.ion()

    fig, a = plt.subplots(nrows=2, ncols=2,figsize=(13, 6))

    tfp_ax = a[0][1]
    shift_ax = a[1][1]
    
    img_length = parameters['FastScanSize']
    img_height = parameters['SlowScanSize']
    kwargs = {'origin': 'lower',  'x_size':img_length*1e6,
          'y_size':img_height*1e6, 'num_ticks': 5, 'stdevs': 3}
    
    kwargs = {'origin': 'lower',  'x_vec':img_length*1e6,
              'y_vec':img_height*1e6, 'num_ticks': 5, 'stdevs': 3}
    
    try:
        ht = h5_file['/height/Raw_Data'][:,0]
        ht = np.reshape(ht, [num_cols, num_rows]).transpose()
        ht_ax = a[0][0]
        ht_image, cbar = px.plot_utils.plot_map(ht_ax, np.fliplr(ht)*1e9, cmap='gray', **kwargs)
        cbar.set_label('Height (nm)', rotation=270, labelpad=16)
    except:
        pass
    
    tfp_ax.set_title('tFP Image')
    shift_ax.set_title('Shift Image')

    tfp_image, cbar_tfp = px.plot_utils.plot_map(tfp_ax, tfp * 1e6, 
                                                 cmap='inferno', show_cbar=False, **kwargs)
    shift_image, cbar_sh = px.plot_utils.plot_map(shift_ax, shift, 
                                                  cmap='inferno', show_cbar=False, **kwargs)
    text = tfp_ax.text(num_cols/2,num_rows+3, '')
    plt.show()

    # Load every file in the file list one by one.
    for i in range(num_rows):

        line_inst = hdf_utils.get_line(h5_ds, i)
        
        if clear_filter:
            line_inst.clear_filter_flags()
        
        tfp[i, :], shift[i, :], inst_freq[i*num_cols:(i+1)*num_cols,:] = line_inst.analyze()

        tfp_image, _ = px.plot_utils.plot_map(tfp_ax, tfp * 1e6, 
                                              cmap='inferno', show_cbar=False, **kwargs)
        shift_image, _ = px.plot_utils.plot_map(shift_ax, shift, 
                                                      cmap='inferno', show_cbar=False, **kwargs)

        tfp_sc = tfp[tfp.nonzero()] * 1e6
        tfp_image.set_clim(vmin=tfp_sc.min(), vmax=tfp_sc.max())

        shift_sc = shift[shift.nonzero()]
        shift_image.set_clim(vmin=shift_sc.min(), vmax=shift_sc.max())

        tfpmean = 1e6 * tfp[i, :].mean()
        tfpstd = 1e6 * tfp[i, :].std()

        if verbose:
            string = ("Line {0:.0f}, average tFP (us) ="
                      " {1:.2f} +/- {2:.2f}".format(i + 1, tfpmean, tfpstd))
            print(string)

            text.remove()
            text = tfp_ax.text((num_cols-len(string))/2,num_rows+4, string)

        #plt.draw()
        plt.pause(0.0001)

        del line_inst  # Delete the instance to open up memory.

    tfp_image, cbar_tfp = px.plot_utils.plot_map(tfp_ax, tfp * 1e6, cmap='inferno', **kwargs)
    cbar_tfp.set_label('Time (us)', rotation=270, labelpad=16)
    shift_image, cbar_sh = px.plot_utils.plot_map(shift_ax, shift, cmap='inferno', **kwargs)
    cbar_sh.set_label('Frequency Shift (Hz)', rotation=270, labelpad=16)
    text = tfp_ax.text(num_cols/2,num_rows+3, '')
    
    plt.show()

    h5_if = save_process(h5_file, h5_ds.parent, inst_freq, parameters, verbose=verbose)
    _, _,_, tfp_fixed = save_ht_outs(h5_file, h5_if.parent, tfp, shift, parameters, verbose=verbose)
    
    #save_CSV(h5_path, tfp, shift, tfp_fixed, append=ds)

    return tfp, shift, inst_freq

def save_process(h5_file, h5_gp, inst_freq, parm_dict, verbose=False):
    """ Adds Instantaneous Frequency as a main dataset """
    # Error check
    if isinstance(h5_gp, h5py.Dataset):
        raise ValueError('Must pass an h5Py group')

    # Get relevant parameters
    num_rows = parm_dict['num_rows']
    num_cols = parm_dict['num_cols']
    pnts_per_avg = parm_dict['pnts_per_avg']

    h5_meas_group = px.hdf_utils.create_indexed_group(h5_gp, 'processed')

    # Create dimensions
    pos_desc = [Dimension('X', 'm', np.linspace(0, parm_dict['FastScanSize'], num_cols)),
                Dimension('Y', 'm', np.linspace(0, parm_dict['SlowScanSize'], num_rows))]
    ds_pos_ind, ds_pos_val = build_ind_val_dsets(pos_desc, is_spectral=False, verbose=verbose)
    spec_desc = [Dimension('Time', 's',np.linspace(0, parm_dict['total_time'], pnts_per_avg))]
    ds_spec_inds, ds_spec_vals = build_ind_val_dsets(spec_desc, is_spectral=True, verbose=verbose)

    # Writes main dataset
    h5_if = px.hdf_utils.write_main_dataset(h5_meas_group,  
                                             inst_freq,
                                             'inst_freq',  # Name of main dataset
                                             'Frequency',  # Physical quantity contained in Main dataset
                                             'Hz',  # Units for the physical quantity
                                             pos_desc,  # Position dimensions
                                             spec_desc,  # Spectroscopic dimensions
                                             dtype=np.float32,  # data type / precision
                                             main_dset_attrs=parm_dict)

    px.hdf_utils.copy_attributes(h5_if, h5_gp)

    return h5_if


def save_ht_outs(h5_file, h5_gp, tfp, shift, parameters, verbose=False):
    """ Save processed Hilbert Transform outputs"""
    # Error check
    if isinstance(h5_gp, h5py.Dataset):
        raise ValueError('Must pass an h5Py group')
        
    # Filter bad pixels
    tfp_fixed, _ = badpixels.fix_array(tfp, threshold=2)
    tfp_fixed = np.array(tfp_fixed)
    
    # write data
    grp_name = h5_gp.name
    grp_tr = px.io.VirtualGroup(grp_name)
    tfp_px = px.io.VirtualDataset('tfp', tfp, parent = h5_gp)
    shift_px = px.io.VirtualDataset('shift', shift, parent = h5_gp)
    tfp_fixed_px = px.io.VirtualDataset('tfp_fixed', tfp_fixed, parent = h5_gp)

    grp_tr.attrs['timestamp'] = get_time_stamp()
    grp_tr.add_children([tfp_px])
    grp_tr.add_children([shift_px])
    grp_tr.add_children([tfp_fixed_px])
    
    # Find folder, write to it
    hdf = px.io.HDFwriter(h5_file)
    h5_refs = hdf.write(grp_tr, print_log=verbose), 
    
    return h5_refs, tfp, shift, tfp_fixed

def save_CSV_from_file(h5_file, h5_path='/', append=''):
    """
    Saves the tfp, shift, and fixed_tfp as CSV files
    
    h5_file : H5Py file
    
    h5_path : str, optional
        specific folder path to write to
    
    append : str, optional
        text to append to file name
    """
    
    h5_file = px.ioHDF5(h5_file).file
    tfp = px.hdf_utils.getDataSet(h5_file[h5_path], 'tfp')[0].value
    tfp_fixed = px.hdf_utils.getDataSet(h5_file[h5_path], 'tfp_fixed')[0].value
    shift = px.hdf_utils.getDataSet(h5_file[h5_path], 'shift')[0].value
    
    path = h5_file.file.filename.replace('\\','/')
    path = '/'.join(path.split('/')[:-1])+'/'
    os.chdir(path)
    np.savetxt('tfp-'+append+'.csv', np.fliplr(tfp).T, delimiter=',')
    np.savetxt('shift-'+append+'.csv', np.fliplr(shift).T, delimiter=',')
    np.savetxt('tfp_fixed-'+append+'.csv', np.fliplr(tfp_fixed).T, delimiter=',')
    
    return

def plot_tfps(h5_file, h5_path='/', append='', savefig=True, stdevs=2):
    """
    Plots the relevant tfp, inst_freq, and shift values as separate image files
    
    h5_file : h5Py File
    
    h5_path : str, optional
        Location of the relevant datasets to be saved/plotted. e.g. h5_rb.name
    
    append : str, optional
        A string to include in the saved figure filename
        
    savefig : bool, optional
        Whether or not to save the image
        
    stdevs : int, optional
        Number of standard deviations to display
    """
    
    h5_file = px.ioHDF5(h5_file).file

    parm_dict = px.hdf_utils.get_attributes(h5_file[h5_path])

    if 'trigger' not in parm_dict:
        parm_dict = hdf_utils.get_params(h5_file)

    if 'Dataset' in str(type(h5_file[h5_path])):
        h5_path = h5_file[h5_path].parent.name
    
    tfp = px.hdf_utils.getDataSet(h5_file[h5_path], 'tfp')[0].value
    tfp_fixed = px.hdf_utils.getDataSet(h5_file[h5_path], 'tfp_fixed')[0].value
    shift = px.hdf_utils.getDataSet(h5_file[h5_path], 'shift')[0].value
    
    xs = parm_dict['FastScanSize']
    ys = parm_dict['SlowScanSize']
    asp = ys/xs
    if asp != 1:
        asp = asp * 2
        
    fig, a = plt.subplots(nrows=3, figsize=(8,9))
    
    [vmint, vmaxt] = np.mean(tfp)-2*np.std(tfp), np.mean(tfp)-2*np.std(tfp)
    [vmins, vmaxs] = np.mean(shift)-2*np.std(shift), np.mean(shift)-2*np.std(shift)
    
    _, cbar_t = px.plot_utils.plot_map(a[0], tfp_fixed*1e6, x_size = xs*1e6, y_size = ys*1e6,
                                       aspect=asp, cmap='inferno', stdevs=stdevs)
    
    _, cbar_r = px.plot_utils.plot_map(a[1], 1/(1e3*tfp_fixed), x_size = xs*1e6, y_size = ys*1e6,
                                       aspect=asp, cmap='inferno', stdevs=stdevs)
    _, cbar_s = px.plot_utils.plot_map(a[2], shift, x_size = xs*1e6, y_size = ys*1e6,
                                       aspect=asp, cmap='inferno', stdevs=stdevs)

    cbar_t.set_label('tfp (us)', rotation=270, labelpad=16)
    a[0].set_title('tfp', fontsize=12)

    cbar_r.set_label('Rate (kHz)', rotation=270, labelpad=16)
    a[1].set_title('1/tfp', fontsize=12)
    
    cbar_s.set_label('shift (Hz)', rotation=270, labelpad=16)
    a[2].set_title('shift', fontsize=12)

    fig.tight_layout()

    if savefig:
        path = h5_file.file.filename.replace('\\','/')
        path = '/'.join(path.split('/')[:-1])+'/'
        os.chdir(path)
        fig.savefig('tfp_shift_'+append+'_.tif', format='tiff')

    return

