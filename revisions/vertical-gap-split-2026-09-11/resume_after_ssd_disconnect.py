"""Recover the unchanged numerical run after validating the remounted SSD.

--prepare copies bootstrap coordinates and metadata internally, links read-only
baseline increment pools, validates them, and records the completed stage prefix.
--run repeats the structural archive verification, then resumes at transport_full
with the canonical reporter's --reuse contract. Scientific source files stay unchanged.
Run through caffeinate -im to prevent system and disk idle sleep; this does not
resolve a faulty cable, enclosure or power supply.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib.util
import json
import os
import pickle
import runpy
import shutil
import sys
import time
import uuid
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'src'))
from soaring.analysis.observables.archive_diagnostics import load_measurement
from soaring.analysis.observables.segment_support import increment_starts
spec=importlib.util.spec_from_file_location('recovery_driver',ROOT/'scripts/rebuild_thesis.py')
DRIVER=importlib.util.module_from_spec(spec)
spec.loader.exec_module(DRIVER)
RECORD=HERE/'recovery-run.json'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def copy_checked(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    temporary=target.with_name(target.name+'.copying')
    shutil.copy2(source,temporary)
    sha=digest(source)
    if digest(temporary)!=sha: raise ValueError(f'Copy mismatch: {source}')
    temporary.replace(target)
    return {'source':str(source),'target':str(target),'sha256':sha,'bytes':target.stat().st_size}


def verify_staged_inputs(proofs):
    """Reject inputs modified between preparation and execution, including links."""
    for proof in proofs:
        target=Path(proof['target'])
        if proof.get('operation')=='read-only input link':
            if not target.is_symlink() or target.resolve()!=Path(proof['source']).resolve():
                raise ValueError(f'Staged input link changed: {target}')
        if target.stat().st_size!=proof['bytes'] or digest(target)!=proof['sha256']:
            raise ValueError(f'Staged input changed: {target}')


def require(condition,message):
    if not condition:raise ValueError(message)


def validate_store(directory,lags):
    directory=Path(directory)
    counts=json.loads((directory/'counts.json').read_text())
    require(len(counts)==len(lags),'Lag count differs from the estimator contract')
    for j,n in enumerate(counts):
        require(isinstance(n,int) and n>=0,'Invalid increment count')
        for kind,width in (('vectors',16),('owners',4)):
            path=directory/f'{kind}-{j}.bin'
            require(path.stat().st_size==n*width,f'Incorrect pool byte size: {path}')
    measured=load_measurement(directory)
    frames=measured['_frames']
    require(len(frames)>0,'Empty flight store')
    require(len({r['flight_id'] for r in frames.rows})==len(frames),'Duplicate flight IDs')
    offset=0
    for row in frames.rows:
        require(row['offset']==offset and row['length']>0,'Invalid coordinate offsets')
        stop=0
        for lo,hi in row['segments']:
            require(lo==stop and hi>lo,'Invalid retained-segment ranges')
            stop=hi
        require(stop==row['length'],'Segment ranges do not cover the saved coordinates')
        offset+=row['length']
    require(offset==len(frames.positions),'Coordinate file and index disagree')
    for start in range(0,len(frames.positions),1000000):
        require(np.isfinite(frames.positions[start:start+1000000]).all(),'Non-finite coordinates')
    selected=np.unique(np.r_[np.linspace(0,len(frames)-1,25,dtype=int),
                             np.argmax([r['duration_s'] for r in frames.rows])])
    for tau,xy,owners in zip(lags,measured['vectors'],measured['owners'],strict=True):
        require(len(xy)==len(owners),'Increment/owner count mismatch')
        last=-1
        for start in range(0,len(owners),1000000):
            who=owners[start:start+1000000]
            require(np.isfinite(xy[start:start+1000000]).all(),'Non-finite increments')
            if len(who):
                require(who[0]>=last and who.min()>=0 and who.max()<len(frames),'Invalid increment owners')
                require((np.diff(who)>=0).all(),'Unordered increment owners')
                last=int(who[-1])
        for i in selected:
            row,pos=frames[int(i)]
            lag=int(tau//10)
            starts=increment_starts(row,len(pos),lag)
            lo,hi=np.searchsorted(owners,[i,i+1])
            np.testing.assert_array_equal(xy[lo:hi],pos[starts+lag]-pos[starts])
    return {'flights':len(frames),'positions':len(frames.positions),
            'oracle_flight_indexes':selected.tolist(),'all_pools_finite_and_owner_order_valid':True}


def guards(record):
    if DRIVER.source_hash(ROOT)!=record['source_sha256']: raise ValueError('Source changed')
    if DRIVER.numerical_source_hash(ROOT)!=record['numerical_source_sha256']: raise ValueError('Numerical source changed')
    if DRIVER.current_cleaning(ROOT)!=record['cleaning']: raise ValueError('Cleaning definition changed')
    for name,g in DRIVER.DISCIPLINES.items():
        if DRIVER.validate_snapshot(g.config().derived_dir,record['cleaning'])!=record['datasets'][name]:
            raise ValueError(f'{name}: source archive changed')


def locks(stack,parent):
    DRIVER._lock(stack,HERE/'.recovery.lock')
    DRIVER._lock(stack,parent.parent.parent/'.rebuild.lock')
    for g in DRIVER.DISCIPLINES.values(): DRIVER._lock(stack,g.config().derived_dir/'.preprocess.lock')


def prepare():
    failure=json.loads((HERE/'ssd-disconnection-20260912.json').read_text())
    parent=Path(failure['parent_run'])
    original=(parent/'manifest.json').read_bytes()
    previous=json.loads(original)
    if previous['run_id']!=failure['run_id']: raise ValueError('Unexpected parent run')
    if previous['status']=='complete': raise ValueError('Parent is already complete')
    record={k:previous[k] for k in ('source_sha256','numerical_source_sha256','cleaning','datasets','resources')}
    if record['source_sha256']!=failure['source_sha256']: raise ValueError('Unexpected interrupted source')
    guards(record)
    with ExitStack() as stack:
        locks(stack,parent)
        if RECORD.exists():
            existing=json.loads(RECORD.read_text())
            require(existing['status'] not in {'prepared','running','complete'},
                    'A prepared, running or completed recovery already exists')
        require((parent/'manifest.json').read_bytes()==original,'Parent changed before locking')
        guards(record)
        prefix=[]
        for s in previous['stages']:
            if s['status']!='complete':break
            prefix.append(copy.deepcopy(s))
        if len(prefix)!=23 or prefix[-1]['id']!='kinematics': raise ValueError('Unexpected completed prefix')
        run_id=datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
        run=HERE/'recovery-runs'/run_id
        arrays=run/'arrays'
        old=parent/'arrays'
        reporter=runpy.run_path(str(ROOT/'scripts/reporting/ch3_global_transport/generate_revision_diagnostics.py'))
        with (old/'ch3_revision_full.pkl').open('rb') as stream:saved=pickle.load(stream)
        contract=reporter['measurement_contract'](24,12,40,sample=False)
        reporter['validate_cache'](saved,contract)
        small=[p for p in old.iterdir() if p.is_file() and p.suffix in ('.npz','.parquet')]
        copies=sum(p.stat().st_size for p in small)
        scaling=0
        for directory in saved['directories'].values():
            source=Path(directory)
            if (source/'.incomplete').exists():raise ValueError(f'Incomplete baseline cache: {source}')
            copies+=sum((source/n).stat().st_size for n in ('positions.bin','flights.json','measurement.pkl','counts.json'))
            with (source/'measurement.pkl').open('rb') as stream:m=pickle.load(stream)
            scaling+=int(np.sum(m['quantile_control']['fixed_origin_counts']))*3*8*6
        if shutil.disk_usage(HERE).free<copies+scaling+2*1024**3:
            raise ValueError('Insufficient internal space for copied inputs, six display arrays and reserve')
        arrays.mkdir(parents=True)
        (run/'parent-manifest-before-recovery.json').write_bytes(original)
        logs=[]
        for index,stage in enumerate(prefix,1):
            log=parent/f"{index:02d}-{stage['id']}.log"
            logs.append(copy_checked(log,run/log.name))
        proofs=[copy_checked(p,arrays/p.name) for p in small]
        stores={}
        staged=copy.deepcopy(saved)
        for name,directory in saved['directories'].items():
            source=Path(directory);target=arrays/source.name;target.mkdir()
            for n in ('positions.bin','flights.json','measurement.pkl','counts.json'):
                proofs.append(copy_checked(source/n,target/n))
            for p in sorted(source.glob('*.bin')):
                if p.name=='positions.bin':continue
                (target/p.name).symlink_to(p.resolve())
                proofs.append({'source':str(p),'target':str(target/p.name),'sha256':digest(p),
                               'bytes':p.stat().st_size,'operation':'read-only input link'})
            stores[name]=validate_store(target,contract['lags_s'])
            staged['directories'][name]=str(target)
        with (arrays/'ch3_revision_full.pkl').open('wb') as stream:pickle.dump(staged,stream,protocol=5)
        completed={s['command'][1]:s['started_unix'] for s in prefix if s['command'][1].endswith('.py')}
        plan=DRIVER.load_plan(ROOT/'configs/rebuild.yaml')
        required=DRIVER.required_outputs()
        reused=DRIVER.check_fresh_outputs({n:p for n,p in required.items() if p in completed},completed,
                                         set(plan.get('historical_outputs',[])),ROOT/'thesis/generated')
        for s in prefix:s.update(reused_from=str(parent),source_sha256_at_execution=previous['source_sha256'])
        record.update(status='prepared',run_id=run_id,run_dir=str(run),source_root=str(ROOT),parent_run=str(parent),
                      parent_manifest_sha256=hashlib.sha256(original).hexdigest(),stages=prefix,
                      reused_outputs=reused,staged_inputs=proofs,store_checks=stores,preserved_logs=logs,
                      original_cache_sha256=digest(old/'ch3_revision_full.pkl'),
                      staged_cache_sha256=digest(arrays/'ch3_revision_full.pkl'),
                      orchestrator_sha256=digest(Path(__file__)),failure_record_sha256=digest(HERE/'ssd-disconnection-20260912.json'))
        guards(record)
        DRIVER.write_json(RECORD,record)
        print(f'Prepared validated local recovery: {run}',flush=True)


def run_prepared():
    record=json.loads(RECORD.read_text())
    if record['status']!='prepared':raise ValueError('Prepare a fresh validated recovery first')
    if record['orchestrator_sha256']!=digest(Path(__file__)):raise ValueError('Recovery orchestrator changed')
    parent=Path(record['parent_run']);run=Path(record['run_dir']);arrays=run/'arrays'
    guards(record)
    if digest(parent/'manifest.json')!=record['parent_manifest_sha256']:raise ValueError('Parent manifest changed')
    if digest(arrays/'ch3_revision_full.pkl')!=record['staged_cache_sha256']:raise ValueError('Staged cache changed')
    plan=DRIVER.load_plan(ROOT/'configs/rebuild.yaml')
    annotations=ROOT/'annotations/phase_labeling'/record['run_id']
    commands=DRIVER.commands(plan,arrays,annotations,clean=False,jobs=8,build=True)
    if [s['id'] for s in record['stages']]!=[name for name,_ in commands[:23]]:raise ValueError('Stage plan changed')
    commands=[(n,c+['--reuse'] if n=='transport_full' else c) for n,c in commands]
    os.environ['SOARING_MAX_WORKERS']='8'
    manifest={k:copy.deepcopy(record[k]) for k in ('run_id','source_root','source_sha256','numerical_source_sha256','cleaning','datasets','resources','stages')}
    manifest.update(status='running',started_utc=datetime.now(UTC).isoformat(),annotation_dir=str(annotations),
                    audit_dir=str(arrays),continuation=record)
    path=run/'manifest.json'
    completed={s['command'][1]:s['started_unix'] for s in manifest['stages'] if s['command'][1].endswith('.py')}
    historical=set(plan.get('historical_outputs',[]))
    owns_run=False
    try:
        with ExitStack() as stack:
            locks(stack,parent)
            current=json.loads(RECORD.read_text())
            require(current['status']=='prepared' and current['run_id']==record['run_id'],
                    'Recovery was already claimed by another process')
            owns_run=True
            guards(record)
            if digest(parent/'manifest.json')!=record['parent_manifest_sha256']:raise ValueError('Parent manifest changed')
            if digest(arrays/'ch3_revision_full.pkl')!=record['staged_cache_sha256']:raise ValueError('Staged cache changed')
            verify_staged_inputs(record['staged_inputs'])
            record['status']='running';DRIVER.write_json(RECORD,record)
            DRIVER.write_json(path,manifest)
            print('Reverify every cleaned fix after remount before reusing the completed prefix.',flush=True)
            start=time.time()
            DRIVER._run([sys.executable,'scripts/verify_dataset.py'],run/'recovery-verify.log')
            guards(record)
            for name,item in record['reused_outputs'].items():
                if digest(ROOT/'thesis/generated'/name)!=item['sha256']:raise ValueError(f'Reused product changed: {name}')
            manifest['recovery_verification']={'status':'complete','started_unix':start,'elapsed_seconds':time.time()-start}
            # Preserve the original bytes above; explicitly repair the stale running
            # status only after the remounted archive has passed verification.
            interrupted=json.loads((parent/'manifest.json').read_text())
            interrupted.update(status='failed',error='SSD disconnected during transport_full (SIGBUS)',
                               interruption_record=str(HERE/'ssd-disconnection-20260912.json'),
                               recovery_run=str(run))
            if interrupted['stages'][-1]['status']=='running':
                interrupted['stages'][-1]['status']='failed'
            DRIVER.write_json(parent/'manifest.json',interrupted)
            manifest['continuation']['parent_manifest_after_interruption_sha256']=digest(parent/'manifest.json')
            DRIVER.write_json(path,manifest)
            for index,(name,command) in enumerate(commands[23:],24):
                guards(record)
                if name=='latex':
                    manifest['outputs']=DRIVER.check_fresh_outputs(DRIVER.required_outputs(),completed,historical,ROOT/'thesis/generated')
                print(f'\n[{index}/{len(commands)}] {name}',flush=True)
                started=time.time();stage={'id':name,'command':command,'status':'running','started_unix':started}
                manifest['stages'].append(stage);DRIVER.write_json(path,manifest)
                DRIVER._run(command,run/f'{index:02d}-{name}.log')
                stage.update(status='complete',elapsed_seconds=time.time()-started)
                if len(command)>1 and command[1].endswith('.py'):completed[command[1]]=started
                DRIVER.write_json(path,manifest)
            guards(record)
            manifest['outputs']=DRIVER.check_fresh_outputs(DRIVER.required_outputs(),completed,historical,ROOT/'thesis/generated')
            manifest.update(status='complete',completed_utc=datetime.now(UTC).isoformat(),pdf_sha256=digest(ROOT/'thesis/main.pdf'))
            DRIVER.write_json(path,manifest)
    except BaseException as exc:
        if not owns_run:raise
        if manifest['stages'][-1]['status']=='running':manifest['stages'][-1]['status']='failed'
        manifest.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        DRIVER.write_json(path,manifest)
        record.update(status='failed',error=manifest['error'])
        DRIVER.write_json(RECORD,record)
        raise
    record['status']='complete';DRIVER.write_json(RECORD,record)
    print(f'Numerical recovery complete: {path}',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare',action='store_true');group.add_argument('--run',action='store_true')
    args=parser.parse_args()
    prepare() if args.prepare else run_prepared()
