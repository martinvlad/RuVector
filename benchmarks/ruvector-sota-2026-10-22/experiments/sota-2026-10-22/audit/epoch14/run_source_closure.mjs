import { sourceClosure } from './source_closure.mjs';
import { testSourceClosure } from './test_source_closure.mjs';

// Replay only declared identities and boundary fixtures; no filesystem or inference.
export function runSourceClosureVerification(fixture) {
  if (!fixture || fixture.source_commit !== 'fbf7334bb0502df285c75674b0a14b3b7a6fa1d2')
    throw Error('Unexpected source snapshot');
  const current = sourceClosure(fixture.plan_pins, fixture.published_files, fixture.external_registry);
  if (current.status !== 'STRUCTURAL_CLOSURE_PASS' || current.checked_pins !== 196 ||
      current.covered_public !== 178 || current.covered_external !== 18 ||
      fixture.external_registry.length !== 37)
    throw Error('Current-source declared closure differs from frozen regression fixture');
  const omitted = new Set(fixture.historical_omitted_paths);
  if (omitted.size !== 13 || omitted.size !== fixture.historical_omitted_paths.length)
    throw Error('Exact historical thirteen-path omission set required');
  const regressed = sourceClosure(fixture.plan_pins,
    fixture.published_files.filter(x => !omitted.has(x.path)), fixture.external_registry);
  if (regressed.status !== 'STRUCTURAL_CLOSURE_FAIL' || regressed.missing_count !== 13 ||
      regressed.issues.length !== 13 || regressed.issues.some(x =>
        x.code !== 'UNDECLARED_FROZEN_SOURCE' || !omitted.has(x.path)) ||
      new Set(regressed.issues.map(x => x.path)).size !== 13)
    throw Error('Historical source-omission regression did not fail closed exactly');
  const pure = testSourceClosure(sourceClosure);
  if (pure.status !== 'PASS' || pure.tests_run !== 24 || pure.failures !== 0)
    throw Error('Pure source-closure fixtures failed');
  return {status:'PASS', scope:'Pure declared-source closure engineering, not file reconstruction, model/native execution or benchmark generalization',
    source_commit:fixture.source_commit, current, historical_omission_regression:regressed,
    pure_fixtures:pure, native_model_session_fit_paid_GPU_calls:0};
}
