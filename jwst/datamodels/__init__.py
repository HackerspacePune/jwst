# Copyright (C) 2010 Association of Universities for Research in Astronomy(AURA)
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#     1. Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#
#     2. Redistributions in binary form must reproduce the above
#       copyright notice, this list of conditions and the following
#       disclaimer in the documentation and/or other materials provided
#       with the distribution.
#
#     3. The name of AURA and its representatives may not be used to
#       endorse or promote products derived from this software without
#       specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY AURA ``AS IS'' AND ANY EXPRESS OR IMPLIED
# WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL AURA BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS
# OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR
# TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
# USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
# DAMAGE.

from __future__ import absolute_import, division, print_function

__version__ = '0.7.4'

import numpy as np
from os.path import basename
from astropy.extern import six
from astropy.io import registry

from . import ndmodel

from .model_base import DataModel
from .amilg import AmiLgModel
from .asn import AsnModel
from .combinedspec import CombinedSpecModel
from .container import ModelContainer
from .contrast import ContrastModel
from .cube import CubeModel
from .dark import DarkModel
from .darkMIRI import DarkMIRIModel
from .drizpars import DrizParsModel, NircamDrizParsModel, MiriImgDrizParsModel
from .outlierpars import OutlierParsModel, NircamOutlierParsModel, MiriImgOutlierParsModel
from .drizproduct import DrizProductModel
from .ifucubepars import IFUCubeParsModel, NirspecIFUCubeParsModel, MiriIFUCubeParsModel
from .throughput import ThroughputModel
from .flat import FlatModel
from .fringe import FringeModel
from .gain import GainModel
from .gls_rampfit import GLS_RampFitModel
from .guiderraw import GuiderRawModel
from .guidercal import GuiderCalModel
from .ifucube import IFUCubeModel
from .image import ImageModel
from .ipc import IPCModel
from .irs2 import IRS2Model
from .lastframe import LastFrameModel
from .level1b import Level1bModel
from .linearity import LinearityModel
from .mask import MaskModel
from .miri_ramp import MIRIRampModel
from .multiexposure import MultiExposureModel
from .multiprod import MultiProductModel
from .multislit import MultiSlitModel
from .multispec import MultiSpecModel
from .nirspec_flat import NRSFlatModel, NirspecFlatModel, NirspecQuadFlatModel
from .pathloss import PathlossModel
from .persat import PersistenceSatModel
from .photom import PhotomModel, FgsPhotomModel, NircamPhotomModel, NirissPhotomModel
from .photom import NirspecPhotomModel, NirspecFSPhotomModel
from .photom import MiriImgPhotomModel, MiriMrsPhotomModel
from .pixelarea import PixelAreaModel, NirspecSlitAreaModel, NirspecMosAreaModel, NirspecIfuAreaModel
from .psfmask import PsfMaskModel
from .quad import QuadModel
from .ramp import RampModel
from .rampfitoutput import RampFitOutputModel
from .readnoise import ReadnoiseModel
from .reference import ReferenceFileModel, ReferenceImageModel, ReferenceCubeModel, ReferenceQuadModel
from .reset import ResetModel
from .resolution import ResolutionModel, MiriResolutionModel
from .rscd import RSCDModel
from .saturation import SaturationModel
from .source_container import SourceModelContainer
from .spec import SpecModel
from .straylight import StrayLightModel
from .superbias import SuperBiasModel
from .trapdensity import TrapDensityModel
from .trappars import TrapParsModel
from .trapsfilled import TrapsFilledModel
from .wcs_ref_models import *
from .util import open



__all__ = [
    'open',
    'DataModel', 'AmiLgModel', 'AsnModel',
    'CameraModel', 'CollimatorModel',
    'CombinedSpecModel', 'ContrastModel', 'CubeModel',
    'DarkModel', 'DarkMIRIModel',
    'DisperserModel', 'DistortionModel', 'DistortionMRSModel',
    'DrizProductModel',
    'DrizParsModel', 'NircamDrizParsModel', 'MiriImgDrizParsModel',
    'FilteroffsetModel',
    'FlatModel', 'NRSFlatModel', 'NirspecFlatModel', 'NirspecQuadFlatModel',
    'FOREModel', 'FPAModel',
    'FringeModel', 'GainModel', 'GLS_RampFitModel',
    'GuiderRawModel', 'GuiderCalModel',
    'IFUCubeModel',
    'IFUCubeParsModel', 'NirspecIFUCubeParsModel', 'MiriIFUCubeParsModel',
    'IFUFOREModel', 'IFUPostModel', 'IFUSlicerModel',
    'ImageModel', 'IPCModel', 'IRS2Model', 'LastFrameModel', 'Level1bModel',
    'LinearityModel', 'MaskModel', 'ModelContainer', 'MSAModel',
    'MultiExposureModel', 'MultiProductModel', 'MultiSlitModel',
    'MultiSpecModel', 'OTEModel',
    'OutlierParsModel', 'MiriImgOutlierParsModel', 'NircamOutlierParsModel',
    'PathlossModel',
    'PersistenceSatModel',
    'PixelAreaModel', 'NirspecSlitAreaModel', 'NirspecMosAreaModel', 'NirspecIfuAreaModel',
    'ThroughputModel',
    'PhotomModel', 'FgsPhotomModel', 'MiriImgPhotomModel', 'MiriMrsPhotomModel',
    'NircamPhotomModel', 'NirissPhotomModel', 'NirspecPhotomModel', 'NirspecFSPhotomModel',
    'QuadModel', 'RampModel', 'MIRIRampModel',
    'RampFitOutputModel', 'ReadnoiseModel',
    'ReferenceFileModel', 'ReferenceCubeModel', 'ReferenceImageModel', 'ReferenceQuadModel',
    'RegionsModel', 'ResetModel',
    'ResolutionModel', 'MiriResolutionModel',
    'RSCDModel', 'SaturationModel', 'SpecModel',
    'StrayLightModel', 'SuperBiasModel', 'SpecwcsModel',
    'TrapDensityModel', 'TrapParsModel', 'TrapsFilledModel',
    'WavelengthrangeModel']

_all_models = __all__[1:]
_local_dict = dict(locals())
_defined_models = { k: _local_dict[k] for k in _all_models }

# Initialize the astropy.io registry
with registry.delay_doc_updates(DataModel):
    registry.register_reader('datamodel', DataModel, ndmodel.read)
    registry.register_writer('datamodel', DataModel, ndmodel.write)
    registry.register_identifier('datamodel', DataModel, ndmodel.identify)


'''
def test(verbose=False) :
    import nose

    # get the pandokia plugin if it is available (it will only
    # do anything if we are run from pandokia).
    try :
        import pandokia.helpers.nose_plugin as nose_plugin
    except ImportError :
        nose_plugin = None

    if nose_plugin :
        addplugins = [nose_plugin.Pdk()]
    else :
        addplugins = None

    # get the name of the test package
    argv = ['nosetests', '--exe', __name__ + '.tests']

    import jwst.datamodels.tests

    print ("ARGS", argv)

    # run nose
    return nose.main(argv = argv,  addplugins=addplugins)
'''
