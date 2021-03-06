#
#  Module for applying flat fielding
#

from __future__ import division

import math
import numpy as np
import logging
from .. import datamodels
from .. datamodels import dqflags
from .. assign_wcs import nirspec       # for NIRSpec IFU data

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

MICRONS_100 = 1.e-4                     # 100 microns, in meters

# This is for NIRSpec.  These exposure types are all fixed-slit modes.
FIXED_SLIT_TYPES = ["NRS_LAMP", "NRS_BRIGHTOBJ", "NRS_FIXEDSLIT"]

def do_correction(input_model, flat_model,
                  f_flat_model, s_flat_model,
                  d_flat_model, flat_suffix=None):
    """
    Short Summary
    -------------
    Flat-field a JWST data model using a flat-field model

    Parameters
    ----------
    input_model: JWST data model
        Input science data model to be flat-fielded.

    flat_model: JWST data model
        Data model containing flat-field for all instruments other than
        NIRSpec spectrographic data.

    f_flat_model: NirspecFlatModel or NirspecQuadFlatModel object
        Flat field for the fore optics.  Used only for NIRSpec data.

    s_flat_model: NirspecFlatModel object
        Flat field for the spectrograph.  Used only for NIRSpec data.

    d_flat_model: NirspecFlatModel object
        Flat field for the detector.  Used only for NIRSpec data.

    flat_suffix: str or None
        Filename suffix for optional output file to save flat field images.
        Note that this is only supported for NIRSpec spectrographic data.

    Returns
    -------
    output_model, interpolated_flats
        output_model is the data model for the flat-fielded science data.
        interpolated_flats may be None, or it may be a MultiSlitModel
        containing the interpolated flat fields (NIRSpec data only).
    """

    # Initialize the output model as a copy of the input
    output_model = input_model.copy()

    # NIRSpec spectrographic data are processed differently from other
    # types of data (including NIRSpec imaging).
    is_NRS_spectrographic = (input_model.meta.instrument.name == 'NIRSPEC' and
                             f_flat_model is not None)

    if is_NRS_spectrographic:
        interpolated_flats = do_NIRSpec_flat_field(output_model,
                                                   f_flat_model, s_flat_model,
                                                   d_flat_model, flat_suffix)
    else:
        if flat_suffix is not None:
            log.warning("The flat_suffix parameter is not implemented "
                        "for this mode; will be ignored.")
        do_flat_field(output_model, flat_model)
        interpolated_flats = None

    return (output_model, interpolated_flats)

#
# These functions are for non-NIRSpec flat fielding, or for NIRSpec imaging.
#
def do_flat_field(output_model, flat_model):
    """
    Short Summary
    -------------
    Apply flat-fielding for non-NIRSpec modes, updating the output model.

    Parameters
    ----------
    output_model: JWST data model
        flat-fielded input science data model, modified in-place

    flat_model: JWST data model
        data model containing flat-field

    Returns
    -------
    None
    """

    if output_model.meta.instrument.name == "NIRSPEC":
        log.debug("Flat field correction for NIRSpec imaging data.")
    else:
        log.debug("Flat field correction for non-NIRSpec modes.")

    any_updated = False # will set True if any flats applied

    # Check to see if flat data array is smaller than science data
    if (output_model.data.shape[-1] > flat_model.data.shape[-1]) or \
       (output_model.data.shape[-2] > flat_model.data.shape[-2]):
        log.warning('Reference data array is smaller than science data')
        log.warning('Step will be skipped')

    # Apply flat to MultiSlits
    elif isinstance(output_model, datamodels.MultiSlitModel):

        # Apply flat to each slit contained in the input
        for slit in output_model.slits:
            log.debug('Applying flat to slit %s' % (slit.name))
            apply_flat_field(slit, flat_model)
            any_updated = True

    # Apply flat to all other models
    else:
        apply_flat_field(output_model, flat_model)
        any_updated = True

    if any_updated:
        output_model.meta.cal_step.flat_field = 'COMPLETE'
    else:
        output_model.meta.cal_step.flat_field = 'SKIPPED'


def apply_flat_field(science, flat):
    """
    Short Summary
    -------------
    Flat fields the data and error arrays, and updates data quality array
    based on bad pixels in flat field arrays. Applies portion of flat field
    corresponding to science image subarray.

    Parameters
    ----------
    science: JWST data model
        input science data model

    flat: JWST data model
        flat field data model

    Returns
    -------
    None
    """

    # If the input science data model is a subarray, extract the same
    # subarray from the flatfield model
    if ref_matches_sci(flat, science):
        flat_data = flat.data
        flat_dq = flat.dq
    else:
        log.info("Extracting matching subarray from flat")
        flat_data = get_subarray(flat.data, science)
        flat_dq = get_subarray(flat.dq, science)

    # For pixels whose flat is either NaN or NO_FLAT_FIELD, update their DQ to
    # indicate that no flat is applied to those pixels
    flat_dq[np.isnan(flat_data)] = np.bitwise_or(flat_dq[np.isnan(flat_data)],
                                                 dqflags.pixel['NO_FLAT_FIELD'])

    # Replace NaN's in flat with 1's
    flat_data[np.isnan(flat_data)] = 1.0

    # Reset flat values of pixels having DQ values containing NO_FLAT_FIELD
    # to 1.0, so that no flat fielding correction is made
    wh_dq = np.bitwise_and(flat_dq, dqflags.pixel['NO_FLAT_FIELD'])
    flat_data[wh_dq == dqflags.pixel['NO_FLAT_FIELD']] = 1.0

    # For GuiderCalModel data, only apply flat to science data array;
    # there isn't an error array.
    if isinstance(science, datamodels.GuiderCalModel):
            # Flatten data array
            science.data /= flat_data
            # Combine the science and flat DQ arrays
            science.dq = np.bitwise_or(science.dq, flat_dq)

    # For CubeModel science data, apply flat to each integration
    elif isinstance(science, datamodels.CubeModel):
        for integ in range(science.data.shape[0]):
            # Flatten data and error arrays
            science.data[integ] /= flat_data
            science.err[integ] /= flat_data
            # Combine the science and flat DQ arrays
            science.dq[integ] = np.bitwise_or(science.dq[integ], flat_dq)

    # For 2D ImageModel science data, apply flat to entire arrays
    else:
        # Flatten data and error arrays
        science.data /= flat_data
        science.err /= flat_data

        # Combine the science and flat DQ arrays
        science.dq = np.bitwise_or(science.dq, flat_dq)


