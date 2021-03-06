"""test_level3_dithers: Test of spectrographic rules."""
from __future__ import absolute_import
from glob import glob
import pytest
import re

from .helpers import (
    BasePoolRule,
    PoolParams,
    combine_pools,
    registry_level3_only,
    t_path
)

from .. import generate
from ..main import constrain_on_candidates


class TestLevel3Spectrographic(BasePoolRule):

    pools = [
        PoolParams(
            path=[
                t_path('data/pool_005_spec_niriss.csv'),
                t_path('data/pool_006_spec_nirspec.csv'),
                t_path('data/pool_007_spec_miri.csv'),
            ],
            n_asns=7,
            n_orphaned=0
        ),
    ]

    valid_rules = [
        'Asn_MIRI_LRS_FIXEDSLIT',
        'Asn_NIR_SO_SLITLESS',
        'Asn_NRS_FIXEDSLIT',
        'Asn_NRS_MSA',
        'Asn_MIRI_IFU',
        'Asn_NRS_IFU'
    ]


@pytest.fixture(
    scope='module',
    params=[
        (
            'o001',
            'spec3',
            'jw99009-o001_spec3_\d{3}_asn',
            'jw99009-o001_t001_nirspec_f100lp-g140m',
            set(('science', 'target_acquistion', 'autowave'))
        ),
        (
            'o002',
            'spec3',
            'jw99009-o002_spec3_\d{3}_asn',
            'jw99009-o002_t003_nirspec_f100lp-g140h',
            set(('science', 'target_acquistion', 'autoflat', 'autowave'))
        ),
        (
            'o003',
            'spec3',
            'jw99009-o003_spec3_\d{3}_asn',
            'jw99009-o003_t002_nirspec_clear',
            set(('science', 'target_acquistion', 'autowave'))
        ),
    ]
)
def nirspec_params(request):
    cid, asn_type, asn_name, product_name, exptypes = request.param
    pool = combine_pools(t_path('data/pool_006_spec_nirspec.csv'))
    gc = {
        'asn_candidate': constrain_on_candidates((cid,))
    }
    rules = registry_level3_only(global_constraints=gc)
    asns, orphaned = generate(pool, rules)
    return asns, asn_type, asn_name, product_name, exptypes


def test_nirspec_modes(nirspec_params):
    asns, asn_type, asn_name, product_name, exptypes = nirspec_params

    assert len(asns) == 1
    asn = asns[0]
    assert asn['asn_type'] == asn_type
    assert re.match(asn_name, asn.asn_name)
    product = asn['products'][0]
    assert product['name'] == product_name
    found_exptypes = set(
        member['exptype']
        for member in product['members']
    )
    assert found_exptypes == exptypes


@pytest.fixture(
    scope='module',
    params=[
        (
            'o007',
            'spec3',
            'jw99009-o007_spec3_\d{3}_asn',
            'jw99009-o007_t001_miri',
        ),
        (
            'o008',
            'spec3',
            'jw99009-o008_spec3_\d{3}_asn',
            'jw99009-o008_t001_miri',
        ),
        (
            'o009',
            'spec3',
            'jw99009-o009_spec3_\d{3}_asn',
            'jw99009-o009_t001_miri'
        ),
        (
            'o010',
            'spec3',
            'jw99009-o010_spec3_\d{3}_asn',
            'jw99009-o010_t001_miri'
        ),
        (
            'o011',
            'spec3',
            'jw99009-o011_spec3_\d{3}_asn',
            'jw99009-o011_t001_miri'
        ),
    ]
)
def miri_params(request):
    cid, asn_type, asn_name, product_name = request.param
    pool = combine_pools(t_path('data/pool_007_spec_miri.csv'))
    gc = {
        'asn_candidate': constrain_on_candidates((cid,))
    }
    rules = registry_level3_only(global_constraints=gc)
    asns, orphaned = generate(pool, rules)
    return asns, asn_type, asn_name, product_name


def test_miri_modes(miri_params):
    asns, asn_type, asn_name, product_name = miri_params

    assert len(asns) == 1
    asn = asns[0]
    assert asn['asn_type'] == asn_type
    assert re.match(asn_name, asn.asn_name)
    assert asn['products'][0]['name'] == product_name
