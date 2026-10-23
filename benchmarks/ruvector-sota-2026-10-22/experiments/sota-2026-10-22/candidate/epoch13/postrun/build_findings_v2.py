"""Append exact DEV-only annotation intersection evidence to immutable v1 findings."""
from pathlib import Path
import argparse,hashlib,json

def build(findings,coverage):
 f=json.loads(findings.read_text());c=json.loads(coverage.read_text())
 if f['status']!='REJECTED_DEV_GATE' or c['n']!=24 or c['confirmation_labels_or_annotations_read']:
  raise ValueError('Expected exposedDEV24only rejected study')
 f['supplement_version']=2
 f['v1_findings_sha256']=hashlib.sha256(findings.read_bytes()).hexdigest()
 f['exact_reference_coverage_sha256']=hashlib.sha256(coverage.read_bytes()).hexdigest()
 f['evidence_and_context']['exact_annotation_character_intersections']=c['summary']
 f['evidence_and_context']['reference_intersection_scope']=c['scope']
 f['next_distinct_question']['evidence']='Native fully retains every annotated reference character on9/15 reference-bearing queries (6Entailment,3Contradiction) yet gets0/9typed decisions correct. Lexical fullyretained9also0typed, positional7also0typed. This is evidence of a reader/task mismatch even where annotation references are present; it does not prove annotations are sufficient or identify the entire cause. Future work must address typed legal decision semantics together with source coverage; another retrieval grid alone has weak support.'
 return f
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--findings',type=Path,required=True);p.add_argument('--coverage',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 with a.out.open('x') as stream:json.dump(build(a.findings,a.coverage),stream,indent=2,allow_nan=False);stream.write('\n')
 print(hashlib.sha256(a.out.read_bytes()).hexdigest())