def ref_matches_sci(ref_model, sci_model):
    """
    Short Summary
    -------------
    Check if the science model has the same subarray parameters as the
    reference model.

    Parameters
    ----------
    ref_model: JWST data model
        data model containing flat-field

    sci_model: JWST data model
        input science data model to be flat-fielded

    Returns
    -------
    True if the science model has the same subarray parameters as the
    reference model, False otherwise.

    """
    # Get the science model subarray parameters
    try:
        sxstart = sci_model.xstart
        sxsize = sci_model.xsize
        systart = sci_model.ystart
        sysize = sci_model.ysize
    except:
        sxstart = sci_model.meta.subarray.xstart
        sxsize = sci_model.meta.subarray.xsize
        systart = sci_model.meta.subarray.ystart
        sysize = sci_model.meta.subarray.ysize

    # Get the flat model subarray parameters
    rxstart = ref_model.meta.subarray.xstart
    rxsize = ref_model.meta.subarray.xsize
    rystart = ref_model.meta.subarray.ystart
    rysize = ref_model.meta.subarray.ysize

    if rxstart is None:
        rxstart = 1
    if rxsize is None:
        rxsize = ref_model.data.shape[-1]
    if rystart is None:
        rystart = 1
    if rysize is None:
        rysize = ref_model.data.shape[-2]

    log.debug(' sci xstart=%d, xsize=%d', sxstart, sxsize)
    log.debug(' sci ystart=%d, ysize=%d', systart, sysize)
    log.debug(' ref xstart=%d, xsize=%d', rxstart, rxsize)
    log.debug(' ref ystart=%d, ysize=%d', rystart, rysize)

    # See if they match the reference model subarray parameters
    if (rxstart == sxstart and rxsize == sxsize and
        rystart == systart and rysize == sysize):
        return True
    else:
        return False


def get_subarray(input_array, sci_model):
    """
    Short Summary
    -------------
    Return the slice from the input array using the subarray parameters of the
    science model.

    Parameters
    ----------
    input_array: 2D numpy array
        input array from which a subarray is extracted

    sci_model: JWST data model
        input science data model

    Returns
    -------
    A slice: 2D numpy array
        slice from the input array
    """

    # Get the science model subarray parameters
    try:
        xstart = sci_model.xstart
        xsize = sci_model.xsize
        ystart = sci_model.ystart
        ysize = sci_model.ysize
    except:
        xstart = sci_model.meta.subarray.xstart
        xsize = sci_model.meta.subarray.xsize
        ystart = sci_model.meta.subarray.ystart
        ysize = sci_model.meta.subarray.ysize

    # Compute the slicing indexes
    xstart = xstart - 1
    xstop = xstart + xsize
    ystart = ystart - 1
    ystop = ystart + ysize

    # Return the slice from the input array
    return input_array[ystart:ystop, xstart:xstop]


