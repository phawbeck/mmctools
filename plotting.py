"""
Library of standardized plotting functions for basic plot formats
"""
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from scipy.interpolate import interp1d
from scipy.signal import welch

# TODO:
# - Separate out calculation of spectra?

# Standard field labels
standard_fieldlabels = {'wspd': r'Wind speed [m/s]',
                        'wdir': r'Wind direction $[^\circ]$',
                        'thetav': r'$\theta_v$ [K]',
                        'uu': r'$\langle u^\prime u^\prime \rangle \;[\mathrm{m^2/s^2}]$',
                        'vv': r'$\langle v^\prime v^\prime \rangle \;[\mathrm{m^2/s^2}]$',
                        'ww': r'$\langle w^\prime w^\prime \rangle \;[\mathrm{m^2/s^2}]$',
                        'uv': r'$\langle u^\prime v^\prime \rangle \;[\mathrm{m^2/s^2}]$',
                        'uw': r'$\langle u^\prime w^\prime \rangle \;[\mathrm{m^2/s^2}]$',
                        'vw': r'$\langle v^\prime w^\prime \rangle \;[\mathrm{m^2/s^2}]$',
                        'tw': r'$\langle w^\prime \theta^\prime \rangle \;[\mathrm{Km/s}]$',
                        'TI': r'TI $[-]$',
                        'TKE': r'TKE $[\mathrm{m^2/s^2}]$',
                        }

# Standard field labels for frequency spectra
standard_spectrumlabels = {'u': r'$E_{uu}\;[\mathrm{m^2/s}]$',
                           'v': r'$E_{vv}\;[\mathrm{m^2/s}]$',
                           'w': r'$E_{ww}\;[\mathrm{m^2/s}]$',
                           'wspd': r'$E_{UU}\;[\mathrm{m^2/s}]$',
                           }

# Default color cycle
default_colors = plt.rcParams['axes.prop_cycle'].by_key()['color']

class PlottingInput(object):
    """
    Auxiliary class to collect input data and options for plotting
    functions, and to check if the inputs are consistent
    """

    def __init__(self, datasets, fields, **argd):
        # Add all arguments as class attributes
        self.__dict__.update({'datasets':datasets,
                              'fields':fields,
                              **argd})

        # Check consistency of all attributes
        self._check_consistency()

    def _check_consistency(self):
        """
        Check consistency of all input data
        """
        # If a single dataset is provided, convert to a dictionary
        # under a generic key 'Dataset'
        if isinstance(self.datasets,pd.DataFrame):
            self.datasets = {'Dataset': self.datasets}

        # If fields is a single instance, convert to a list
        if isinstance(self.fields,str):
            self.fields = [self.fields,]

        # If heights is single instance, convert to list
        try:
            if isinstance(self.heights,(int,float)):
                self.heights = [self.heights,]
        except AttributeError:
            pass

        # If times is single instance, convert to list
        try:
            if isinstance(self.times,(str,int,float,np.number)):
                self.times = [self.times,]
        except AttributeError:
            pass

        # Check if all datasets have at least one of the requested fields
        for dfname in self.datasets:
            df = self.datasets[dfname]
            assert(any([field in df.columns for field in self.fields])), \
                'Dataset '+dfname+' does not contain any of the requested fields'

        # If one set of fieldlimits is specified, check number of fields
        # and convert to dictionary
        try:
            if isinstance(self.fieldlimits, (list, tuple)):
                assert(len(self.fields)==1), 'Unclear to what field fieldlimits corresponds'
                self.fieldlimits = {self.fields[0]:self.fieldlimits}
        except AttributeError:
            self.fieldlimits = {}

        # If one fieldlabel is specified, check number of fields
        try:
            if isinstance(self.fieldlabels, str):
                assert(len(self.fields)==1), 'Unclear to what field fieldlabels corresponds'
                self.fieldlabels = {self.fields[0]: self.fieldlabels}
        except AttributeError:
            self.fieldlabels = {}

        # If one colorscheme is specified, check number of fields
        try:
            self.cmap = {}
            if isinstance(self.colorschemes, str):
                assert(len(self.fields)==1), 'Unclear to what field colorschemes corresponds'
                self.cmap[self.fields[0]] = mpl.cm.get_cmap(self.colorschemes)
            else:
            # Set missing colorschemes to viridis
                for field in self.fields:
                    if field not in self.colorschemes.keys():
                        self.colorschemes[field] = 'viridis'
                    self.cmap[field] = mpl.cm.get_cmap(self.colorschemes[field])
        except AttributeError:
            pass

        # Make sure fieldorder is recognized
        try:
            assert(self.fieldorder in ['C','F']), "Error: fieldorder '"\
                +self.fieldorder+"' not recognized, must be either 'C' or 'F'"
        except AttributeError:
            pass

    def get_available_fields(self,dfname):
        """
        Return list of available fields for dataset 'dfname'
        """
        available_fields = []
        for field in self.fields:
            if field in self.datasets[dfname].columns:
                available_fields.append(field)
        return available_fields

    def set_missing_fieldlimits(self):
        """
        Set missing fieldlimits to min and max over all datasets
        """
        for field in self.fields:
            if field not in self.fieldlimits.keys():
                self.fieldlimits[field] = [ min([df[field].min() for df in self.datasets.values()]),
                                            max([df[field].max() for df in self.datasets.values()]) ]


