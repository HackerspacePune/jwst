"""
Test functions for NIRSPEC WCS - all modes.
"""
import os.path
import numpy as np
from numpy.testing.utils import assert_allclose
from astropy.io import fits
from astropy.modeling import models as astmodels
from gwcs import wcs
from ... import datamodels
from ...transforms.models import Slit
from .. import nirspec
from .. import assign_wcs_step
from . import data
import pytest

data_path = os.path.split(os.path.abspath(data.__file__))[0]


wcs_kw = {'wcsaxes': 2, 'ra_ref': 165, 'dec_ref': 54,
          'v2_ref': -8.3942412, 'v3_ref': -5.3123744, 'roll_ref': 37,
          'crpix1': 1024, 'crpix2': 1024,
          'cdelt1': .08, 'cdelt2': .08,
          'ctype1': 'RA---TAN', 'ctype2': 'DEC--TAN',
          'pc1_1': 1, 'pc1_2': 0, 'pc2_1': 0, 'pc2_2': 1
          }


slit_fields_num = ["shutter_id", "xcen", "ycen",
                   "ymin", "ymax", "quadrant", "source_id", "nshutters",
                   "stellarity", "source_xpos", "source_ypos"]


slit_fields_str = ["name", "source_name", "source_alias", "catalog_id"]


def _compare_slits(s1, s2):
    for f in slit_fields_num:
        assert_allclose(getattr(s1, f), getattr(s2, f))
    for f in slit_fields_str:
        assert getattr(s1, f) == getattr(s2, f)


def get_file_path(filename):
    """
    Construct an absolute path.
    """
    return os.path.join(data_path, filename)


def create_hdul():
    """
    Create a fits HDUList instance.
    """
    hdul = fits.HDUList()
    phdu = fits.PrimaryHDU()
    phdu.header['instrume'] = 'NIRSPEC'
    phdu.header['detector'] = 'NRS1'
    phdu.header['time-obs'] = '8:59:37'
    phdu.header['date-obs'] = '2016-09-05'

    for item in wcs_kw.items():
        phdu.header[item[0]] = item[1]
    hdul.append(phdu)
    return hdul


def create_reference_files(datamodel):
    """
    Create a dict {reftype: reference_file}.
    """
    refs = {}
    step = assign_wcs_step.AssignWcsStep()
    for reftype in assign_wcs_step.AssignWcsStep.reference_file_types:
        refs[reftype] = step.get_reference_file(datamodel, reftype)
    return refs


def create_nirspec_imaging_file():
    image = create_hdul()
    image[0].header['exp_type'] = 'NRS_IMAGE'
    image[0].header['filter'] = 'F290LP'
    image[0].header['grating'] = 'MIRROR'
    return image

'''
def create_nirspec_mos_file():
    image = create_hdul()
    image[0].header['exp_type'] = 'NRS_MSASPEC'
    image[0].header['filter'] = 'F170LP'
    image[0].header['grating'] = 'G235M'
    image[0].header['crval3'] = 0
    image[0].header['wcsaxes'] = 3
    image[0].header['ctype3'] = 'WAVE'
    image[0].header['pc3_1'] = 1
    image[0].header['pc3_2'] = 0

    msa_status_file = get_file_path('SPCB-GD-A.msa.fits.gz')
    image[0].header['MSACONFG'] = msa_status_file
    return image
'''

def create_nirspec_ifu_file(filter, grating, lamp='N/A'):
    image = create_hdul()
    image[0].header['exp_type'] = 'NRS_IFU'
    image[0].header['filter'] = filter #'F170LP'
    image[0].header['grating'] = grating #'G235H'
    image[0].header['crval3'] = 0
    image[0].header['wcsaxes'] = 3
    image[0].header['ctype3'] = 'WAVE'
    image[0].header['pc3_1'] = 1
    image[0].header['pc3_2'] = 0
    image[0].header['lamp'] = lamp
    image[0].header['GWA_XTIL'] = 0.35986012
    image[0].header['GWA_YTIL'] = 0.13448857
    return image


def create_nirspec_fs_file():
    image = create_hdul()
    image[0].header['exp_type'] = 'NRS_FIXEDSLIT'
    image[0].header['filter'] = 'F100LP'
    image[0].header['grating'] = 'G140H'
    image[0].header['crval3'] = 0
    image[0].header['wcsaxes'] = 3
    image[0].header['ctype3'] = 'WAVE'
    image[0].header['pc3_1'] = 1
    image[0].header['pc3_2'] = 0
    image[0].header['GWA_XTIL'] = 3.5896975e-001
    image[0].header['GWA_YTIL'] = 1.3438272e-001
    image[0].header['GWA_TTIL'] = 3.9555361e+001
    image[0].header['SUBARRAY'] = "ALLSLITS"
    return image


