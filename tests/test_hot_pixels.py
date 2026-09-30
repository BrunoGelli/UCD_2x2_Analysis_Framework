import hashlib
import json
from pathlib import Path

import h5py
import numpy as np
import pytest

from ucd2x2.core.hot_pixels import (FIELDS, STAT_NAMES, CleaningPolicy, EventHitReader,
    EventCleaner, PixelAccumulator, HotPixelMask, build_hot_mask, pixel_ids, decode_pixel, product_stem)
from ucd2x2.core.event_scan import event_summary, scan_events, load_candidates

DTYPE = np.dtype([(f,"u8") for f in FIELDS] + [(f,"f8") for f in ("x","y","z","Q")] + [("is_disabled","?")])


def hits(channels, charges=None):
    a = np.zeros(len(channels), dtype=DTYPE)
    a["io_group"],a["io_channel"],a["chip_id"] = 1,2,3
    a["channel_id"] = channels
    a["Q"] = 1 if charges is None else charges
    a["x"] = np.arange(len(a))
    return a


def write_flow(path, arrays, sparse=False):
    """Genuine event->hit references; target rows are deliberately shuffled."""
    lengths = list(map(len,arrays))
    flat = np.concatenate(arrays) if arrays else np.empty(0,dtype=DTYPE)
    permutation = np.random.default_rng(42).permutation(len(flat)) if sparse else np.arange(len(flat))
    stored = flat[permutation]
    inverse = np.argsort(permutation)
    counts = np.asarray(lengths,dtype=np.int64)
    stops = np.cumsum(counts)
    starts = stops-counts
    regions = np.empty(len(arrays),dtype=[("start","u8"),("stop","u8")])
    regions["start"],regions["stop"] = starts,stops
    pairs = np.column_stack([np.repeat(np.arange(len(arrays)),counts),inverse]).astype("u8")
    events = np.zeros(len(arrays),dtype=[("id","u8")]);events["id"] = np.arange(len(arrays))+100
    with h5py.File(path,"w") as f:
        f.create_dataset("charge/events/data",data=events)
        for collection in ("prompt","final"):
            base = f"charge/calib_{collection}_hits"
            f.create_dataset(base+"/data",data=stored)
            f.create_dataset("charge/events/ref/"+base+"/ref",data=pairs)
            f.create_dataset("charge/events/ref/"+base+"/ref_region",data=regions)


@pytest.mark.parametrize("sparse",[False,True])
@pytest.mark.parametrize("block_rows",[1,4,1000])
def test_reference_reader_is_exact_with_empty_events(tmp_path,sparse,block_rows):
    arrays = [hits([1,2,3]),hits([]),hits([5,5,5,5]),hits([1,4])]
    path = tmp_path/"flow.h5";write_flow(path,arrays,sparse)
    with EventHitReader(path,block_rows=block_rows) as reader:
        for i,expected in enumerate(arrays):
            assert np.array_equal(reader.get(i),expected)
            assert reader.event_id(i)==i+100
        assert reader.h5.mode=="r"
        with pytest.raises(IndexError):reader.get(-1)


def test_reader_rejects_corrupt_refs(tmp_path):
    path=tmp_path/"flow.h5";write_flow(path,[hits([1,2])])
    with h5py.File(path,"r+") as f:f['charge/events/ref/charge/calib_prompt_hits/ref'][0,0]=99
    with EventHitReader(path) as reader:
        with pytest.raises(ValueError,match="inconsistent"):reader.get(0)


def test_hardware_keys_are_collision_free_and_strict():
    a=hits([0,0,65535]);a['io_group']=[1,2,65535];a['chip_id'][2]=65535;a['io_channel'][2]=65535
    ids=pixel_ids(a)
    assert len(np.unique(ids))==3
    assert decode_pixel(ids[2])==(65535,65535,65535,65535)
    a['channel_id'][0]=65536
    with pytest.raises(ValueError,match="range"):pixel_ids(a)
    with pytest.raises(ValueError,match="missing"):pixel_ids(np.zeros(1,dtype=[('y','f8'),('z','f8')]))


def test_accumulator_matches_counts_across_flushes():
    a=PixelAccumulator(flush_pairs=1)
    for channels in ([1,1,1,1,2,2],[1,2,2,3],[],[2,3,3,3]):a.add(hits(channels))
    a.flush()
    assert a.n_events==4
    assert np.array_equal(a.stats,np.array([[5,2,1,1,1,4],[5,3,2,0,0,2],[4,2,1,1,0,3]]))