def _create_subplots_if_needed(ntotal,
                               ncols=None,
                               default_ncols=1,
                               fieldorder='C',
                               avoid_single_column=False,
                               sharex=False,
                               sharey=False,
                               subfigsize=(12,3),
                               wspace=0.4,
                               hspace=0.4,
                               fig=None,
                               ax=None
                               ):
    """
    Auxiliary function to create fig and ax

    If fig and ax are None:
    - Set nrows and ncols based on ntotal and specified ncols,
      accounting for fieldorder and avoid_single_column
    - Create fig and ax with nrows and ncols, taking into account
      sharex, sharey, subfigsize, wspace, hspace

    If fig and ax are not None:
    - Try to determine nrows and ncols from ax
    - Check whether size of ax corresponds to ntotal
    """

    if ax is None:
        if not ncols is None:
            # Use ncols if specified and appropriate
            assert(ntotal%ncols==0), 'Error: Specified number of columns is not a true divisor of total number of subplots'
            nrows = int(ntotal/ncols)
        else:
            # Defaut number of columns
            ncols = default_ncols
            nrows = int(ntotal/ncols)
    
            if fieldorder=='F':
                # Swap number of rows and columns
                nrows, ncols = ncols, nrows
            
            if avoid_single_column and ncols==1:
                # Swap number of rows and columns
                nrows, ncols = ncols, nrows

        # Create fig and ax with nrows and ncols
        fig,ax = plt.subplots(nrows=nrows,ncols=ncols,sharex=sharex,sharey=sharey,figsize=(subfigsize[0]*ncols,subfigsize[1]*nrows))

        # Adjust subplot spacing
        fig.subplots_adjust(wspace=wspace,hspace=hspace)

    else:
        # Make sure user-specified axes has appropriate size
        assert(np.asarray(ax).size==ntotal), 'Specified axes does not have the right size'

        # Determine nrows and ncols in specified axes
        try:
            nrows,ncols = np.asarray(ax).shape
        except ValueError:
            # ax array has only one dimension
            # there is no way of knowing whether ax is a single row
            # or a single column, so assuming the latter
            nrows = np.asarray(ax).size
            ncols = 1

    return fig, ax, nrows, ncols