def test_nirspec_imaging():
    """
    Test Nirspec Imaging mode using build 6 reference files.
    """
    #Test creating the WCS
    f = create_nirspec_imaging_file()
    im = datamodels.ImageModel(f)

    refs = create_reference_files(im)

    pipe = nirspec.create_pipeline(im, refs)
    w = wcs.WCS(pipe)
    im.meta.wcs = w
    # Test evaluating the WCS
    im.meta.wcs(1, 2)


@pytest.mark.xfail(reason="test needs CV3 update")
def test_nirspec_ifu_against_esa():
    """
    Test Nirspec IFU mode using build 6 reference files.
    """
    #Test creating the WCS
    filename = create_nirspec_ifu_file('OPAQUE', 'G140H', 'REF')
    im = datamodels.ImageModel(filename)
    refs = create_reference_files(im)

    pipe = nirspec.create_pipeline(im, refs)
    w = wcs.WCS(pipe)
    im.meta.wcs = w
    # Test evaluating the WCS (slice 0)
    w0 = nirspec.nrs_wcs_set_input(im, 0)

    ref = fits.open(get_file_path('Trace_IFU_Slice_00_MON-COMBO-IFU-06_8410_jlab85.fits.gz'))
    crpix = np.array([ref[1].header['crpix1'], ref[1].header['crpix2']])
    crval = np.array([ref[1].header['crval1'], ref[1].header['crval2']])

    # get positions within the slit and the coresponding lambda
    slit1 = ref[5].data # y offset on the slit
    lam = ref[4].data
    # filter out locations outside the slit
    cond = np.logical_and(slit1 < .5, slit1 > -.5)
    y, x = cond.nonzero()
    cor = crval - np.array(crpix)
    # 1-based coordinates full frame coordinates
    y = y + cor[1] + 1
    x = x + cor[0] + 1
    sca2world = w0.get_transform('sca', 'msa_frame')
    _, slit_y, lp = sca2world(x, y)

    # Convert meters to microns for the second parameters as the
    # first parameter will be in microns.
    assert_allclose(lp, lam[cond] * 1e6, rtol=1e-4, atol=1e-4)
    ref.close()

'''
def test_nirspec_mos():
    """
    Test full optical path in Nirspec MOS mode using build 6 reference files.
    """
    #Test creating the WCS
    f = create_nirspec_mos_file()
    im = datamodels.ImageModel(f)

    refs = create_reference_files(im)
    pipe = nirspec.create_pipeline(im, refs)
    w = wcs.WCS(pipe)
    im.meta.wcs = w
    # Test evaluating the WCS
    _, wrange = nirspec.spectral_order_wrange_from_model(im)
    w1 = nirspec.nrs_wcs_set_input(im, 4, 5824, wrange)
    w1(1, 2)
'''

@pytest.mark.xfail(reason="test needs CV3 update")
def test_nirspec_fs_esa():
    """
    Test Nirspec FS mode using build 6 reference files.
    """
    #Test creating the WCS
    filename = create_nirspec_fs_file()
    im = datamodels.ImageModel(filename)
    refs = create_reference_files(im)
    #refs['disperser'] = get_file_path('jwst_nirspec_disperser_0001.asdf')
    pipe = nirspec.create_pipeline(im, refs)
    w = wcs.WCS(pipe)
    im.meta.wcs = w
    # Test evaluating the WCS
    w1 = nirspec.nrs_wcs_set_input(im, "S200A1")

    ref = fits.open(get_file_path('Trace_SLIT_A_200_1_SLIT-COMBO-016_9791_jlab85_0001.fits.gz'))
    crpix = np.array([ref[1].header['crpix1'], ref[1].header['crpix2']])
    crval = np.array([ref[1].header['crval1'], ref[1].header['crval2']])
    # get positions within the slit and the coresponding lambda
    slit1 = ref[5].data # y offset on the slit
    lam = ref[4].data
    # filter out locations outside the slit
    cond = np.logical_and(slit1 < .5, slit1 > -.5)
    y, x = cond.nonzero()
    cor = crval - np.array(crpix)
    # 1-based coordinates full frame coordinates
    y = y + cor[1] + 1
    x = x + cor[0] + 1
    sca2world = w1.get_transform('sca', 'v2v3')
    ra, dec, lp = sca2world(x, y)
    # w1 now outputs in microns hence the 1e6 factor
    lp *= 1e-6
    lam = lam[cond]
    nan_cond = ~np.isnan(lp)
    assert_allclose(lp[nan_cond], lam[nan_cond], atol=10**-13)
    ref.close()


