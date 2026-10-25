"""E34 inference policy inheritance audit; parses source only, never imports it."""
import ast
from data_common import require,identity,digest
EXACT={'source_context.py':'e847c2d3819a3b469bb6a601a9633f4c8a1279d2b3a2a3e2c2d02cd82eb5c517',
       'model.py':'8bb27dc7d79f2b0a3d27b2d7d82333b1cb442abe3eb3adfeedf4dc37f3a42f52',
       'vector_codec.py':'b2bfbb9fae8aacc3127a2516d387e3a8e99eb0db15d6cdfea0cf137fa19a3906'}
FUNCTIONS={'query.py:query':'22b186c3d3e7683632cf9a5069f10ba6cc3eef0b42da095ea25c637a4a71688d',
 'query.py:hybrid_order':'db70ce13694c5b36a33e3803870601a236d865f091ad88b22cbb8077819318f0',
 'proof.py:decide':'59dca95c29a1e0012e42f94d4ee1fa2467a24e71c8e7aab8a62dcc8f77323f15',
 'evidence.py:span':'f54a214669697c1ea614dca46ac5027092c6e9353bf99f36ed9242838e3b10c8',
 'evidence.py:provenance':'4c49ffdb29ebe2e51c31a62fa44fbf54208772a09f9bdbbe737783177ac09743',
 'evidence.py:lexical_order':'50b2c42abb54c16a518ef4544f0ff4b1b4f61e7f9145656b2c15ca1ddb825cf3'}
class MetadataEpoch(ast.NodeTransformer):
    def visit_Dict(self,node):
        self.generic_visit(node)
        for key,value in zip(node.keys,node.values):
            if isinstance(key,ast.Constant)and key.value=='epoch'and isinstance(value,ast.Constant)and type(value.value)is int and value.value in(34,35):value.value=0
        return node
def audit(root):
    folder=root/'experiments/sota-2026-10-22/candidate/epoch35';checks=[]
    for name,wanted in EXACT.items():
        pin=identity(folder/name);require(pin['sha256']==wanted,'Inference source bytes changed: '+name)
        checks.append({'source':name,'mode':'EXACT_E34_BYTES','sha256':wanted})
    for key,wanted in FUNCTIONS.items():
        name,function=key.split(':');tree=ast.parse((folder/name).read_bytes())
        matches=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name==function]
        require(len(matches)==1,'Missing/duplicate inference function: '+key);node=matches[0]
        metadata_only=key in['query.py:query','proof.py:decide']
        if metadata_only:node=MetadataEpoch().visit(node)
        got=digest(ast.dump(node,include_attributes=False).encode());require(got==wanted,'Inference function changed: '+key)
        checks.append({'source':key,'mode':'AST_EXCEPT_EXACT_EPOCH_RECEIPT_METADATA'if metadata_only else'EXACT_E34_AST','normalized_ast_sha256':got})
    return {'status':'PASS_UNCHANGED_E34_INFERENCE_POLICY','checks':checks,
        'source_pins_origin':'E34 candidate files verified by Git blob SHA1 and size against actual branch4d51073072c428b58685e5498337bfdece6aac9b before deriving these hashes.',
        'candidate_imports_or_execution':0,'scope':'Byte/function-AST inheritance only; orchestration, input identity and phase metadata separately audited. Not proof of complete model training lineage.'}