def plot_timeheight(datasets,
                    fields,
                    fig=None,ax=None,
                    colorschemes={},
                    fieldlimits={},
                    heightlimits=None,
                    timelimits=None,
                    fieldlabels={},
                    labelsubplots=False,
                    showcolorbars=True,
                    ncols=1,
                    subfigsize=(12,4),
                    datasetkwargs={},
                    **kwargs
                    ):
    """
    Plot time-height contours for different datasets and fields

    Usage
    =====
    datasets : pandas.DataFrame or dict 
        Dataset(s). If more than one set, datasets should
        be a dictionary with entries <dataset_name>: dataset
    fields : str or list
        Fieldname(s) corresponding to particular column(s) of
        the datasets
    fig : figure handle
        Custom figure handle. Should be specified together with ax
    ax : axes handle, or list or numpy ndarray with axes handles
        Customand axes handle(s).
        Size of ax should equal ndatasets*nfields
    colorschemes : str or dict
        Name of colorschemes. If only one field is plotted, colorschemes
        can be a string. Otherwise, it should be a dictionary with
        entries <fieldname>: name_of_colorschemes
        Missing colorschemess are set to 'viridis'
    fieldlimits : list or tuple, or dict
        Value range for the various fields. If only one field is 
        plotted, fieldlimits can be a list or tuple. Otherwise, it
        should be a dictionary with entries <fieldname>: fieldlimit.
        Missing fieldlimits are set automatically
    heightlimits : list or tuple
        Height axis limits
    timelimits : list or tuple
        Time axis limits
    fieldlabels : str or dict
        Custom field labels. If only one field is plotted, fieldlabels
        can be a string. Otherwise it should be a dictionary with
        entries <fieldname>: fieldlabel
    labelsubplots : bool
        Label subplots as (a), (b), (c), ...
    showcolorbars : bool
        Show colorbar per subplot
    ncols : int
        Number of columns in axes grid, must be a true divisor of total
        number of axes.
    subfigsize : list or tuple
        Standard size of subfigures
    datasetkwargs : dict
        Dataset-specific options that are passed on to the actual
        plotting function. These options overwrite general options
        specified through **kwargs. The argument should be a dictionary
        with entries <dataset_name>: {**kwargs}
    **kwargs : other keyword arguments
        Options that are passed on to the actual plotting function.
        Note that these options should be the same for all datasets and
        fields and can not be used to set dataset or field specific
        limits, colorschemess, norms, etc.
        Example uses include setting shading, rasterized, etc.
    """

    args = PlottingInput(
        datasets=datasets,
        fields=fields,
        fieldlimits=fieldlimits,
        fieldlabels=fieldlabels,
        colorschemes=colorschemes,
    )
    args.set_missing_fieldlimits()

    nfields = len(args.fields)
    ndatasets = len(args.datasets)
    ntotal = nfields * ndatasets

    # Concatenate custom and standard field labels
    # (custom field labels overwrite standard fields labels if existent)
    args.fieldlabels = {**standard_fieldlabels, **args.fieldlabels}        

    fig, ax, nrows, ncols = _create_subplots_if_needed(
                                    ntotal,
                                    ncols,
                                    sharex=True,
                                    sharey=True,
                                    subfigsize=subfigsize,
                                    fig=fig,
                                    ax=ax
                                    )

    # Create flattened view of axes
    axv = np.asarray(ax).reshape(-1)

    # Initialise list of colorbars
    cbars = []

    # Loop over datasets, fields and times 
    for i, dfname in enumerate(args.datasets):
        df = args.datasets[dfname]

        heightvalues = df['height'].unique()
        timevalues = mdates.date2num(df.index.unique().values) # Convert to days since 0001-01-01 00:00 UTC, plus one
        Ts,Zs = np.meshgrid(timevalues,heightvalues,indexing='xy')

        # Create list with available fields only
        available_fields = args.get_available_fields(dfname)

        # Pivot all fields in a dataset at once
        df_pivot = df.pivot(columns='height',values=available_fields)

        for j, field in enumerate(fields):
            # Skip loop if field not available
            if not field in available_fields:
                print('Warning: field "'+field+'" not available in dataset '+dfname)
                continue

            # Store plotting options in dictionary
            plotting_properties = {
                'vmin': args.fieldlimits[field][0],
                'vmax': args.fieldlimits[field][1],
                'cmap': args.cmap[field]
                }

            # Index of axis corresponding to dataset i and field j
            axi = i*nfields + j

            # Extract data from dataframe
            fieldvalues = df_pivot[field].values 

            # Gather label, color, general options and dataset-specific options
            # (highest priority to dataset-specific options, then general options)
            try:
                plotting_properties = {**plotting_properties,**kwargs,**datasetkwargs[dfname]}
            except KeyError:
                plotting_properties = {**plotting_properties,**kwargs}

            # Plot data
            im = axv[axi].pcolormesh(Ts,Zs,fieldvalues.T,**plotting_properties)

            # Colorbar mark up
            if showcolorbars:
                cbar = fig.colorbar(im,ax=axv[axi],shrink=1.0)
                # Set field label if known
                try:
                    cbar.set_label(args.fieldlabels[field])
                except KeyError:
                    pass
                # Save colorbar
                cbars.append(cbar)

            # Set title if more than one dataset
            if ndatasets>1:
                axv[axi].set_title(dfname,fontsize=16)



    # Axis mark up
    axv[-1].xaxis_date()
    axv[-1].xaxis.set_minor_locator(mdates.HourLocator(byhour=range(24),interval=6))
    axv[-1].xaxis.set_minor_formatter(mdates.DateFormatter('%H%M'))
    axv[-1].xaxis.set_major_locator(mdates.DayLocator())
    axv[-1].xaxis.set_major_formatter(mdates.DateFormatter('\n%Y-%m-%d'))
    for axi in axv[(nrows-1)*ncols:]:
        axi.set_xlabel(r'UTC time')

    # Set time and height limits if specified
    if not timelimits is None:
        axv[-1].set_xlim(timelimits)
    if not heightlimits is None:
        axv[-1].set_ylim(heightlimits)

    # Add y labels
    for axi in axv: 
        axi.set_ylabel(r'Height [m]')
    
    # Number sub figures as a, b, c, ...
    if labelsubplots and axv.size > 1:
        for i,axi in enumerate(axv):
            axi.text(-0.14,1.0,'('+chr(i+97)+')',transform=axi.transAxes,size=16)

    return fig, ax, cbars