#
# The following functions are for NIRSpec spectrographic data.
#
def do_NIRSpec_flat_field(output_model,
                          f_flat_model, s_flat_model,
                          d_flat_model, flat_suffix):
    """
    Short Summary
    -------------
    Apply flat-fielding for NIRSpec data, updating the output model.

    Parameters
    ----------
    output_model: JWST data model
        Science data model, modified (flat fielded) in-place.

    f_flat_model: NirspecFlatModel or NirspecQuadFlatModel object
        Flat field for the fore optics.

    s_flat_model: NirspecFlatModel object
        Flat field for the spectrograph.

    d_flat_model: NirspecFlatModel object
        Flat field for the detector.

    flat_suffix: str or None
        Filename suffix for optional output file to save the interpolated
        flat field images.  If not None, a file will be written (later, not
        by the current function).

    Returns
    -------
    MultiSlitModel, ImageModel (for IFU data), or None
        If not None, the value will be the interpolated flat fields.
    """

    log.debug("Flat field correction for NIRSpec spectrographic data.")

    exposure_type = output_model.meta.exposure.type

    # We expect NIRSpec IFU data to be an ImageModel, but it's conceivable
    # that the slices have been copied out into a MultiSlitModel, so
    # check for that case.
    if not hasattr(output_model, "slits"):
        if exposure_type == "NRS_IFU":
            if not isinstance(output_model, datamodels.ImageModel):
                log.error("NIRSpec IFU data is not an ImageModel; "
                          "don't know how to process it.")
                raise RuntimeError("Input is {}; expected ImageModel"
                                   .format(type(output_model)))
            return NIRSpec_IFU(output_model,
                               f_flat_model, s_flat_model,
                               d_flat_model, flat_suffix)

    # Create an output model for the interpolated flat fields.
    if flat_suffix is not None:
        interpolated_flats = datamodels.MultiSlitModel()
        interpolated_flats.update(output_model, only="PRIMARY")
    else:
        interpolated_flats = None

    any_updated = False
    if exposure_type == "NRS_MSASPEC":
        # This is not the same as output_model.slits; `slits` will be
        # used a few lines farther down.
        slits = nirspec.get_open_slits(output_model)
    for (k, slit) in enumerate(output_model.slits):
        log.info("Processing slit %s", slit.name)
        slit_nt = None
        if exposure_type == "NRS_MSASPEC":
            # Find this slit in the list of open slits.
            for j in range(len(slits)):
                if str(slits[j].name) == slit.name:
                    slit_nt = slits[j]
                    break
            if slit_nt is None:
                log.error("Couldn't find slit %s in list of open slits; "
                          "skipping ...", slit.name)
                continue

        # pixels with respect to the original image
        ysize, xsize = slit.data.shape
        xstart = slit.xstart - 1
        ystart = slit.ystart - 1
        xstop = xstart + xsize
        ystop = ystart + ysize

        # Make sure there is a WCS.
        if not hasattr(slit.meta, "wcs") or slit.meta.wcs is None:
            log.error("Slit %s does not have a 'wcs' attribute.", slit.name)
            if output_model.meta.cal_step.assign_wcs == 'COMPLETE':
                raise RuntimeError("WCS was not found, but it isn't clear "
                                   "why not.")
            else:
                raise RuntimeError("The assign_wcs step has not been run.")

        # Get the wavelength of each pixel in the extracted slit data.
        # pixels with respect to the cutout
        grid = np.indices((ysize, xsize), dtype=np.float64)
        # The arguments are the X and Y pixel coordinates (in that order).
        (ra, dec, wl) = slit.meta.wcs(grid[1], grid[0])
        del ra, dec, grid
        nan_mask = np.isnan(wl)
        good_mask = np.logical_not(nan_mask)
        sum_nan_mask = nan_mask.sum(dtype=np.intp)
        sum_good_mask = good_mask.sum(dtype=np.intp)
        if sum_nan_mask > 0:
            log.debug("Number of NaNs in sci wavelength array = %s out of %s",
                      sum_nan_mask, sum_nan_mask + sum_good_mask)
            if sum_good_mask < 1:
                log.warning("(all are NaN)")
            # Replace NaNs with a harmless but out-of-bounds value.
            wl[nan_mask] = -1000.
        if wl.max() > 0. and wl.max() < MICRONS_100:
            log.warning("Wavelengths in SCI data appear to be in meters.")

        # Combine the three flat fields for the current subarray.
        (flat_2d, flat_dq_2d) = create_flat_field(wl,
                        f_flat_model, s_flat_model, d_flat_model,
                        xstart, xstop, ystart, ystop,
                        exposure_type, slit.name, slit_nt)
        mask = (flat_2d <= 0.)
        nbad = mask.sum(dtype=np.intp)
        if nbad > 0:
            log.debug("%d flat-field values <= 0", nbad)
            flat_2d[mask] = 1.
        del mask

        if flat_suffix is not None:
            # Save flat_2d and flat_dq_2d for an output file.
            new_flat = datamodels.ImageModel(data=flat_2d, dq=flat_dq_2d)
            interpolated_flats.slits.append(new_flat.copy())
            interpolated_flats.slits[k].err[...] = 1.   # xxx not realistic
            # xxx There's more info that could be copied over.
            interpolated_flats.slits[k].name = slit.name
            interpolated_flats.slits[k].xstart = slit.xstart
            interpolated_flats.slits[k].xsize = slit.xsize
            interpolated_flats.slits[k].ystart = slit.ystart
            interpolated_flats.slits[k].ysize = slit.ysize
            # Copy the WCS info from output (same as input).
            interpolated_flats.slits[k].meta.wcs = \
                  output_model.slits[k].meta.wcs

        slit.data /= flat_2d
        slit.err /= flat_2d
        slit.dq |= flat_dq_2d.astype(slit.dq.dtype)

        any_updated = True

    if any_updated:
        output_model.meta.cal_step.flat_field = 'COMPLETE'
    else:
        output_model.meta.cal_step.flat_field = 'SKIPPED'

    return interpolated_flats

