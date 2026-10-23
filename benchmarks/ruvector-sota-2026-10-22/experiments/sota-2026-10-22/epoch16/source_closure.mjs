// One exact licensed public dataset dependency, then unchanged epoch14 guard.
// Structural metadata only; actual file-byte verification belongs to the CLI.
import { sourceClosure } from '../audit/epoch14/source_closure.mjs';

export const LICENSED_DATA = Object.freeze({
  path:'experiments/sota-2026-10-22/legal-transfer/epoch3/sources/original-train.json',
  sha256:'dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5',
  bytes:7608211, kind:'licensed_dataset_asset', license:'CC-BY-4.0',
  source_commit:'eced6528dd3c1d14d73f9a87df8f7bdbc03126f9',
  source_url:'https://raw.githubusercontent.com/stanfordnlp/contract-nli/eced6528dd3c1d14d73f9a87df8f7bdbc03126f9/resources/contract-nli.zip',
  archive_sha256:'e03fc77bbf8b53e2976a250e81d8a294bc3d5e5fb014521e477dee9340d6287b',
  archive_member:'contract-nli/train.json',
  provenance_manifest:{path:'experiments/sota-2026-10-22/candidate/epoch3/publication/RESTORE_EPOCH3_DATA.json',sha256:'c3073e56747e89eadf3ab7ce4cc6c68838b561df82cdb9d023ba1206437606be'},
  acquisition_helper:{path:'experiments/sota-2026-10-22/candidate/epoch3/publication/restore_original_data.py',sha256:'03b716e9a225c5efa60e4aeab16df3c6d53906bd1d36edcc12f9514e34d68c5a'},
  license_file:{path:'experiments/sota-2026-10-22/epoch16/source-data-LICENSE.txt',sha256:'9e5f1b3c610b9c2da5c313bf81d577a7d1acec686bdb0384edefa6df0f90cd94'}
});

export function sourceClosure16(planPins, publishedFiles, registry) {
  if (![planPins,publishedFiles,registry].every(Array.isArray))
    return sourceClosure(planPins,publishedFiles,registry);
  const issues=[];
  const issue=(code,detail)=>issues.push({code,path:LICENSED_DATA.path,detail});
  const rows=registry.filter(r=>r?.path===LICENSED_DATA.path || r?.kind==='licensed_dataset_asset');
  const pins=planPins.filter(r=>r?.path===LICENSED_DATA.path);
  if(rows.length!==1)issue('EXACTLY_ONE_LICENSED_DATA_RESTORE_REQUIRED','No duplicate or arbitrary data exception');
  if(pins.length!==1 || pins[0]?.sha256!==LICENSED_DATA.sha256)
    issue('LICENSED_DATA_PIN_REQUIRED','Exact dataset bytes must be a unique frozen plan pin');
  if(publishedFiles.some(r=>r?.path===LICENSED_DATA.path))
    issue('LICENSED_DATA_IS_EXTERNAL','No implicit public-source alias for this dataset');
  for(const row of rows) {
    for(const key of ['path','sha256','bytes','kind','license','source_commit','source_url','archive_sha256','archive_member'])
      if(row[key]!==LICENSED_DATA[key])issue('LICENSED_DATA_IDENTITY_OR_LICENSE_CHANGED',key);
    for(const key of ['provenance_manifest','acquisition_helper','license_file']) {
      const expected=LICENSED_DATA[key],ref=row[key];
      if(ref?.path!==expected.path || ref?.sha256!==expected.sha256)
        issue('LICENSED_DATA_RESTORE_PROVENANCE_CHANGED',key);
      const matches=publishedFiles.filter(x=>x?.path===expected.path);
      if(matches.length!==1 || matches[0]?.sha256!==expected.sha256)
        issue('LICENSED_DATA_PROVENANCE_NOT_PUBLIC',key);
      if(!planPins.some(x=>x?.path===expected.path && x.sha256===expected.sha256))
        issue('LICENSED_DATA_PROVENANCE_NOT_PINNED',key);
    }
  }
  const base=sourceClosure(planPins.filter(x=>x?.path!==LICENSED_DATA.path),publishedFiles,
    registry.filter(x=>x?.path!==LICENSED_DATA.path && x?.kind!=='licensed_dataset_asset'));
  const all=[...base.issues,...issues];
  return {...base,status:all.length?'STRUCTURAL_CLOSURE_FAIL':'STRUCTURAL_CLOSURE_PASS',
    checked_pins:base.checked_pins+pins.length,
    covered_external:base.covered_external+(issues.length?0:1),
    licensed_dataset_assets_covered:issues.length?0:1,
    issues:all,scope:'Declared identities only. Exactly one originalContractNLI source asset requires frozen bytes, immutable source/archive, public pinned CC-BY license/spec/restorer. Other model/native/public rules are unchanged. No label selection, acquisition, model execution or benchmark result.'};
}