def plot_timehistory_at_height(datasets,
                               fields,
                               heights,
                               fig=None,ax=None,
                               fieldlimits={},
                               timelimits=None,
                               fieldlabels={},
                               colormap=None,
                               stack_by_datasets=None,
                               labelsubplots=False,
                               ncols=1,
                               subfigsize=(12,3),
                               datasetkwargs={},
                               **kwargs
                               ):
    """
    Plot time history at specified height(s) for various dataset(s)
    and/or field(s).
    
    By default, data for multiple datasets or multiple heights are
    stacked in a single subplot. When multiple datasets and multiple
    heights are specified together, heights are stacked in a subplot
    per field and per dataset.

    Usage
    =====
    datasets : pandas.DataFrame or dict 
        Dataset(s). If more than one set, datasets should
        be a dictionary with entries <dataset_name>: dataset
    fields : str or list
        Fieldname(s) corresponding to particular column(s) of
        the datasets
    heights : float or list
        Height(s) for which time history is plotted
    fig : figure handle
        Custom figure handle. Should be specified together with ax
    ax : axes handle, or list or numpy ndarray with axes handles
        Customand axes handle(s).
        Size of ax should equal nfields * (ndatasets or nheights)
    fieldlimits : list or tuple, or dict
        Value range for the various fields. If only one field is 
        plotted, fieldlimits can be a list or tuple. Otherwise, it
        should be a dictionary with entries <fieldname>: fieldlimit.
        Missing fieldlimits are set automatically
    timelimits : list or tuple
        Time axis limits
    fieldlabels : str or dict
        Custom field labels. If only one field is plotted, fieldlabels
        can be a string. Otherwise it should be a dictionary with
        entries <fieldname>: fieldlabel
    colormap : str
        Colormap used when stacking heights
    stack_by_datasets : bool
        Stack by datasets if True, otherwise stack by heights
    labelsubplots : bool
        Label subplots as (a), (b), (c), ...
    ncols : int
        Number of columns in axes grid, must be a true divisor of total
        number of axes.
    subfigsize : list or tuple
        Standard size of subfigures
    datasetkwargs : dict
        Dataset-specific options that are passed on to the actual
        plotting function. These options overwrite general options
        specified through **kwargs. The argument should be a dictionary
        with entries <dataset_name>: {**kwargs}
    **kwargs : other keyword arguments
        Options that are passed on to the actual plotting function.
        Note that these options should be the same for all datasets,
        fields and heights, and they can not be used to set dataset,
        field or height specific colors, limits, etc.
        Example uses include setting linestyle/width, marker, etc.
    """
    # Avoid FutureWarning concerning the use of an implicitly registered
    # datetime converter for a matplotlib plotting method. The converter
    # was registered by pandas on import. Future versions of pandas will
    # require explicit registration of matplotlib converters, as done here.
    from pandas.plotting import register_matplotlib_converters
    register_matplotlib_converters()

    args = PlottingInput(
        datasets=datasets,
        fields=fields,
        heights=heights,
        fieldlimits=fieldlimits,
        fieldlabels=fieldlabels,
    )

    nfields = len(args.fields)
    nheights = len(args.heights)
    ndatasets = len(args.datasets)

    # Concatenate custom and standard field labels
    # (custom field labels overwrite standard fields labels if existent)
    args.fieldlabels = {**standard_fieldlabels, **args.fieldlabels}

    # Set up subplot grid
    if stack_by_datasets is None:
        if nheights>1:
            stack_by_datasets = False
        else:
            stack_by_datasets = True

    if stack_by_datasets:
        ntotal = nfields*nheights
    else:
        ntotal = nfields*ndatasets

    fig, ax, nrows, ncols = _create_subplots_if_needed(
                                    ntotal,
                                    ncols,
                                    sharex=True,
                                    subfigsize=subfigsize,
                                    fig=fig,
                                    ax=ax
                                    )

    # Create flattened view of axes
    axv = np.asarray(ax).reshape(-1)

    # Loop over datasets and fields 
    for i,dfname in enumerate(args.datasets):
        df = args.datasets[dfname]
        timevalues = df.index.unique()
        if isinstance(timevalues, pd.TimedeltaIndex):
            timevalues = timevalues.total_seconds()
        heightvalues = df['height'].unique()

        # Create list with available fields only
        available_fields = args.get_available_fields(dfname)

        # If any of the requested heights is not available,
        # pivot the dataframe to allow interpolation.
        # Pivot all fields in a dataset at once to reduce computation time
        if not all([h in heightvalues for h in args.heights]):
            df_pivot = df.pivot(columns='height',values=available_fields)
            print('Pivoting '+dfname)

        for j, field in enumerate(args.fields):
            # Skip loop if field not available
            if not field in available_fields:
                print('Warning: field "'+field+'" not available in dataset '+dfname)
                continue


            for k, height in enumerate(args.heights):
                # Store plotting options in dictionary
                # Set default linestyle to '-' and no markers
                plotting_properties = {
                    'linestyle':'-',
                    'marker':None,
                    }

                # Axis order, label and title depend on value of stack_by_datasets 
                if stack_by_datasets:
                    # Index of axis corresponding to field j and height k
                    axi = k*nfields + j

                    # Use datasetname as label
                    plotting_properties['label'] = dfname

                    # Set title if multiple heights are compared
                    if nheights>1:
                        axv[axi].set_title('z = {:.1f} m'.format(height),fontsize=16)

                    # Set colors
                    plotting_properties['color'] = default_colors[i]
                else:
                    # Index of axis corresponding to field j and dataset i 
                    axi = i*nfields + j

                    # Use height as label
                    plotting_properties['label'] = 'z = {:.1f} m'.format(height)

                    # Set title if multiple datasets are compared
                    if ndatasets>1:
                        axv[axi].set_title(dfname,fontsize=16)

                    # Set colors
                    if colormap is not None:
                        cmap = mpl.cm.get_cmap(colormap)
                        plotting_properties['color'] = cmap(k/(nheights-1))
                    else:
                        plotting_properties['color'] = default_colors[k]

                # Extract data from dataframe
                if height in heightvalues:
                    signal = df.loc[df.height==height,field].values
                else:
                    signal = interp1d(heightvalues,df_pivot[field].values,axis=1,fill_value="extrapolate")(height)
                
                # Gather label, color, general options and dataset-specific options
                # (highest priority to dataset-specific options, then general options)
                try:
                    plotting_properties = {**plotting_properties,**kwargs,**datasetkwargs[dfname]}
                except KeyError:
                    plotting_properties = {**plotting_properties,**kwargs}
                
                # Plot data
                axv[axi].plot(timevalues,signal,**plotting_properties)

                # Set field label if known
                try:
                    axv[axi].set_ylabel(args.fieldlabels[field])
                except KeyError:
                    pass
                # Set field limits if specified
                try:
                    axv[axi].set_ylim(args.fieldlimits[field])
                except KeyError:
                    pass
   
    # Set axis grid
    for axi in axv:
        axi.xaxis.grid(True,which='minor')
        axi.yaxis.grid()
    
    # Format time axis
    if isinstance(timevalues, (pd.DatetimeIndex, pd.TimedeltaIndex)):
        axv[-1].xaxis_date()
        axv[-1].xaxis.set_minor_locator(mdates.HourLocator(byhour=range(24),interval=6))
        axv[-1].xaxis.set_minor_formatter(mdates.DateFormatter('%H%M'))
        axv[-1].xaxis.set_major_locator(mdates.DayLocator())
        axv[-1].xaxis.set_major_formatter(mdates.DateFormatter('\n%Y-%m-%d'))
        tstr = 'UTC time'
    else:
        tstr = 'time [s]'

    for axi in axv[(nrows-1)*ncols:]:
        axi.set_xlabel(tstr)

    # Set time limits if specified
    if not timelimits is None:
        axv[-1].set_xlim(timelimits)

    # Number sub figures as a, b, c, ...
    if labelsubplots and axv.size > 1:
        for i,axi in enumerate(axv):
            axi.text(-0.14,1.0,'('+chr(i+97)+')',transform=axi.transAxes,size=16)

    # Add legend if more than one entry
    if (stack_by_datasets and ndatasets>1) or (not stack_by_datasets and nheights>1):
        leg = axv[ncols-1].legend(loc='upper left',bbox_to_anchor=(1.05,1.0),fontsize=16)

    return fig, ax


