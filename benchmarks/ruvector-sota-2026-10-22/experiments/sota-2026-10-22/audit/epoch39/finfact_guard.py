"""Frozen input-only surface STOP checks. No labels/models/files/network."""
import re,unicodedata
GUARD_VERSION='finfact-e39-selfclaim-direct-verdict-stop-v1'
VERDICT_PATTERNS=[
 r'\b(?:our (?:ruling|verdict)|(?:fact[- ]check|truth[- ]o[- ]meter) (?:rating|verdict))\b',
 r'\bwe (?:rate|rated|have rated|classify|classified) (?:this|the) (?:claim|statement|assertion)\b',
 r'\b(?:this|the) (?:claim|statement|assertion) (?:(?:is|was|has been) )?(?:rated|labelled|labeled|classified)\b',
 r'\b(?:this|the) (?:claim|statement|assertion) (?:is|was) (?:completely |mostly |partly |entirely )?(?:true|false|neutral|misleading|unproven|a mixture)\b',
 r'\b(?:rating|verdict|ruling)\s*:\s*(?:mostly (?:true|false)|true|false|neutral|mixture|unproven|misleading|pants[- ]on[- ]fire)\b',
 r'\bpants[- ]on[- ]fire\b',
]
INPUT_CAPS={'provided_evidence_units':256,'unit_UTF8_bytes':262144,'case_features_UTF8_bytes':1048576,'claim_UTF8_bytes':65536}
def normalized(text):return ' '.join(unicodedata.normalize('NFKC',text).casefold().split())
def guard_premise(claim,premise):
 if type(claim)is not str or type(premise)is not str:raise ValueError('INPUT_TYPE_STOP')
 c,p=normalized(claim),normalized(premise);flags=[]
 if not c or not p:flags.append('EMPTY_CLAIM_OR_PREMISE')
 if c and p==c:flags.append('SELF_CLAIM_ONLY')
 for i,pattern in enumerate(VERDICT_PATTERNS):
  if re.search(pattern,p):flags.append('DIRECT_VERDICT_PATTERN_'+str(i+1))
 return {'guard_version':GUARD_VERSION,'passed':not flags,'flags':flags,'matching_only_normalization':True,'input_text_changed':False,'scope':'Fixed conservative surface cues only; no guarantee that all semantic leakage can be detected.'}
def guard_features(claim,evidence):
 flags=[]
 if type(claim)is not str or type(evidence)is not list or not evidence or any(type(x)is not str for x in evidence):return {'passed':False,'flags':['INPUT_STRUCTURE_STOP'],'guard_version':GUARD_VERSION}
 if len(evidence)>INPUT_CAPS['provided_evidence_units']:flags.append('PROVIDED_UNIT_CAP_STOP')
 if len(claim.encode())>INPUT_CAPS['claim_UTF8_bytes']:flags.append('CLAIM_BYTE_CAP_STOP')
 if any(len(x.encode())>INPUT_CAPS['unit_UTF8_bytes']for x in evidence):flags.append('UNIT_BYTE_CAP_STOP')
 import json
 if len(json.dumps({'claim':claim,'evidence_sentences':evidence},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())>INPUT_CAPS['case_features_UTF8_bytes']:flags.append('CASE_BYTE_CAP_STOP')
 premise=' '.join(evidence);check=guard_premise(claim,premise);flags+=check['flags']
 nonempty=[normalized(x)for x in evidence if normalized(x)]
 if nonempty and all(x==normalized(claim)for x in nonempty)and'SELF_CLAIM_ONLY'not in flags:flags.append('SELF_CLAIM_ONLY')
 # Check each supplied unit as well as the combined source. No stripping/deletion.
 for text in evidence:
  unit=normalized(text)
  for i,pattern in enumerate(VERDICT_PATTERNS):
   if re.search(pattern,unit)and'DIRECT_VERDICT_PATTERN_'+str(i+1)not in flags:flags.append('DIRECT_VERDICT_PATTERN_'+str(i+1))
 return {'guard_version':GUARD_VERSION,'passed':not flags,'flags':flags,'input_caps':dict(INPUT_CAPS),'input_text_changed':False,'source_or_label_values_used_for_choice':False,'scope':check['scope']}
