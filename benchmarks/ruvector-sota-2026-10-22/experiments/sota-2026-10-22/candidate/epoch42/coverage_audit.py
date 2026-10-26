"""Literal/date span retention diagnostics only; no arithmetic or absence proof."""
import re

NUMBER=re.compile(r'(?<![\w])[-+\u2212]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)(?![\w])')
DATE=re.compile(r'\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{2,4}|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+\d{1,2},?\s+\d{4})\b',re.I)


def audit(spans,selected_ids):
    document=''.join(row['sentence']for row in spans);selected=set(selected_ids)
    ranges=[(row['start'],row['end'])for row in spans if row['unit_id']in selected]
    result={}
    for name,pattern in [('numeric_literal',NUMBER),('date_pattern',DATE)]:
        matches=list(pattern.finditer(document));kept=sum(any(a<=m.start()and m.end()<=b for a,b in ranges)for m in matches)
        result.update({name+'_total':len(matches),name+'_retained':kept,name+'_omitted':len(matches)-kept,
            name+'_coverage':kept/len(matches)if matches else 1.})
    result['scope']='Frozen literal/date regex diagnostics; not exhaustive numeric semantics, evidence sufficiency, or arithmetic correctness.'
    return result
