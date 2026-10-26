"""Invented public metadata only. No current stage/owner/Git/scientific calls."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import argparse, base64, copy, json, tempfile, unittest
import guard as g
import stagebuilder as s

class TransportMetadata(unittest.TestCase):
    def rejects(self, f, *a):
        with self.assertRaises((ValueError, KeyError, TypeError)): f(*a)
    def cas(self):
        return dict(repository_full_name=g.REPO,branch_name=g.BRANCH,sha='1'*40,expected_sha='2'*40,force=False)
    def test_exact_cas_and_parent(self):
        a=self.cas(); g.validate_request(g.TOOLS['ref'],a)
        for k,v in [('force',True),('force',0),('branch_name','main'),('expected_sha',None),('sha',next(iter(g.DENY)))]:
            b=dict(a);b[k]=v;self.rejects(g.validate_request,g.TOOLS['ref'],b)
        b=dict(a);b['unexpected']=True;self.rejects(g.validate_request,g.TOOLS['ref'],b)
        c=dict(repository_full_name=g.REPO,tree_sha='3'*40,parent_sha='2'*40,message='invented')
        g.validate_request(g.TOOLS['commit'],c)
        for key,value in [('parents',['2'*40]),('parent_sha',next(iter(g.DENY))),('tree_sha','invalid')]:
            d=dict(c);d[key]=value;self.rejects(g.validate_request,g.TOOLS['commit'],d)
    def test_scope_and_denied_objects(self):
        a=dict(repository_full_name=g.REPO,base_tree_sha='1'*40,tree_elements=[dict(path=g.SCOPE+g.ROOTS[0]+'invented.json',mode='100644',type='blob',sha='2'*40)])
        g.validate_request(g.TOOLS['tree'],a)
        for path in ['main.json',g.SCOPE+'../escape.json',g.SCOPE+'unrelated.json',g.SCOPE+g.ROOTS[0]+'../escape.json']:
            b=copy.deepcopy(a);b['tree_elements'][0]['path']=path;self.rejects(g.validate_request,g.TOOLS['tree'],b)
        for denied in g.DENY:
            b=copy.deepcopy(a);b['tree_elements'][0]['sha']=denied;self.rejects(g.validate_request,g.TOOLS['tree'],b)
        b=copy.deepcopy(a);b['tree_elements']*=33;self.rejects(g.validate_request,g.TOOLS['tree'],b)
    def test_identifying_and_bare_ack(self):
        req=self.cas();fresh=dict(ref='refs/heads/'+g.BRANCH,object={'sha':req['sha']})
        self.assertIsNone(g.acknowledge(g.TOOLS['ref'],req,{'success':True},fresh_ref=fresh))
        self.assertEqual(g.acknowledge(g.TOOLS['ref'],req,fresh,fresh_ref=fresh),req['sha'])
        for result,proof in [({'success':True},None),({'success':1},fresh),({'success':False},fresh),({'success':True,'ref':'wrong'},fresh),(fresh,{'ref':'wrong','object':{'sha':req['sha']}})]:
            self.rejects(g.acknowledge,g.TOOLS['ref'],req,result,None,proof)
        self.assertEqual(g.acknowledge(g.TOOLS['tree'],{}, {'sha':'3'*40},'3'*40),'3'*40)
        self.rejects(g.acknowledge,g.TOOLS['tree'],{}, {'success':True},'3'*40)
        self.rejects(g.acknowledge,g.TOOLS['tree'],{}, {'sha':'4'*40},'3'*40)
    def test_durable_raw_before_owner_or_decode(self):
        oldW,oldOwner=g.W,g.owner_fence
        try:
            with tempfile.TemporaryDirectory(prefix='invented-',dir=Path(__file__).parent) as td:
                g.W=Path(td);g.owner_fence=lambda:(_ for _ in ()).throw(AssertionError('owner must not run'))
                raw=b'{"isError":true,"structuredContent":{"private_fixture":false}}'
                a=argparse.Namespace(mode='capture-raw',phase='source',id='e48-source-g13-blob-0',payload=base64.b64encode(raw).decode())
                self.assertTrue(g.main(a)['raw_durable']);self.assertEqual(g.body(g.W/'publication/requests'/ (a.id+'.raw-tool-return.json')),raw)
                with self.assertRaises(FileExistsError):g.main(a)
                g.main(argparse.Namespace(mode='capture-proof',phase='source',proof='ref',payload=base64.b64encode(raw).decode()))
        finally:g.W,g.owner_fence=oldW,oldOwner
    def test_uncertain_journal_stops(self):
        intent=dict(phase='intent',id='invented',kind='tree');response=dict(phase='response',id='invented',kind='tree',ok=True)
        g.clean([intent,response])
        for rows in [[intent],[intent,dict(response,ok=False)],[intent,dict(response,id='wrong')],[intent,dict(response,ok=1)]]:self.rejects(g.clean,rows)
    def test_merkle_and_scoped_siblings(self):
        leaves=[dict(path='sha/file.txt',mode='100644',type='blob',sha=g.git(b'a'),size=1),dict(path='z.txt',mode='100644',type='blob',sha=g.git(b'z'),size=1)]
        scope=g.scope_sha(leaves)
        bench={'tree':[dict(path='other',mode='040000',type='tree',sha='4'*40),dict(path='ruvector-sota-2026-10-22',mode='040000',type='tree',sha=scope)]}
        bench['sha']=g.tree_sha(bench['tree']);root={'tree':[dict(path='benchmarks',mode='040000',type='tree',sha=bench['sha']),dict(path='other.txt',mode='100644',type='blob',sha='5'*40)]}
        root['sha']=g.tree_sha(root['tree']);before=copy.deepcopy((root,bench))
        self.assertEqual(s.layout(leaves,root,bench),(root['sha'],bench['sha'],scope))
        changed=copy.deepcopy(leaves);changed[0]['sha']=g.git(b'b');self.assertNotEqual(s.layout(changed,root,bench)[0],root['sha'])
        self.assertEqual((root,bench),before)
        self.rejects(g.scope_sha,[*leaves,leaves[0]])
    def test_typed_historical_controls(self):
        cont=dict(goal_met=False,official_rank=None,champion={'id':'native104'},unused_confirmation_sets=[],active_run={'epoch':47},checkpoint_manifest_sha256='old',history={'docs':[357,227,46,212],'no_rewrite':True})
        cp=dict(schema_version=1,project_files=[dict(path='old.json',bytes=1,sha256='a'*64)],epoch47_final={'score':4})
        x=dict(phase='source',CONT_patch={'epoch48_source':{'source':True}},CP_phase_record={'source':True},ACTIVE=dict(epoch=48,phase='source',source_checkpoint=g.BASE,owner_sha256=g.OWNER['sha256'],kind=g.KIND,work_active=True,experiments_active=False,OS_lock_observation_scope='PREPUBLICATION_SNAPSHOT_NOT_CURRENT_REMOTE_LEASE',publication_is_not_scientific_authorization=True))
        before=copy.deepcopy((cont,cp));newcont,newcp,_=s.preserve_controls(cont,cp,x,[dict(path=g.ROOTS[0]+'new.json',bytes=2,sha256='b'*64)])
        self.assertEqual(newcont['history']['docs'],[357,227,46,212]);self.assertTrue(g.same(newcp['epoch47_final'],cp['epoch47_final']))
        self.assertEqual(newcont['checkpoint_manifest_sha256'],g.sha(g.encoded(newcp)));self.assertEqual((cont,cp),before)
        bad=copy.deepcopy(x);bad['CONT_patch']['champion']={'id':'fake'};self.rejects(s.preserve_controls,cont,cp,bad,[])
    def test_type_exact_refs_and_json(self):
        self.assertFalse(g.same(True,1));self.rejects(g.parse,'{"x":1,"x":2}');self.rejects(g.parse,'{"x":NaN}')
        self.rejects(g.relative,'x/../y');self.rejects(g.relative,'/absolute')
    def test_controller_raw_order_and_definitions_only(self):
        js=(Path(__file__).parent/'controller.js').read_text()
        mutation=js[js.index('const mutate48='):js.index('const siblings48=')]
        self.assertLess(mutation.index("await guard48('intent'"),mutation.index('raw=await tools[slot.kind](args)'))
        self.assertLess(mutation.index('await capture48(slot.id,raw)'),mutation.index("await guard48('owner');",mutation.index('await capture48(slot.id,raw)')))
        self.assertLess(mutation.index('await capture48(slot.id,raw)'),mutation.index("guard48('response'"))
        self.assertEqual(js.count('const publishE48Phase=async'),1);self.assertNotIn('await publishE48Phase(',js)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TransportMetadata))
    print(json.dumps({'fixture_kind':'INVENTED_PUBLICATION_METADATA_ONLY','tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'actual_Git_mutations':0,'native_model_or_corpus_runs':0,'checks_passed':result.wasSuccessful()},sort_keys=True))
    raise SystemExit(not result.wasSuccessful())