def NIRSpec_IFU(output_model,
                f_flat_model, s_flat_model,
                d_flat_model, flat_suffix):
    """
    Short Summary
    -------------
    Apply flat-fielding for NIRSpec IFU data, in-place

    Parameters
    ----------
    output_model: JWST data model
        Science data model, modified (flat fielded) in-place.

    f_flat_model: NirspecFlatModel or NirspecQuadFlatModel object
        Flat field for the fore optics.

    s_flat_model: NirspecFlatModel object
        Flat field for the spectrograph.

    d_flat_model: NirspecFlatModel object
        Flat field for the detector.

    flat_suffix: str or None
        Filename suffix for optional output file to save the interpolated
        flat field images.  If not None, a file will be written (later, not
        by the current function).

    Returns
    -------
    ImageModel or None
        If not None, the value will be the interpolated flat field.
    """
    any_updated = False
    exposure_type = output_model.meta.exposure.type
    flat = np.ones_like(output_model.data)
    flat_dq = np.zeros_like(output_model.dq)

    try:
        list_of_wcs = nirspec.nrs_ifu_wcs(output_model)
    except (KeyError, AttributeError):
        if output_model.meta.cal_step.assign_wcs == 'COMPLETE':
            log.error("The input file does not appear to have WCS info.")
            raise RuntimeError("Problem accessing WCS information.")
        else:
            log.error("This mode %s requires WCS information.", exposure_type)
            raise RuntimeError("The assign_wcs step has not been run.")
    for (k, ifu_wcs) in enumerate(list_of_wcs):

        # example:  bounding_box = ((1600.5, 2048.5),   # X
        #                           (1886.5, 1925.5))   # Y
        truncated = False
        try:
            xstart = ifu_wcs.bounding_box[0][0]
            xstop = ifu_wcs.bounding_box[0][1]
            ystart = ifu_wcs.bounding_box[1][0]
            ystop = ifu_wcs.bounding_box[1][1]
            log.debug("Using ifu_wcs.bounding_box.")
        except AttributeError:
            log.info("ifu_wcs.bounding_box not found; using domain instead.")
            xstart = ifu_wcs.domain[0]['lower']
            xstop = ifu_wcs.domain[0]['upper']
            ystart = ifu_wcs.domain[1]['lower']
            ystop = ifu_wcs.domain[1]['upper']

        if xstart < -0.5:
            truncated = True
            log.info("xstart from WCS bounding_box was %g" % xstart)
            xstart = 0.
        if ystart < -0.5:
            truncated = True
            log.info("ystart from WCS bounding_box was %g" % ystart)
            ystart = 0.
        if xstop > 2047.5:
            truncated = True
            log.info("xstop from WCS bounding_box was %g" % xstop)
            xstop = 2047.
        if ystop > 2047.5:
            truncated = True
            log.info("ystop from WCS bounding_box was %g" % ystop)
            ystop = 2047.
        if truncated:
            log.info("WCS bounding_box for stripe %d extended beyond image "
                     "edges, has been truncated to ...", k)
            log.info('  xstart=%g, xstop=%g, ystart=%g, ystop=%g',
                     xstart, xstop, ystart, ystop)

        # Convert these to integers, and add one to the upper limits,
        # because we want to use these as slice limits.
        xstart = int(math.ceil(xstart))
        xstop = int(math.floor(xstop)) + 1
        ystart = int(math.ceil(ystart))
        ystop = int(math.floor(ystop)) + 1

        dx = xstop - xstart
        dy = ystop - ystart
        ind = np.indices((dy, dx))
        x = ind[1] + xstart
        y = ind[0] + ystart
        coords = ifu_wcs(x, y)
        wl = coords[2]
        nan_flag = np.isnan(wl)
        good_flag = np.logical_not(nan_flag)
        if wl[good_flag].max() < MICRONS_100:
            log.warning("Wavelengths in WCS table appear to be in meters")
        # Set NaNs to a harmless value, but don't modify nan_flag.
        wl[nan_flag] = 1.

        (flat_2d, flat_dq_2d) = create_flat_field(wl,
                        f_flat_model, s_flat_model, d_flat_model,
                        xstart, xstop, ystart, ystop,
                        exposure_type, None, None)
        flat_2d[nan_flag] = 1.
        mask = (flat_2d <= 0.)
        nbad = mask.sum(dtype=np.intp)
        if nbad > 0:
            log.debug("%d flat-field values <= 0", nbad)
            flat_2d[mask] = 1.
        del mask

        flat[ystart:ystop, xstart:xstop][good_flag] = flat_2d[good_flag]
        flat_dq[ystart:ystop, xstart:xstop] |= flat_dq_2d.copy()
        del nan_flag, good_flag

        any_updated = True

    if any_updated:
        output_model.dq |= flat_dq
        output_model.data /= flat
        output_model.err /= flat
        output_model.meta.cal_step.flat_field = 'COMPLETE'
        if flat_suffix is None:
            interpolated_flats = None
        else:
            # Create an output model for the interpolated flat fields.
            interpolated_flats = datamodels.ImageModel(data=flat, dq=flat_dq)
            interpolated_flats.update(output_model, only="PRIMARY")
    else:
        output_model.meta.cal_step.flat_field = 'SKIPPED'
        interpolated_flats = None

    return interpolated_flats


def create_flat_field(wl, f_flat_model, s_flat_model, d_flat_model,
                      xstart, xstop, ystart, ystop,
                      exposure_type, slit_name, slit_nt=None):
    """Extract and combine flat field components.

    Parameters
    ----------
    wl: 2-D ndarray
        Wavelength at each pixel of the 2-D slit array.  This array has
        shape (ystop - ystart, xstop - xstart).

    f_flat_model: NirspecFlatModel or NirspecQuadFlatModel object
        Flat field for the fore optics.

    s_flat_model: NirspecFlatModel object
        Flat field for the spectrograph.

    d_flat_model: NirspecFlatModel object
        Flat field for the detector.

    xstart, ystart: int
        Starting pixel numbers (zero indexed) for the slice containing
        the data for the current slit.

    xstop, ystop: int
        End of the slice containing the data for the current slit.  The
        start and stop values are Python slice notation, i.e. the region
        to be extracted is [ystart:ystop, xstart:xstop].

    exposure_type: str
        The exposure type refers to fixed_slit, IFU, or using the
        micro-shutter array.

    slit_name: str
        The name of the slit currently being processed.

    slit_nt: namedtuple or None
        For MSA data only, info about the current slit.

    Returns
    -------
    tuple, two 2-D ndarrays
        flat_2d: ndarray, 2-D, float
            The flat field, interpolated over wavelength, same shape as `wl`.
            Divide the 2-D extracted spectrum by this array to correct for
            flat-field variations.
        flat_dq: ndarray, 2-D, int
            The data quality array corresponding to flat_2d.
    """

    (f_flat, f_flat_dq) = fore_optics_flat(wl, f_flat_model, exposure_type,
                                           slit_name, slit_nt)

    (s_flat, s_flat_dq) = spectrograph_flat(wl, s_flat_model,
                                            xstart, xstop, ystart, ystop,
                                            exposure_type, slit_name)

    (d_flat, d_flat_dq) = detector_flat(wl, d_flat_model,
                                        xstart, xstop, ystart, ystop,
                                        exposure_type, slit_name)

    flat_2d = f_flat * s_flat * d_flat

    flat_dq = combine_dq(f_flat_dq, s_flat_dq, d_flat_dq,
                         default_shape=flat_2d.shape)

    return (flat_2d, flat_dq)