def plot_profile(datasets,
                 fields,
                 times,
                 fig=None,ax=None,
                 fieldlimits={},
                 heightlimits=None,
                 fieldlabels={},
                 colormap=None,
                 stack_by_datasets=None,
                 labelsubplots=False,
                 fieldorder='C',
                 ncols=None,
                 subfigsize=(4,5),
                 datasetkwargs={},
                 **kwargs
                ):
    """
    Plot vertical profile at specified time(s) for various dataset(s)
    and/or field(s).

    By default, data for multiple datasets or multiple times are
    stacked in a single subplot. When multiple datasets and multiple
    times are specified together, times are stacked in a subplot
    per field and per dataset.

    Usage
    =====
    datasets : pandas.DataFrame or dict 
        Dataset(s). If more than one set, datasets should
        be a dictionary with entries <dataset_name>: dataset
    fields : str or list
        Fieldname(s) corresponding to particular column(s) of
        the datasets
    times : str, int, float, list
        Time(s) for which vertical profiles are plotted, specified as
        either datetime strings or numerical values (seconds, e.g.,
        simulation time).
    fig : figure handle
        Custom figure handle. Should be specified together with ax
    ax : axes handle, or list or numpy ndarray with axes handles
        Customand axes handle(s).
        Size of ax should equal nfields * (ndatasets or ntimes)
    fieldlimits : list or tuple, or dict
        Value range for the various fields. If only one field is 
        plotted, fieldlimits can be a list or tuple. Otherwise, it
        should be a dictionary with entries <fieldname>: fieldlimit.
        Missing fieldlimits are set automatically
    heightlimits : list or tuple
        Height axis limits
    fieldlabels : str or dict
        Custom field labels. If only one field is plotted, fieldlabels
        can be a string. Otherwise it should be a dictionary with
        entries <fieldname>: fieldlabel
    colormap : str
        Colormap used when stacking times
    stack_by_datasets : bool
        Stack by datasets if True, otherwise stack by times
    labelsubplots : bool
        Label subplots as (a), (b), (c), ...
    fieldorder : 'C' or 'F'
        Index ordering for assigning fields and datasets/times (depending
        on stack_by_datasets) to axes grid (row by row). Fields is considered the
        first axis, so 'C' means fields change slowest, 'F' means fields
        change fastest.
    ncols : int
        Number of columns in axes grid, must be a true divisor of total
        number of axes.
    subfigsize : list or tuple
        Standard size of subfigures
    datasetkwargs : dict
        Dataset-specific options that are passed on to the actual
        plotting function. These options overwrite general options
        specified through **kwargs. The argument should be a dictionary
        with entries <dataset_name>: {**kwargs}
    **kwargs : other keyword arguments
        Options that are passed on to the actual plotting function.
        Note that these options should be the same for all datasets,
        fields and times, and they can not be used to set dataset,
        field or time specific colors, limits, etc.
        Example uses include setting linestyle/width, marker, etc.
    """

    args = PlottingInput(
        datasets=datasets,
        fields=fields,
        times=times,
        fieldlimits=fieldlimits,
        fieldlabels=fieldlabels,
        fieldorder=fieldorder,
    )

    nfields = len(args.fields)
    ntimes = len(args.times)
    ndatasets = len(args.datasets)

    # Concatenate custom and standard field labels
    # (custom field labels overwrite standard fields labels if existent)
    args.fieldlabels = {**standard_fieldlabels, **args.fieldlabels}

    # Set up subplot grid
    if stack_by_datasets is None:
        if ntimes>1:
            stack_by_datasets = False
        else:
            stack_by_datasets = True

    if stack_by_datasets:
        ntotal = nfields * ntimes
    else:
        ntotal = nfields * ndatasets

    fig, ax, nrows, ncols = _create_subplots_if_needed(
                                    ntotal,
                                    ncols,
                                    default_ncols=int(ntotal/nfields),
                                    fieldorder=args.fieldorder,
                                    avoid_single_column=True,
                                    sharey=True,
                                    subfigsize=subfigsize,
                                    wspace=0.2,
                                    fig=fig,
                                    ax=ax,
                                    )

    # Create flattened view of axes
    axv = np.asarray(ax).reshape(-1)

    # Loop over datasets, fields and times 
    for i, dfname in enumerate(args.datasets):
        df = args.datasets[dfname]
        heightvalues = df['height'].unique()

        # Create list with available fields only
        available_fields = args.get_available_fields(dfname)

        # Pivot all fields in a dataset at once
        df_pivot = df.pivot(columns='height',values=available_fields)

        for j, field in enumerate(args.fields):
            # Skip loop if field not available
            if not field in available_fields:
                print('Warning: field "'+field+'" not available in dataset '+dfname)
                continue

            for k, time in enumerate(args.times):
                plotting_properties = {}

                # Axis order, label and title depend on value of stack_by_datasets 
                if stack_by_datasets:
                    # Index of axis corresponding to field j and time k
                    if args.fieldorder == 'C':
                        axi = j*ntimes + k
                    else:
                        axi = k*nfields + j

                    # Use datasetname as label
                    plotting_properties['label'] = dfname

                    # Set title if multiple times are compared
                    if ntimes>1:
                        if isinstance(time, (int,float,np.number)):
                            tstr = '{:g} s'.format(time)
                        else:
                            tstr = pd.to_datetime(time).strftime('%Y-%m-%d %H%M UTC')
                        axv[axi].set_title(tstr, fontsize=16)

                    # Set color
                    plotting_properties['color'] = default_colors[i]
                else:
                    # Index of axis corresponding to field j and dataset i
                    if args.fieldorder == 'C':
                        axi = j*ndatasets + i
                    else:
                        axi = i*nfields + j
                    
                    # Use time as label
                    if isinstance(time, (int,float,np.number)):
                        plotting_properties['label'] = '{:g} s'.format(time)
                    else:
                        plotting_properties['label'] = pd.to_datetime(time).strftime('%Y-%m-%d %H%M UTC')

                    # Set title if multiple datasets are compared
                    if ndatasets>1:
                        axv[axi].set_title(dfname,fontsize=16)

                    # Set colors
                    if colormap is not None:
                        cmap = mpl.cm.get_cmap(colormap)
                        plotting_properties['color'] = cmap(k/(ntimes-1))
                    else:
                        plotting_properties['color'] = default_colors[k]
                
                # Extract data from dataframe
                fieldvalues = df_pivot[field].loc[time].values.squeeze()

                # Gather label, color, general options and dataset-specific options
                # (highest priority to dataset-specific options, then general options)
                try:
                    plotting_properties = {**plotting_properties,**kwargs,**datasetkwargs[dfname]}
                except KeyError:
                    plotting_properties = {**plotting_properties,**kwargs}

                # Plot data
                axv[axi].plot(fieldvalues,heightvalues,**plotting_properties)

                # Set field label if known
                try:
                    axv[axi].set_xlabel(args.fieldlabels[field])
                except KeyError:
                    pass
                # Set field limits if specified
                try:
                    axv[axi].set_xlim(args.fieldlimits[field])
                except KeyError:
                    pass
    
    for axi in axv:
        axi.grid(True,which='both')

    # Set height limits if specified
    if not heightlimits is None:
        axv[0].set_ylim(heightlimits)

    # Add y labels
    for r in range(nrows): 
        axv[r*ncols].set_ylabel(r'Height [m]')
    
    # Number sub figures as a, b, c, ...
    if labelsubplots and axv.size > 1:
        for i,axi in enumerate(axv):
            axi.text(-0.14,-0.18,'('+chr(i+97)+')',transform=axi.transAxes,size=16)
    
    # Add legend if more than one entry
    if (stack_by_datasets=='datasets' and ndatasets>1) or (stack_by_datasets=='times' and ntimes>1):
        leg = axv[ncols-1].legend(loc='upper left',bbox_to_anchor=(1.05,1.0),fontsize=16)

    return fig,ax


