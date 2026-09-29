import json
from pathlib import Path
import subprocess
import sys
import pytest
from ucd2x2.cli import build_event_display_command,_build_parser,policy_from_args


def test_cli_help_runs_successfully():
    proc=subprocess.run([sys.executable,'-m','ucd2x2.cli','--help'],capture_output=True,text=True,check=True)
    for command in ('event-display','stage2-run','build-hot-mask','scan-events'):
        assert command in proc.stdout


def test_stage2_run_via_cli_writes_summary_json(tmp_path):
    out=tmp_path/'stage2_summary.json'
    subprocess.run([sys.executable,'-m','ucd2x2.cli','stage2-run','--input','tests/sample_data.hdf5',
                    '--config','configs/stage2/repeated_pixel_then_dbscan.yaml','--output',str(out),
                    '--max-events','2'],check=True)
    payload=json.loads(out.read_text())
    assert payload['n_events_processed']<=2
    assert 'total_clusters' in payload


def test_build_event_display_command_defaults():
    cmd=build_event_display_command('tests/sample_data.hdf5')
    assert cmd[:4]==[sys.executable,'-m','panel','serve']
    assert '--show' in cmd
    assert cmd[-3:]==['--args','--h5',str(Path('tests/sample_data.hdf5').resolve())]


def test_build_event_display_command_optional_args():
    cmd=build_event_display_command('a.h5',show=False,port=5007,max_hits=120)
    assert '--no-show' not in cmd and '--show' not in cmd
    assert cmd[cmd.index('--port')+1]=='5007'
    assert cmd[cmd.index('--max_hits')+1]=='120'


def test_jupyter_proxy_and_clean_app():
    cmd=build_event_display_command('a.h5',hot_mask='a.pkl',jupyter=True,
                                     service_prefix='/user/example/server/',port=5006)
    assert cmd[4].endswith('clean_panel.py')
    assert cmd[cmd.index('--root-path')+1]=='/user/example/server/proxy/5006/'
    assert cmd[cmd.index('--allow-websocket-origin')+1]=='jupyter.nersc.gov'
    assert cmd[cmd.index('--address')+1]=='127.0.0.1'
    assert '--show' not in cmd
    with pytest.raises(ValueError,match='INSIDE'):
        build_event_display_command('a.h5',jupyter=True,service_prefix='')


def test_explicit_cut_disable():
    args=_build_parser().parse_args(['scan-events','a.h5','-o','a.csv','--global-mean-max','none',
                                    '--event-max-hits-per-pixel','0','--max-event-fraction','0.1'])
    policy=policy_from_args(args)
    assert policy.global_mean_max is None and policy.event_max_hits==0 and policy.max_event_fraction==.1