def fore_optics_flat(wl, f_flat_model, exposure_type,
                     slit_name, slit_nt):
    """Extract the flat for the fore optics part.

    Parameters
    ----------
    wl: 2-D ndarray
        Wavelength at each pixel of the 2-D slit array.

    f_flat_model: NirspecFlatModel or NirspecQuadFlatModel object
        Flat field for the fore optics.

    exposure_type: str
        The exposure type refers to fixed_slit, IFU, or using the
        micro-shutter array.

    slit_name: str
        The name of the slit currently being processed.

    slit_nt: namedtuple or None
        For MOS data (only), this is used to get the quadrant number and
        the indices of the current shutter in the Y and X directions.

    Returns
    -------
    tuple (f_flat, f_flat_dq)
        The flat field and associated data quality array.
    """

    if slit_nt is None:
        quadrant = None
    else:
        quadrant = slit_nt.quadrant - 1         # convert to zero indexed

    (tab_wl, tab_flat) = read_flat_table(f_flat_model, exposure_type,
                                         slit_name, quadrant)
    if tab_wl.max() < MICRONS_100:
        log.warning("Wavelengths in f_flat table appear to be in meters")

    # While there actually is a slowly varying flat field for the MSA mode,
    # it's a 1-D array, not 2-D.  This array will be applied by incorporating
    # it into tab_flat.  So even for the MSA, there will not be any 2-D
    # image flat, so set the variable to 1.
    flat_2d = 1.

    if exposure_type == "NRS_MSASPEC":
        # The MOS "image" is in MSA coordinates (shutter index in x and y),
        # not detector pixel coordinates.
        # This is an example to show what xcen and ycen mean:
        #       shutter_id = xcen + (ycen - 1) * 365
        msa_y, msa_x = slit_nt.ycen, slit_nt.xcen
        msa_y -= 1              # convert to zero indexed
        msa_x -= 1
        full_array_flat = f_flat_model.quadrants[quadrant].data
        full_array_dq = f_flat_model.quadrants[quadrant].dq
        # Get the wavelength corresponding to each plane in the "image".
        image_wl = read_image_wl(f_flat_model, quadrant)
        if image_wl.max() < MICRONS_100:
            log.warning("Wavelengths in f_flat image appear to be in meters.")
        one_d_flat = full_array_flat[:, msa_y, msa_x]
        # This is just a single value, i.e. the shutter can be flagged
        # as bad.  But if it's bad, why was the shutter used?  And what are
        # we supposed to do if it is bad, flag the whole slit as bad?
        # xxx d_dq = full_array_dq[msa_y, msa_x]

        # The wavelengths and flat-field values read from the reference
        # table are tab_wl and tab_flat respectively.  We need to combine
        # the 1-D MSA flat from the reference "image" with the table
        # values, so interpolate the 1-D MSA flat at each wavelength in
        # tab_wl, and multiply into tab_flat.
        #     numpy.interp(x, xp, fp, left, right)
        #       x:  values at which to interpolate
        #       xp:  array of independent-variable values (must be increasing)
        #       fp:  array of data values
        #       left, right:  values to return for out-of-bounds x
        tab_flat *= np.interp(tab_wl, image_wl, one_d_flat, 1., 1.)

    f_flat_dq = None

    # The shape of the output array is obtained from `wl`.
    f_flat = combine_fast_slow(wl, flat_2d, tab_wl, tab_flat)

    return (f_flat, f_flat_dq)


def spectrograph_flat(wl, s_flat_model,
                      xstart, xstop, ystart, ystop,
                      exposure_type, slit_name):
    """Extract the flat for the spectrograph part.

    Parameters
    ----------
    wl: 2-D ndarray
        Wavelength at each pixel of the 2-D slit array.

    s_flat_model: NirspecFlatModel object
        Flat field for the spectrograph.

    xstart, ystart: int
        Starting pixel numbers (zero indexed) for the slice containing
        the data for the current slit.

    xstop, ystop: int
        End of the slice containing the data for the current slit.  The
        start and stop values are Python slice notation, i.e. the region
        to be extracted is [ystart:ystop, xstart:xstop].

    exposure_type: str
        The exposure type refers to fixed_slit, IFU, or using the
        micro-shutter array.

    slit_name: str
        The name of the slit currently being processed.

    Returns
    -------
    tuple (s_flat, s_flat_dq)
        The flat field and associated data quality array.
    """

    quadrant = None

    if xstart >= xstop or ystart >= ystop:
        return (1., None)

    (tab_wl, tab_flat) = read_flat_table(s_flat_model, exposure_type,
                                         slit_name, quadrant)
    if tab_wl.max() < MICRONS_100:
        log.warning("Wavelengths in s_flat table appear to be in meters")

    full_array_flat = s_flat_model.data
    full_array_dq = s_flat_model.dq

    if len(full_array_flat.shape) == 3:
        # MSA data
        image_flat = full_array_flat[:, ystart:ystop, xstart:xstop]
        image_dq = full_array_dq[:, ystart:ystop, xstart:xstop]
        # Get the wavelength corresponding to each plane in the image.
        image_wl = read_image_wl(s_flat_model, quadrant)
        if image_wl.max() < MICRONS_100:
            log.warning("Wavelengths in s_flat image appear to be in meters")
        (flat_2d, s_flat_dq) = interpolate_flat(image_flat, image_dq,
                                                image_wl, wl)
    else:
        flat_2d = full_array_flat[ystart:ystop, xstart:xstop]
        s_flat_dq = full_array_dq[ystart:ystop, xstart:xstop]

    s_flat = combine_fast_slow(wl, flat_2d, tab_wl, tab_flat)

    return (s_flat, s_flat_dq)


