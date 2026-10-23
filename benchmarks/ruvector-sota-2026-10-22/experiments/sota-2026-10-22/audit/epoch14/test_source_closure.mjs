// Pure engineering fixtures; no benchmark generalization or file hashing.
export function testSourceClosure(sourceClosure) {
  const h = "a".repeat(64), h2 = "b".repeat(64);
  const p = (path,sha256=h,bytes=1) => ({path,sha256,bytes});
  const pub = [p("source/main.py"), p("assets.lock.json"), p("acquire.py")];
  const ext = [{...p("models/reader/model.onnx"),kind:"model_asset",
    provenance_manifest:{path:"assets.lock.json",sha256:h},
    acquisition_helper:{path:"acquire.py",sha256:h}}];
  const pins = [{path:"source/main.py",sha256:h},{path:"models/reader/model.onnx",sha256:h}];
  const clone = x => JSON.parse(JSON.stringify(x));
  const tests = [];
  const check = (name,fn) => {if (!fn()) throw Error("Fixture failed: "+name); tests.push({name,status:"PASS"});};
  const pass = r => r.status === "STRUCTURAL_CLOSURE_PASS";
  const code = (r,c) => r.issues.some(x=>x.code===c);
  check("explicit_source_and_model_registry_pass",()=>pass(sourceClosure(pins,pub,ext)));
  check("absent_source_rejected",()=>code(sourceClosure(pins,pub.slice(1),ext),"UNDECLARED_FROZEN_SOURCE"));
  check("onnx_extension_does_not_implicitly_defer",()=>code(sourceClosure(pins,pub,[]),"UNDECLARED_FROZEN_SOURCE"));
  check("external_wrong_digest_rejected",()=>{const e=clone(ext);e[0].sha256=h2;return code(sourceClosure(pins,pub,e),"EXTERNAL_PIN_HASH_MISMATCH");});
  check("public_wrong_digest_rejected",()=>{const q=clone(pub);q[0].sha256=h2;return code(sourceClosure(pins,q,ext),"PUBLIC_PIN_HASH_MISMATCH");});
  check("source_cannot_masquerade_as_model_asset",()=>{const e=clone(ext);e[0].path="source/omitted.py";return code(sourceClosure(pins,pub,e),"UNSUPPORTED_EXTERNAL_KIND_OR_NAMESPACE");});
  check("unknown_external_kind_rejected",()=>{const e=clone(ext);e[0].kind="source_diagnostic";return code(sourceClosure(pins,pub,e),"UNSUPPORTED_EXTERNAL_KIND_OR_NAMESPACE");});
  check("provenance_manifest_must_be_published",()=>{const e=clone(ext);e[0].provenance_manifest.path="absent.lock.json";return code(sourceClosure(pins,pub,e),"UNPUBLISHED_OR_CHANGED_EXTERNAL_PROVENANCE");});
  check("acquisition_helper_must_be_published",()=>{const e=clone(ext);e[0].acquisition_helper.path="absent.py";return code(sourceClosure(pins,pub,e),"UNPUBLISHED_OR_CHANGED_EXTERNAL_PROVENANCE");});
  check("provenance_digest_must_match",()=>{const e=clone(ext);e[0].provenance_manifest.sha256=h2;return code(sourceClosure(pins,pub,e),"UNPUBLISHED_OR_CHANGED_EXTERNAL_PROVENANCE");});
  check("duplicate_plan_pin_rejected",()=>code(sourceClosure([...pins,pins[0]],pub,ext),"DUPLICATE_PLAN_PIN"));
  check("conflicting_public_digest_rejected",()=>code(sourceClosure(pins,[...pub,p("source/main.py",h2)],ext),"CONFLICTING_PUBLIC_IDENTITY"));
  check("conflicting_public_byte_length_rejected",()=>code(sourceClosure(pins,[...pub,p("source/main.py",h,2)],ext),"CONFLICTING_PUBLIC_IDENTITY"));
  check("identical_public_overlap_is_allowed",()=>pass(sourceClosure(pins,[...pub,pub[0]],ext)));
  check("conflicting_external_identity_rejected",()=>code(sourceClosure(pins,pub,[...ext,{...ext[0],bytes:2}]),"CONFLICTING_EXTERNAL_IDENTITY"));
  check("public_external_collision_rejected",()=>code(sourceClosure(pins,[...pub,p("models/reader/model.onnx",h2)],ext),"PUBLIC_EXTERNAL_IDENTITY_MISMATCH"));
  check("parent_path_rejected",()=>code(sourceClosure([{path:"../source.py",sha256:h}],pub,ext),"INVALID_RECORD"));
  check("absolute_path_rejected",()=>code(sourceClosure([{path:"/source.py",sha256:h}],pub,ext),"INVALID_RECORD"));
  check("windows_separator_rejected",()=>code(sourceClosure([{path:"source"+String.fromCharCode(92)+"main.py",sha256:h}],pub,ext),"INVALID_RECORD"));
  check("null_path_rejected",()=>code(sourceClosure([{path:"source"+String.fromCharCode(0)+".py",sha256:h}],pub,ext),"INVALID_RECORD"));
  check("invalid_digest_rejected",()=>code(sourceClosure([{path:"source/main.py",sha256:"A".repeat(64)}],pub,ext),"INVALID_RECORD"));
  check("unsafe_byte_length_rejected",()=>code(sourceClosure(pins,[...pub,p("extra.py",h,Number.MAX_SAFE_INTEGER+1)],ext),"INVALID_RECORD"));
  check("invalid_input_type_rejected",()=>code(sourceClosure(null,pub,ext),"INVALID_INPUT"));
  check("inputs_remain_immutable",()=>{const before=JSON.stringify({pins,pub,ext});sourceClosure(pins,pub,ext);return before===JSON.stringify({pins,pub,ext});});
  return {status:"PASS",tests_run:tests.length,failures:0,tests,
    scope:"Pure V8 structural engineering fixtures, not native/model execution or benchmark generalization"};
}
