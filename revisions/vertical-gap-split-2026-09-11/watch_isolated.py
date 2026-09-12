"""Record current isolated-stage status locally, without reading active Parquet outputs."""
from pathlib import Path
import json,time
from datetime import UTC,datetime
here=Path(__file__).resolve().parent
record=json.loads((here/'isolated-continuation.json').read_text())
run=Path(record['run_dir'])
while True:
 manifest=json.loads((run/'manifest.json').read_text()); stages=manifest['stages'];last=stages[-1]
 now=time.time();live={'observed_utc':datetime.now(UTC).isoformat(),'run_id':manifest['run_id'],'status':manifest['status'],'stage':last['id'],'completed_stages':sum(s['status']=='complete' for s in stages),'stage_elapsed_seconds':now-last['started_unix'] if last['status']=='running' else last.get('elapsed_seconds'),'manifest':str(run/'manifest.json'),'source_root':manifest['source_root']}
 (here/'isolated-live.json').write_text(json.dumps(live,indent=2)+'\n')
 if manifest['status'] in ('complete','failed'): break
 time.sleep(50)