def detector_flat(wl, d_flat_model,
                  xstart, xstop, ystart, ystop,
                  exposure_type, slit_name):
    """Extract the flat for the detector part.

    Parameters
    ----------
    wl: 2-D ndarray
        Wavelength at each pixel of the 2-D slit array.

    d_flat_model: NirspecFlatModel object
        Flat field for the detector.

    xstart, ystart: int
        Starting pixel numbers (zero indexed) for the slice containing
        the data for the current slit.

    xstop, ystop: int
        End of the slice containing the data for the current slit.  The
        start and stop values are Python slice notation, i.e. the region
        to be extracted is [ystart:ystop, xstart:xstop].

    exposure_type: str
        The exposure type refers to fixed_slit, IFU, or using the
        micro-shutter array.

    slit_name: str
        The name of the slit currently being processed.

    Returns
    -------
    tuple (d_flat, d_flat_dq)
        The flat field and associated data quality array.
    """

    quadrant = None

    if xstart >= xstop or ystart >= ystop:
        return (1., None)

    (tab_wl, tab_flat) = read_flat_table(d_flat_model, exposure_type,
                                         slit_name, quadrant)
    if tab_wl.max() < MICRONS_100:
        log.warning("Wavelengths in d_flat table appear to be in meters.")

    full_array_flat = d_flat_model.data
    full_array_dq = d_flat_model.dq
    image_flat = full_array_flat[:, ystart:ystop, xstart:xstop]
    if len(full_array_dq.shape) == 2:
        image_dq = full_array_dq[ystart:ystop, xstart:xstop]
    else:
        image_dq = full_array_dq[:, ystart:ystop, xstart:xstop]
    # Get the wavelength corresponding to each plane in the image.
    image_wl = read_image_wl(d_flat_model, quadrant)
    if image_wl.max() < MICRONS_100:
        log.warning("Wavelengths in d_flat image appear to be in meters.")

    (flat_2d, d_flat_dq) = interpolate_flat(image_flat, image_dq,
                                            image_wl, wl)

    d_flat = combine_fast_slow(wl, flat_2d, tab_wl, tab_flat)

    return (d_flat, d_flat_dq)


def combine_dq(f_flat_dq, s_flat_dq, d_flat_dq, default_shape):
    """Combine non-None DQ arrays via bitwise_or.

    Parameters
    ----------
    f_flat_dq: ndarray
        The DQ array for the fore optics component.

    s_flat_dq: ndarray
        The DQ array for the spectrograph component.

    d_flat_dq: ndarray
        The DQ array for the detector component.

    default_shape: tuple
        If all three of the DQ arrays (see above) are None, use this shape
        to create a DQ array filled with zero.

    Returns
    -------
    ndarray
        The DQ array resulting from combining the input DQ arrays via
        bitwise OR.
    """

    dq_list = []
    if f_flat_dq is not None:
        dq_list.append(f_flat_dq)
    if s_flat_dq is not None:
        dq_list.append(s_flat_dq)
    if d_flat_dq is not None:
        dq_list.append(d_flat_dq)
    n_dq = len(dq_list)
    if n_dq < 1:
        flat_dq = np.zeros(default_shape, dtype=np.uint32)
    elif n_dq == 1:
        flat_dq = dq_list[0].copy()
    elif n_dq == 2:
        flat_dq = np.bitwise_or(dq_list[0], dq_list[1])
    elif n_dq == 3:
        temp = np.bitwise_or(dq_list[0], dq_list[1])
        flat_dq = np.bitwise_or(temp, dq_list[2])

    return flat_dq


def read_image_wl(flat_model, quadrant=None):
    """Read wavelengths for the image planes.

    Parameters
    ----------
    flat_model: NirspecFlatModel or NirspecQuadFlatModel object
        Flat field for the current component.

    quadrant: int (0, 1, 2, or 3)
        The quadrant of the micro-shutter array.  This is only needed for
        fore-optics for MSA (MOS) data.

    Returns
    -------
    """

    if quadrant is not None:                    # NRS_MSASPEC
        wavelength = flat_model.quadrants[quadrant].wavelength["wavelength"]
    else:
        wavelength = flat_model.wavelength["wavelength"]

    if len(wavelength.shape) > 1:
        n = wavelength.shape[-1]
        try:
            wl = wavelength.reshape((n,))
        except ValueError:
            log.error("Image wavelength array has shape %s; "
                      "don't know how to interpret that.",
                      str(wavelength.shape))
            raise ValueError("Expected either a scalar column or just one row.")
        wavelength = wl
    # The assumption here is that any NaN or non-positive wavelengths will
    # only be at the end of the array.  If there are embedded NaNs or zero
    # or negative wavelengths, the following will result in the wavelengths
    # becoming out of synch with the flat-field data.  In this case, it
    # will be necessary to also filter (along the first image axis) and
    # return the flat-field data.
    filter1 = np.logical_not(np.isnan(wavelength))      # skip NaNs
    wavelength = wavelength[filter1]
    filter2 = (wavelength > 0.)
    wavelength = wavelength[filter2]

    return wavelength


