#
# Module for handling Data Quality Initialization
#
# This version applies an IRS2-format mask reference file to an IRS2-format
# (3200, 2048) pixeldq array.  Only minor changes were made to the original
# code, in functions is_subarray (use < rather than !=) and check_dimensions
# (pixeldq data type should be uint32).

import logging

import numpy as np

from .. import datamodels

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


guider_list = ['FGS_ID-IMAGE', 'FGS_ID-STACK', 'FGS_ACQ1', 'FGS_ACQ2',\
             'FGS_TRACK', 'FGS_FINEGUIDE'] # FGS guider operation modes


def correct_model(input_model, mask_model):
    """DQ Initialize a JWST Model"""
    output_model = do_dqinit(input_model, mask_model)

    return output_model


def do_dqinit(input_model, mask_model):
    """Do the DQ initialization"""

    # Inflate empty DQ array, if necessary
    check_dimensions(input_model)

    # Make sure the mask array is not smaller than the science array
    if (input_model.data.shape[-1] > mask_model.dq.shape[-1]) or \
       (input_model.data.shape[-2] > mask_model.dq.shape[-2]):
        log.warning("Reference data shape is smaller than science data")
        log.warning("Step will be skipped")
        input_model.meta.cal_step.dq_init = 'SKIPPED'
        return input_model

    # Create output model as copy of input
    output_model = input_model.copy()

    # Extract subarray from reference data, if necessary
    if is_subarray(output_model):
        log.debug('input exposure is a subarray readout')
        mask_array = get_mask_subarray(mask_model, output_model)
    else:
        mask_array = mask_model.dq

    # Set model-specific data quality in output
    if input_model.meta.exposure.type in guider_list:
        dq = np.bitwise_or(input_model.dq, mask_array)
        output_model.dq = dq
    else:
        dq = np.bitwise_or(input_model.pixeldq, mask_array)
        output_model.pixeldq = dq

    output_model.meta.cal_step.dq_init = 'COMPLETE'

    return output_model


def is_subarray(input_model):

    # get model-specific data quality dimensions
    if input_model.meta.exposure.type in guider_list:
        nrows, ncols = input_model.dq.shape
    else:
        nrows, ncols = input_model.pixeldq.shape

    instrument = input_model.meta.instrument.name

    if instrument == 'MIRI':
        if ncols < 1032 or nrows < 1024: return True
        return False
    else:
        if ncols < 2048 or nrows < 2048: return True
        return False


def get_mask_subarray(mask_model, output_model):

    if (output_model.meta.subarray.xstart is None or
        output_model.meta.subarray.ystart is None):
        raise ValueError('xstart or ystart metadata values not found')

    # get model-specific data quality array sizes
    if output_model.meta.exposure.type in guider_list:
        ysize, xsize = output_model.dq.shape
    else:
        ysize, xsize = output_model.pixeldq.shape

    xstart = output_model.meta.subarray.xstart
    xstop = xstart + xsize - 1
    ystart = output_model.meta.subarray.ystart
    ystop = ystart + ysize - 1

    log.debug('science xstart=%d, xstop=%d, ystart=%d, ystop=%d',
              xstart, xstop, ystart, ystop)
    log.debug('ref xsize=%d, ysize=%d',
              mask_model.dq.shape[1], mask_model.dq.shape[0])

    if (xstart < 1 or ystart < 1 or
        xstop > mask_model.dq.shape[1] or ystop > mask_model.dq.shape[0]):
        log.error('Computed reference file subarray indexes are incompatible with size of reference data array')
        log.error('xstart=%d, xstop=%d, ystart=%d, ystop=%d',
                   xstart, xstop, ystart, ystop)
        log.error('Reference xsize=%d, ysize=%d',
                   mask_model.dq.shape[1], mask_model.dq.shape[0])
        raise ValueError('Bad subarray indexes')

    return mask_model.dq[ystart - 1:ystop, xstart - 1:xstop]


def check_dimensions(input_model):
    #
    # Check that the input model pixeldq attribute has the same dimensions as the
    # image plane of the input model science data
    # If it has dimensions (0,0), create an array of zeros with the same shape as
    # the image plane of the input model. For the FGS modes, the GuiderRawModel
    # has a dq array only (no pixeldq or groupdq)

    input_shape = input_model.data.shape

    if isinstance(input_model, datamodels.GuiderRawModel):
        if input_model.dq.shape != input_shape[-2:]:

            # If the shape is different, then the mask model should have a shape of (0,0)
            # If that's the case, create the array
            if input_model.dq.shape == (0, 0):
                input_model.dq = np.zeros((input_shape[-2:])).astype('uint32')
            else:
                log.error("DQ array has the wrong shape: (%d, %d)" % input_model.dq.shape)

    else:   # RampModel
        if input_model.pixeldq.shape != input_shape[-2:]:

            # If the shape is different, then the mask model should have a shape of (0,0)
            # If that's the case, create the array
            if input_model.pixeldq.shape == (0, 0):
                input_model.pixeldq = np.zeros((input_shape[-2:])).astype('uint32')
            else:
                log.error("Pixeldq array has the wrong shape: (%d, %d)" % input_model.pixeldq.shape)

        # Perform the same check for the input model groupdq array
        if input_model.groupdq.shape != input_shape:
            if input_model.groupdq.shape == (0, 0, 0, 0):
                input_model.groupdq = np.zeros((input_shape)).astype('uint8')
            else:
                log.error("Groupdq array has the wrong shape: (%d, %d, %d, %d)" % input_model.groupdq.shape)
    return
