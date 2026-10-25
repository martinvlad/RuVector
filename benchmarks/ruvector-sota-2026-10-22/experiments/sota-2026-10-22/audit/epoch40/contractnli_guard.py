"""Prospective structural/input caps, complete source coverage and self-claim guard."""
import hashlib,json,unicodedata
MAX_UNITS=1024
MAX_DOCUMENT_BYTES=1048576
MAX_UNIT_BYTES=262144
MAX_CLAIM_BYTES=65536
MAX_CASE_FEATURE_BYTES=2097152

def normalized(value):return ' '.join(value.casefold().split())
def matching(value):return ' '.join(unicodedata.normalize('NFKC',value).casefold().split())
def digest(value):return hashlib.sha256(value.encode()).hexdigest()
def guard_features(claim,evidence,document=None):
 flags=[]
 if type(claim)is not str or not claim.strip():flags.append('NONEMPTY_ORIGINAL_HYPOTHESIS_REQUIRED')
 if type(evidence)is not list or not evidence or len(evidence)>MAX_UNITS:flags.append('SOURCE_UNIT_COUNT_CAP')
 if flags:return {'passed':False,'flags':flags}
 if len(claim.encode())>MAX_CLAIM_BYTES:flags.append('HYPOTHESIS_UTF8_CAP')
 if any(type(s)is not str or len(s.encode())>MAX_UNIT_BYTES for s in evidence):flags.append('SOURCE_UNIT_UTF8_CAP')
 if flags:return {'passed':False,'flags':flags}
 full=''.join(evidence)
 if document is not None and full!=document:flags.append('SOURCE_PARTITION_NOT_COMPLETE')
 if not full.strip():flags.append('EMPTY_SOURCE_DOCUMENT')
 if len(full.encode())>MAX_DOCUMENT_BYTES:flags.append('SOURCE_DOCUMENT_UTF8_CAP')
 if matching(full)==matching(claim):flags.append('SOURCE_EQUALS_HYPOTHESIS')
 return {'passed':not flags,'flags':flags,'units':len(evidence),'source_UTF8_bytes':len(full.encode()),'hypothesis_UTF8_bytes':len(claim.encode()),'all_source_characters_preserved':True}
def guard_premise(claim,premise):
 flags=[]
 if type(claim)is not str or type(premise)is not str or not claim.strip()or not premise.strip():flags.append('NONEMPTY_HYPOTHESIS_PREMISE_REQUIRED')
 elif matching(claim)==matching(premise):flags.append('PACKED_SOURCE_EQUALS_HYPOTHESIS')
 return {'passed':not flags,'flags':flags,'normalization_for_guard_only':True}
def partition(document,spans):
 if type(document)is not str or type(spans)is not list:raise ValueError('SOURCE_DOCUMENT_SPAN_SCHEMA')
 ends=set()
 for span in spans:
  if type(span)is not list or len(span)!=2 or any(type(x)is not int for x in span)or not 0<=span[0]<=span[1]<=len(document):raise ValueError('SOURCE_SPAN_OFFSET_SCHEMA')
  if span[1]>0:ends.add(span[1])
 ends.add(len(document));start=0;units=[]
 for end in sorted(ends):
  if end>start:units.append({'unit_id':len(units),'sentence':document[start:end],'start':start,'end':end});start=end
 if ''.join(u['sentence']for u in units)!=document:raise ValueError('SOURCE_PARTITION_COVERAGE')
 return units