def read_flat_table(flat_model, exposure_type,
                    slit_name=None, quadrant=None):
    """Read the table (the "fast" variation).

    Parameters
    ----------
    flat_model: NIRSpec flat-field object
        This contains the flat field table from which we will read the
        "fast" variation flat-field data.

    exposure_type: str
        The exposure type refers to fixed_slit, IFU, or using the
        micro-shutter array.  In this function we just need to check for
        fixed-slit types.

    slit_name: str
        The name of the slit.  This is only needed for fixed-slit data, in
        which case it is used for selecting the relevant row of the table.

    quadrant: int (0, 1, 2, or 3)
        The quadrant of the micro-shutter array.  This is only needed for
        fore-optics for MSA (MOS) data.

    Returns
    -------
    tuple, two ndarrays
        tab_wl: ndarray, 1-D, float
        tab_flat: ndarray, 1-D, float
    """

    if quadrant is not None:                    # NRS_MSASPEC
        data = flat_model.quadrants[quadrant].flat_table
    else:
        data = flat_model.flat_table

    try:
        slit_col = data["slit_name"]
    except KeyError:
        slit_col = None
    try:
        nelem_col = data["nelem"]
    except KeyError:
        nelem_col = None
    wl_col = data["wavelength"]
    flat_col = data["data"]

    nrows = len(wl_col)
    row = None
    # Note that it's only for fixed-slit data that we need to select the
    # row based on the slit name.
    if exposure_type in FIXED_SLIT_TYPES and slit_col is not None:
        slit_name_lc = slit_name.lower()
        for i in range(nrows):
            # Note:  The .strip() is a workaround.  As of the time of
            # writing, the value of a text string may have trailing blanks
            # if there is only one row in the table.
            column_value = slit_col[i].lower().strip()
            if column_value == "any" or column_value == slit_name_lc:
                row = i
                break
        if row is None:
            log.error("Slit name %s not found in flat field table", slit_name)
            raise ValueError("{} not found in SLIT_NAME column (nor was 'ANY')"
                             .format(slit_name))

    nelem = None                        # initial value
    if row is not None:
        # Table contains arrays; use the row that was found above.
        tab_wl = wl_col[row].copy()
        tab_flat = flat_col[row].copy()
        if nelem_col is not None:
            nelem = nelem_col[row]
    else:
        # There was no SLIT_NAME column, or the data are not fixed-slit.
        if len(wl_col.shape) > 1:
            # Table contains arrays, but there should be only one row.
            tab_wl = wl_col[0].copy()
            tab_flat = flat_col[0].copy()
            if nelem_col is not None:
                nelem = nelem_col[0]
        else:
            # Table contains scalar columns.
            tab_wl = wl_col.copy()
            tab_flat = flat_col.copy()
            if nelem_col is not None:
                nelem = nelem_col[0]            # arbitrary choice of row
    if nelem is not None:
        if len(tab_wl) < nelem:
            log.error("The fast_variation array size %d in "
                      "the data model is too small, and table data were "
                      "truncated.", len(tab_wl))
            nelem = len(tab_wl)                 # truncated!
        else:
            tab_wl = tab_wl[:nelem]
            tab_flat = tab_flat[:nelem]
    else:
        nelem = len(tab_wl)

    # Trailing dummy rows should have been taken care of via nelem above,
    # but only if an nelem column was present and was set correctly.
    filter1 = np.logical_not(np.isnan(tab_wl))  # skip NaNs
    filter2 = np.logical_not(np.isnan(tab_flat))
    filter = np.logical_and(filter1, filter2)
    n1 = filter.sum(dtype=np.intp)
    if n1 != nelem:
        log.debug("The table wavelength or flat-field data array contained "
                  "%d NaNs; these have been skipped.", nelem - n1)
        tab_wl = tab_wl[filter]
        tab_flat = tab_flat[filter]
    del filter1, filter2, filter
    # Skip zero or negative wavelengths, and skip zero flat-field values.
    filter1 = (tab_wl > 0.)
    filter2 = (tab_flat != 0.)
    filter = np.logical_and(filter1, filter2)
    n2 = filter.sum(dtype=np.intp)
    if n2 != n1:
        log.debug("The table wavelength or flat-field data array contained "
                  "%d zero or negative values; these have been skipped.",
                  n1 - n2)
        tab_wl = tab_wl[filter]
        tab_flat = tab_flat[filter]
    del filter1, filter2, filter

    return (tab_wl, tab_flat)


def combine_fast_slow(wl, flat_2d, tab_wl, tab_flat):
    """Multiply the image by the tabular values.

    Parameters
    ----------
    wl: 2-D ndarray
        Wavelength at each pixel of the 2-D slit array.

    flat_2d: 2-D ndarray or a scalar (float)
        The flat field derived from the image part of the reference file,
        or a scalar (e.g. 1) if there is no image part in the current
        reference file.

    tab_wl: ndarray, 1-D
        Wavelengths corresponding to `tab_flat`.

    tab_flat: ndarray, 1-D
        The flat field from the table part of the reference file.  This
        is the "fast" variation of the flat, i.e. fast with respect to
        wavelength.

    Returns
    -------
    2-D ndarray
        The product of flat_2d and the values in `tab_flat` interpolated
        to the wavelengths of the science image, i.e. `wl`.
    """

    (ny, nx) = wl.shape

    dwl = np.zeros_like(wl)

    # Determine which axis is the dispersion direction (this test is
    # not foolproof).
    mid_x = nx // 2
    mid_y = ny // 2
    dwlx = abs(wl[mid_y, mid_x+1] - wl[mid_y, mid_x-1])
    dwly = abs(wl[mid_y+1, mid_x] - wl[mid_y-1, mid_x])
    if dwlx >= dwly:
        dispaxis = 1                            # only used for log info
        # The wavelength span of pixel i is (wl[i+1] - wl[i-1]) / 2.
        temp = (wl[:, 2:] - wl[:, 0:-2]) / 2.
        dwl[:, 1:-1] = temp
        dwl[:, 0] = dwl[:, 1]
        dwl[:, -1] = dwl[:, -2]
    else:
        dispaxis = 2
        temp = (wl[2:, :] - wl[0:-2, :]) / 2.
        dwl[1:-1, :] = temp
        dwl[0, :] = dwl[1, :]
        dwl[-1, :] = dwl[-2, :]
    log.debug("dispaxis = %d", dispaxis)

    wl_low = wl - dwl / 2.
    wl_high = wl + dwl / 2.

    # Values averaged within tab_flat.
    values = np.zeros_like(wl)
    (ny, nx) = wl.shape
    # Abscissas and weights for 3-point Gaussian integration, but taking
    # the width of the interval to be 1, so the result will be the average
    # over the interval.
    d = math.sqrt(0.6) / 2.
    dx = np.array([-d, 0., d])
    wgt = np.array([5., 8., 5.]) / 18.
    for j in range(ny):
        for i in range(nx):
            # average the tabular data over the range of wavelengths
            values[j, i] = g_average(wl[j, i], dwl[j, i],
                                     tab_wl, tab_flat, dx, wgt)

    return flat_2d * values