def test_exact_thresholds_non_destructive_union(tmp_path):
    arrays=[hits([1]*4+[2]*3+[3]),hits([4])]
    path=tmp_path/'flow.h5';write_flow(path,arrays)
    before=hashlib.sha256(path.read_bytes()).hexdigest()
    mask=build_hot_mask(path,tmp_path/'mask.pkl',policy=CleaningPolicy(global_mean_max=None))
    local=EventCleaner(mask)
    original=arrays[0].copy()
    keep,counts=local.apply(arrays[0])
    assert keep.tolist()==[False]*4+[True]*4
    assert np.array_equal(arrays[0],original)
    assert counts['removed_local']==4
    global_cleaner=EventCleaner(mask,CleaningPolicy(global_mean_max=1))
    keep,counts=global_cleaner.apply(arrays[0])
    assert keep.sum()==1
    assert sum(counts['removed_'+k] for k in ('global','local','invalid','disabled'))+keep.sum()==len(original)
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before


def test_global_strictly_greater_and_occupancy(tmp_path):
    path=tmp_path/'flow.h5';write_flow(path,[hits([1,2]),hits([1,2,2]),hits([1])])
    mask=build_hot_mask(path)
    assert len(mask.bad_pixels())==0  # both totals equal N=3
    assert len(mask.bad_pixels(CleaningPolicy(max_event_fraction=2/3)))==1  # channel 1 in all events


def test_cache_source_and_collection_validation(tmp_path):
    a=tmp_path/'a.h5';b=tmp_path/'b.h5';write_flow(a,[hits([1])]);write_flow(b,[hits([1])])
    mask=build_hot_mask(a,tmp_path/'a.pkl')
    loaded=HotPixelMask.load(tmp_path/'a.pkl')
    with EventHitReader(a) as reader:loaded.validate(reader)
    with EventHitReader(b) as reader:
        with pytest.raises(ValueError,match='mismatch'):loaded.validate(reader)
    with EventHitReader(a,'final') as reader:
        with pytest.raises(ValueError,match='mismatch'):loaded.validate(reader)
    assert product_stem(a)!=product_stem(b)
    with pytest.raises(ValueError,match='overwrite'):mask.save(a)
    with pytest.raises(ValueError,match='legacy'):HotPixelMask({'bad_pixels':set()})


def test_scanner_and_cleaner_agree_signed_charge(tmp_path):
    arrays=[hits([1,1,1,1,2],[100,100,100,100,-2]),hits([3,4],[4,5]),hits([])]
    path=tmp_path/'flow.h5';write_flow(path,arrays,True)
    mask=build_hot_mask(path)
    rows=scan_events(path,tmp_path/'out.csv',mask)
    assert [r['event_index'] for r in rows]==[1,2,0]
    assert rows[-1]['total_Q']==-2 and rows[-1]['positive_Q']==0
    with EventHitReader(path) as reader:
        loaded=load_candidates(tmp_path/'out.csv',reader,EventCleaner(mask),mask)
        assert [r['event_index'] for r in loaded]==[1,2,0]
        with pytest.raises(ValueError,match='mismatch'):
            load_candidates(tmp_path/'out.csv',reader,EventCleaner(mask,CleaningPolicy(event_max_hits=2)),mask)


def test_disabled_and_nan_are_removed_separately():
    a=hits([1,2,3,4],[-5,2,np.nan,4]);a['is_disabled'][1]=True;a['x'][3]=np.inf
    keep,report=EventCleaner().apply(a)
    assert keep.tolist()==[True,False,False,False]
    assert report['removed_invalid']==2 and report['removed_disabled']==1
    assert event_summary(a[keep])['total_Q']==-5


def test_empty_file(tmp_path):
    path=tmp_path/'empty.h5';write_flow(path,[])
    mask=build_hot_mask(path,tmp_path/'empty.pkl')
    assert mask.summary()['n_hot_pixels']==0
    assert scan_events(path,tmp_path/'empty.csv',mask)==[]
    assert Path(str(tmp_path/'empty.csv')+'.json').is_file()


@pytest.mark.parametrize('kwargs',[dict(event_max_hits=-1),dict(global_mean_max=-1),dict(global_mean_max=float('nan')),dict(max_event_fraction=1.1)])
def test_bad_policy(kwargs):
    with pytest.raises(ValueError):CleaningPolicy(**kwargs)


def test_geometry_is_a_diagnostic_not_a_hidden_hit_cut():
    a=hits([1,2],[4,5]);a['x']=[20,9000];a['y']=0;a['z']=20
    keep,_=EventCleaner().apply(a)
    assert keep.all()
    report=event_summary(a)
    assert report['total_Q']==9
    assert report['n_in_nominal_volume']==1 and report['Q_in_nominal_volume']==4


def test_charge_threshold_does_not_depend_on_plot_sampling():
    a=hits(list(range(100)),np.arange(100,dtype=float))
    keep,_=EventCleaner().apply(a)
    assert event_summary(a[keep])['total_Q']==4950
