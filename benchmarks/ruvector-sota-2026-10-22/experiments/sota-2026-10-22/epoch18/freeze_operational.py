"""Freeze only source/operational metadata; full real validator is a separate gate."""
from study_metadata import *
def main():
    plan=operational_plan()
    write(E/'operational-plan.json',plan)
    print(__import__('json').dumps({'operational_plan':ident(E/'operational-plan.json'),'pins':len(plan['pins']),
        'new_case_inputs_or_annotation_choices_read':0,'model_native_fit_paid_GPU_calls':0,
        'operational_prelabel_only':True,'native_execution_admitted':False}))
if __name__=='__main__':main()