def g_average(wl0, dwl0, tab_wl, tab_flat, dx, wgt):
    """Gaussian integration.

    Parameters
    ----------
    wl0: float
        Wavelength at the center of the current pixel.

    dwl0: float
        Width (in wavelength units) of the current pixel.

    tab_wl: ndarray, 1-D
        Array of wavelengths corresponding to `tab_flat` flat-field values.

    tab_flat: ndarray, 1-D
        Array of flat-field values.

    dx: ndarray, 1-D
        Array of offsets within a pixel:  -0.3873, 0.0, +0.3873

    wgt: ndarray, 1-D
        Array of weights:  5/18, 8/18, 5/18

    Returns
    -------
    float
        The average value of `tab_flat` over the current pixel.
    """

    npts = len(dx)
    wavelengths = wl0 + dwl0 * dx
    sum = 0.
    for k in range(npts):
        value = wl_interpolate(wavelengths[k], tab_wl, tab_flat)
        sum += (value * wgt[k])

    return sum


def wl_interpolate(wavelength, tab_wl, tab_flat):
    """Interpolate the flat field at the specified wavelength.

    Linear interpolation is used.

    Parameters
    ----------
    wavelength: float
        The wavelength (microns) at which to find the flat-field value.

    tab_wl: ndarray, 1-D
        Array of wavelengths corresponding to `tab_flat` flat-field values.
        These are assumed to be strictly increasing.

    tab_flat: ndarray, 1-D
        Array of flat-field values.

    Returns
    -------
    float
        The flat-field value (from `tab_flat`) at `wavelength`.
    """

    if wavelength < tab_wl[0] or wavelength > tab_wl[-1]:
        return 1.
    n0 = np.searchsorted(tab_wl, wavelength) - 1
    p = (wavelength - tab_wl[n0]) / (tab_wl[n0 + 1] - tab_wl[n0])
    q = 1. - p

    return q * tab_flat[n0] + p * tab_flat[n0 + 1]


def interpolate_flat(image_flat, image_dq, image_wl, wl):
    """

    Short Summary
    -------------
    Interpolate within the 3-D flat field image to get a 2-D flat.

    Parameters
    ----------
    image_flat: ndarray, 3-D
        This is slice [:, ystart:ystop, xstart:xstop] of the flat field
        reference image.  This slice covers the spatial extent of the
        extracted 2-D spectrum and includes all of the wavelength axis
        (the first axis) of the reference image.

    image_dq: ndarray, 2-D or 3-D
        This is slice [:, ystart:ystop, xstart:xstop] of the data quality
        array for the flat field reference image.

    image_wl: ndarray, 1-D
        The wavelength for each plane of the flat field reference image.

    wl: ndarray, 2-D
        The wavelength at each pixel of the 2-D extracted science spectrum.

    Returns
    -------
    tuple, two 2-D ndarrays
    flat_2d: ndarray, 2-D, float
        The flat field, interpolated over wavelength, same shape as `wl`.
        Divide the 2-D extracted spectrum by this array to correct for
        flat-field variations.
    flat_dq: ndarray, 2-D, int
        The data quality array corresponding to flat_2d.
    """

    if len(image_flat.shape) < 3:
        return (image_flat, image_dq)

    (nz, ysize, xsize) = image_flat.shape
    if nz == 1:
        if len(image_dq.shape) == 2:
            return (image_flat.reshape((ysize, xsize)), image_dq)
        else:
            return (image_flat.reshape((ysize, xsize)),
                    image_dq.reshape((ysize, xsize)))

    grid = np.indices((ysize, xsize), dtype=np.intp)
    ixpixel = grid[1]
    iypixel = grid[0]

    # The initial value of -1 is a flag to indicate that elements have not
    # been assigned valid values yet.
    k = np.zeros(wl.shape, dtype=np.intp) - 1

    # Truncate the index for wavelengths that are outside the range of
    # image_wl.  Near the end of this function we'll flag these pixels
    # with NO_FLAT_FIELD and set flat_2d to 1, but for now the indices
    # need to be assigned harmless values to avoid indexing out of bounds.
    #   Why do we set the upper limit of k to nz - 2?
    #   Because we interpolate using elements k and k + 1.
    k[:, :] = np.where(wl <= image_wl[0], 0, k)
    k[:, :] = np.where(wl >= image_wl[nz - 1], nz - 2, k)

    # Look for the correct interval for linear interpolation.
    for k_test in range(nz - 1):
        test1 = np.logical_and(wl >= image_wl[k_test],
                               wl < image_wl[k_test + 1])
        # If an element of k is not -1, it has already been assigned, and
        # I don't want to clobber it.
        test2 = np.logical_and(k == -1, test1)
        k[:, :] = np.where(test2, k_test, k)
        if np.all(k >= 0):
            break

    # Use linear interpolation within the 3-D flat field to get a 2-D
    # flat field.
    denom = image_wl[k + 1] - image_wl[k]
    zero_denom = (denom == 0.)
    denom = np.where(zero_denom, 1., denom)
    p = np.where(zero_denom, 0., (wl - image_wl[k]) / denom)
    q = 1. - p
    flat_2d = q * image_flat[k, iypixel, ixpixel] + \
              p * image_flat[k + 1, iypixel, ixpixel]
    if len(image_dq.shape) == 2:
        flat_dq = image_dq.copy()
    else:
        flat_dq = np.where(p == 0.,
                           image_dq[k, iypixel, ixpixel],
                           np.bitwise_or(image_dq[k, iypixel, ixpixel],
                                         image_dq[k + 1, iypixel, ixpixel]))

    # If the wavelength is out of range, set a DQ flag.
    indx = np.where(wl < image_wl[0])
    flat_dq[indx] |= dqflags.pixel['NO_FLAT_FIELD']
    indx = np.where(wl > image_wl[nz - 1])
    flat_dq[indx] |= dqflags.pixel['NO_FLAT_FIELD']

    # If a pixel is flagged as bad, applying flat_2d should not make any
    # change to the science data.
    flat_2d[:, :] = np.where(flat_dq > 0, 1., flat_2d)

    return (flat_2d.astype(image_flat.dtype), flat_dq)