@pytest.mark.xfail(reason="test needs CV3 update")
def test_correct_tilt():
    """
    Example provided by Catarina.
    """
    xtilt = 0.35896975
    ytilt = 0.1343827
    #ztilt = None
    corrected_theta_x = 0.02942671219861111
    corrected_theta_y = 0.00018649006677464447
    #corrected_theta_z = -0.2523269848788889
    disp = {'gwa_tiltx': {'temperatures': [39.58],
                          'tilt_model': astmodels.Polynomial1D(1, c0=3307.85402614,
                                                               c1=-9182.87552123),
                          'unit': 'arcsec',
                          'zeroreadings': [0.35972327]},
            'gwa_tilty': {'temperatures': [39.58],
                          'tilt_model': astmodels.Polynomial1D(1, c0=0.0, c1=0.0),
                          'unit': 'arcsec',
                          'zeroreadings': [0.0]},
            'instrument': 'NIRSPEC',
            'reftype': 'DISPERSER',
            'theta_x': 0.02942671219861111,
            'theta_y': -0.0007745488724972222,
            #'theta_z': -0.2523269848788889,
            'tilt_x': 0.0,
            'tilt_y': -8.8
            }
    disp_corrected = nirspec.correct_tilt(disp, xtilt, ytilt)#, ztilt)
    assert np.isclose(disp_corrected['theta_x'], corrected_theta_x)
    #assert(np.isclose(disp_corrected['theta_z'], corrected_theta_z))
    assert np.isclose(disp_corrected['theta_y'], corrected_theta_y)


def test_msa_configuration_normal():
    """
    Test the get_open_msa_slits function.
    """

    # Test 1: Reasonably normal as well
    msa_meta_id = 12
    msaconfl = get_file_path('msa_configuration.fits')
    slitlet_info = nirspec.get_open_msa_slits(msaconfl, msa_meta_id)
    ref_slit = Slit(55, 9376, 251, 26, -5.15, 0.55, 4, 1, 5, '95065_1', '2122',
                      '2122', 0.13, -0.31716078999999997, -0.18092266)
    _compare_slits(slitlet_info[0], ref_slit)


def test_msa_configuration_no_background():
    """
    Test the get_open_msa_slits function.
    """
    # Test 2: Two main shutters, not allowed and should fail
    msa_meta_id = 13
    msaconfl = get_file_path('msa_configuration.fits')
    with pytest.raises(ValueError):
        slitlet_info = nirspec.get_open_msa_slits(msaconfl, msa_meta_id)


def test_msa_configuration_all_background():
    """
    Test the get_open_msa_slits function.
    """

    # Test 3:  No non-background, not acceptable.
    msa_meta_id = 14
    msaconfl = get_file_path('msa_configuration.fits')
    slitlet_info = nirspec.get_open_msa_slits(msaconfl, msa_meta_id)
    ref_slit = Slit(57, 616, 251, 2, 22.45, 25.85, 4, 1, 3, '95065_1', '2122',
                    '2122', 0.13, -0.5, -0.5)
    _compare_slits(slitlet_info[0], ref_slit)



def test_msa_configuration_row_skipped():
    """
    Test the get_open_msa_slits function.
    """

    # Test 4: One row is skipped, should be acceptable.
    msa_meta_id = 15
    msaconfl = get_file_path('msa_configuration.fits')
    slitlet_info = nirspec.get_open_msa_slits(msaconfl, msa_meta_id)
    ref_slit = Slit(58, 8646, 251, 24, -2.85, 5.15, 4, 1, 6, '95065_1', '2122',
                      '2122', 0.130, -0.31716078999999997, -0.18092266)
    _compare_slits(slitlet_info[0], ref_slit)


def test_msa_configuration_multiple_returns():
    """
    Test the get_open_msa_slits function.
    """
    # Test 4: One row is skipped, should be acceptable.
    msa_meta_id = 16
    msaconfl = get_file_path('msa_configuration.fits')
    slitlet_info = nirspec.get_open_msa_slits(msaconfl, msa_meta_id)
    ref_slit1 = Slit(59, 8651, 256, 24, -2.85, 5.15, 4, 1, 6, '95065_1', '2122',
                     '2122', 0.13000000000000003, -0.31716078999999997, -0.18092266)
    ref_slit2 = Slit(60, 11573, 258, 32, -2.85, 4, 4, 2, 6, '95065_2', '172',
                     '172', 0.70000000000000007, -0.31716078999999997, -0.18092266)
    _compare_slits(slitlet_info[0], ref_slit1)
    _compare_slits(slitlet_info[1], ref_slit2)