def plot_spectrum(datasets,
                  height,
                  fields,
                  times,
                  fig=None,ax=None,
                  Tperiod=3600.0,
                  Tsegment=600.0,
                  fieldlimits={},
                  freqlimits=None,
                  fieldlabels={},
                  labelsubplots=False,
                  ncols=None,
                  subfigsize=(4,5),
                  datasetkwargs={},
                  **kwargs
                  ):
    """
    Plot frequency spectrum at a given height for different datasets,
    times and fields, using a subplot per time and per field

    The frequency spectrum is computed using scipy.signal.welch, which
    estimates the power spectral density by dividing the data into over-
    lapping segments, computing a modified periodogram for each segment
    and averaging the periodograms.

    Usage
    =====
    datasets : pandas.DataFrame or dict 
        Dataset(s). If more than one set, datasets should
        be a dictionary with entries <dataset_name>: dataset
    height : float
        Height for which frequency spectrum is plotted
    fields : str or list
        Fieldname(s) corresponding to particular column(s) of
        the datasets
    times : str, list
        Start time(s) of the time period(s) for which the frequency
        spectrum is computed.
    fig : figure handle
        Custom figure handle. Should be specified together with ax
    ax : axes handle, or list or numpy ndarray with axes handles
        Customand axes handle(s).
        Size of ax should equal nfields * ntimes
    Tperiod : float
        Length of the time period in seconds over which frequency
        spectrum is computed.
    Tsegment : float
        Length of time segments of the welch method in seconds
    fieldlimits : list or tuple, or dict
        Value range for the various fields. If only one field is 
        plotted, fieldlimits can be a list or tuple. Otherwise, it
        should be a dictionary with entries <fieldname>: fieldlimit.
        Missing fieldlimits are set automatically
    freqlimits : list or tuple
        Frequency axis limits
    fieldlabels : str or dict
        Custom field labels. If only one field is plotted, fieldlabels
        can be a string. Otherwise it should be a dictionary with
        entries <fieldname>: fieldlabel
    labelsubplots : bool
        Label subplots as (a), (b), (c), ...
    ncols : int
        Number of columns in axes grid, must be a true divisor of total
        number of axes.
    subfigsize : list or tuple
        Standard size of subfigures
    datasetkwargs : dict
        Dataset-specific options that are passed on to the actual
        plotting function. These options overwrite general options
        specified through **kwargs. The argument should be a dictionary
        with entries <dataset_name>: {**kwargs}
    **kwargs : other keyword arguments
        Options that are passed on to the actual plotting function.
        Note that these options should be the same for all datasets,
        fields and times, and they can not be used to set dataset,
        field or time specific colors, limits, etc.
        Example uses include setting linestyle/width, marker, etc.
    """

    args = PlottingInput(
        datasets=datasets,
        fields=fields,
        times=times,
        fieldlimits=fieldlimits,
        fieldlabels=fieldlabels,
    )

    nfields = len(args.fields)
    ntimes = len(args.times)
    ndatasets = len(args.datasets)
    ntotal = nfields * ntimes

    # Concatenate custom and standard field labels
    # (custom field labels overwrite standard fields labels if existent)
    args.fieldlabels = {**standard_spectrumlabels, **args.fieldlabels}

    fig, ax, nrows, ncols = _create_subplots_if_needed(
                                    ntotal,
                                    ncols,
                                    default_ncols=ntimes,
                                    avoid_single_column=True,
                                    sharex=True,
                                    subfigsize=subfigsize,
                                    wspace=0.3,
                                    hspace=0.5,
                                    fig=fig,
                                    ax=ax,
                                    )

    # Create flattened view of axes
    axv = np.asarray(ax).reshape(-1)

    # Loop over datasets, fields and times 
    for j, dfname in enumerate(args.datasets):
        df = args.datasets[dfname]

        heightvalues = df['height'].unique()
        timevalues   = df.index.unique()
        dt = (timevalues[1]-timevalues[0]) / pd.Timedelta(1,unit='s')     #Sampling rate in seconds

        # Create list with available fields only
        available_fields = args.get_available_fields(dfname)

        # Pivot all fields of a dataset at once
        df_pivot = df.pivot(columns='height',values=available_fields)

        for k, field in enumerate(args.fields):
            # Skip loop if field not available
            if not field in available_fields:
                print('Warning: field "'+field+'" not available in dataset '+dfname)
                continue

            for i, tstart in enumerate(args.times):
                plotting_properties = {'label':dfname}

                # Index of axis corresponding to field k and time i
                axi = k*ntimes + i
                
                # Axes mark up
                if j==0:
                    axv[axi].set_title(pd.to_datetime(tstart).strftime('%Y-%m-%d %H%M UTC'),fontsize=16)

                # Compute frequency spectrum
                istart = np.where(timevalues==pd.to_datetime(tstart))[0][0]
                signal = interp1d(heightvalues,df_pivot[field].interpolate(method='linear').values,axis=1,fill_value="extrapolate")(height)
                f, P = welch(signal[istart:istart+np.int(Tperiod/dt)],fs=1./dt,nperseg=np.int(Tsegment/dt),
                            detrend='linear',window='hanning',scaling='density')
                
                # Gather label, general options and dataset-specific options
                # (highest priority to dataset-specific options, then general options)
                try:
                    plotting_properties = {**plotting_properties,**kwargs,**datasetkwargs[dfname]}
                except KeyError:
                    plotting_properties = {**plotting_properties,**kwargs}

                # Plot data
                axv[axi].loglog(f[1:],P[1:],**plotting_properties)
   

    # Set frequency label
    for c in range(ncols):
        axv[ncols*(nrows-1)+c].set_xlabel('f [Hz]')

    # Specify field label and field limits if specified 
    for r in range(nrows):
        try:
            axv[r*ncols].set_ylabel(fieldlabels[fields[r]])
        except KeyError:
            pass
        try:
            axv[r*ncols].set_ylim(fieldlimits[fields[r]])
        except KeyError:
            pass

    # Set frequency limits if specified
    if not freqlimits is None:
        axv[0].set_xlim(freqlimits)

    # Number sub figures as a, b, c, ...
    if labelsubplots and axv.size > 1:
        for i,axi in enumerate(axv):
            axi.text(-0.14,-0.18,'('+chr(i+97)+')',transform=axi.transAxes,size=16)

    # Add legend if more than one dataset
    if ndatasets>1:
        leg = axv[ncols-1].legend(loc='upper left',bbox_to_anchor=(1.05,1.0))

    return fig, ax
