"""Publish the locally reviewed isolated thesis back into the working checkout.

Keeps the original numerical manifest and its viewer-source identity. A separate
record proves which non-numerical viewer changes are present in the working tree.
Requires the final manuscript review; it cannot certify a running rebuild.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

HERE=Path(__file__).resolve().parent
WORK=HERE.parents[1]


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def require(condition,message):
 if not condition: raise ValueError(message)

def load_helper():
 spec=importlib.util.spec_from_file_location('isolated_continuation', HERE/'continue_isolated_rebuild.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 return module

def main(run):
 record=json.loads((HERE/'isolated-continuation.json').read_text())
 require(Path(record['run_dir']).resolve()==run.resolve(),'Unexpected continuation')
 manifest_path=run/'review-inputs/manifest.json'
 manifest_bytes=manifest_path.read_bytes();manifest=json.loads(manifest_bytes)
 review_path=run/'review-inputs/manuscript-review.json'
 review_bytes=review_path.read_bytes();review=json.loads(review_bytes)
 require(record['status']=='complete' and manifest['status']=='complete','Numerical completion required')
 require(len(manifest['stages'])==39 and all(s['status']=='complete' for s in manifest['stages']), 'Incomplete stage chain')
 require(review['numerical_manifest_sha256']==sha(manifest_path),'Review input identity differs')
 helper=load_helper();frozen=helper.FROZEN;driver=helper.load_driver()
 require(driver.source_hash(frozen)==review['source_sha256'],'Reviewed manuscript changed')
 require(driver.numerical_source_hash(frozen)==manifest['numerical_source_sha256'],'Numerical source changed')
 require(driver.current_cleaning(frozen)==manifest['cleaning'],'Cleaning changed')
 for name,discipline in driver.DISCIPLINES.items():
  require(driver.validate_snapshot(discipline.config().derived_dir,manifest['cleaning'])==manifest['datasets'][name],f'Archive changed: {name}')
 proof=helper.viewer_difference_proof()
 required=set(driver.required_outputs())
 require(required<=set(manifest['outputs']),'Reviewed manuscript has unidentified inputs')
 for name,row in manifest['outputs'].items():
  require(sha(frozen/'thesis/generated'/name)==row['sha256'],f'Result changed: {name}')
 require(sha(frozen/'thesis/main.pdf')==review['pdf_sha256'],'Reviewed PDF changed')
 annotation_src=Path(manifest['annotation_dir'])
 annotation_dest=WORK/'annotations/phase_labeling'/manifest['run_id']
 require(annotation_src.is_dir(),'Annotation pack missing')
 require(not annotation_dest.exists(),'Working annotation pack already exists; inspect before replacing')
 # Refuse to overwrite any concurrent generated-data edit in the working tree.
 sources=[p for p in (frozen/'thesis/generated').iterdir() if p.is_file() and not p.name.startswith('._')]
 changes=[]
 for src in sorted(sources):
  dest=WORK/'thesis/generated'/src.name
  if dest.exists() and sha(dest)!=sha(src):
   expected=record['copied_generated'].get(src.name)
   require(expected and sha(dest)==expected['sha256'],f'Working generated file edited concurrently: {src.name}')
   changes.append((src,dest))
  elif not dest.exists(): changes.append((src,dest))
 backup=run/'checkout-before-final'
 require(not (HERE/'reviewed-checkout.json').exists(),'Working publication already recorded')
 backup.mkdir(exist_ok=False)
 copied={}
 for src,dest in changes:
  if dest.exists():shutil.copy2(dest,backup/dest.name)
  shutil.copy2(src,dest);require(sha(src)==sha(dest),f'Copy differs: {dest}')
  copied[dest.name]=sha(dest)
 shutil.copytree(annotation_src,annotation_dest)
 annotations={str(p.relative_to(annotation_src)):sha(p) for p in annotation_src.rglob('*') if p.is_file()}
 require(all(sha(annotation_dest/n)==digest for n,digest in annotations.items()),'Annotation copy differs')
 pdf=WORK/'thesis/main.pdf'
 if pdf.exists():shutil.copy2(pdf,backup/'previous-main.pdf')
 shutil.copy2(frozen/'thesis/main.pdf',pdf)
 require(sha(pdf)==review['pdf_sha256'],'Working PDF copy differs')
 require(helper.viewer_difference_proof()==proof,'Source changed during publication')
 for name,discipline in driver.DISCIPLINES.items():
  require(driver.validate_snapshot(discipline.config().derived_dir,manifest['cleaning'])==manifest['datasets'][name],f'Archive changed during publication: {name}')
 require(manifest_path.read_bytes()==manifest_bytes and review_path.read_bytes()==review_bytes,'Original record altered')
 required_hashes={name:sha(WORK/'thesis/generated'/name) for name in manifest['outputs']}
 require(all(required_hashes[n]==row['sha256'] for n,row in manifest['outputs'].items()),'Working required result mismatch')
 report={'reviewed_utc':datetime.now(UTC).isoformat(),'numerical_run':str(run),
  'numerical_manifest_sha256':sha(run/'manifest.json'),'review_input_manifest_sha256':sha(manifest_path),
  'manuscript_review_sha256':sha(review_path),'executed_numerical_source_sha256':manifest['numerical_source_sha256'],
  'working_source_sha256':driver.source_hash(WORK),'working_numerical_source_sha256':driver.numerical_source_hash(WORK),
  'viewer_difference_proof':proof,'cleaning':manifest['cleaning'],'datasets':manifest['datasets'],
  'copied_generated':copied,'required_results_sha256':required_hashes,'pdf_sha256':sha(pdf),
  'annotation_pack':str(annotation_dest),'annotations_sha256':annotations,
  'scope':'Final locally reviewed thesis from the completed isolated run; numerical dependencies identical, four separately identified viewer files differ. Original numerical manifests unchanged.',
  'script_sha256':sha(Path(__file__))}
 (HERE/'reviewed-checkout.json').write_text(json.dumps(report,indent=2)+'\n')
 print(f'Reviewed thesis copied to {pdf}; source reconciliation in {HERE/"reviewed-checkout.json"}')

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',required=True,type=Path)
 main(parser.parse_args().run.resolve())
