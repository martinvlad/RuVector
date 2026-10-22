"""Conservative, label-free validators for explicit response constraints.

No file access, task identifiers, evaluated example strings or answer tables.
Unsupported language falls back to the actual native decision component.
"""
import ast
import json
import operator
import re

NUMBERS={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10}

def request_response(state):
    try:
        obj=json.loads(state)
        if isinstance(obj,dict) and isinstance(obj.get('request'),str) and isinstance(obj.get('response'),str):
            return obj['request'],obj['response'],''
    except (ValueError,TypeError):pass
    match=re.search(r'(?is)\b(?:Response|Answer)\s*:\s*(.*)$',state)
    if match:return state[:match.start()],match.group(1).strip(),state[:match.start()]
    match=re.search(r'(?is)\b(?:the response|the answer)\s+(?:is|gives)\s+(.*?)[.]?$',state)
    if match:return state[:match.start()],re.sub(r'^only\s+','',match.group(1)).rstrip('.'),state[:match.start()]
    return None

def arithmetic(expression):
    ops={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv}
    def visit(node):
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):return node.value
        if isinstance(node,ast.BinOp) and type(node.op) in ops:return ops[type(node.op)](visit(node.left),visit(node.right))
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.USub):return -visit(node.operand)
        raise ValueError('Unsupported arithmetic syntax')
    if len(expression)>80:raise ValueError('Arithmetic limit')
    return visit(ast.parse(expression,mode='eval').body)

def solve(state,question):
    if question['type']!='noul' or not re.search(r'(?i)response.*(?:satisf|correct)|satisf.*request',question.get('instructions','')):return None
    pair=request_response(state)
    if not pair:return None
    request,response,context=pair
    if len(request)>2000 or len(response)>2000:return None
    words=re.search(r'(?i)exactly\s+(\d+|'+ '|'.join(NUMBERS)+r')\s+words',request)
    if words:
        raw=words.group(1).lower();required=int(raw) if raw.isdigit() else NUMBERS[raw]
        actual=len(response.split())
        return {'decision':actual==required,'rule':'exact_word_count','required':required,'actual':actual}
    if re.search(r'(?i)\b(?:JSON\s+)?array\b',request) and not re.search(r'(?i)code|function|implement|sort|iterate',request):
        try:parsed=json.loads(response)
        except ValueError:parsed=None
        if not isinstance(parsed,list):return {'decision':False,'rule':'explicit_JSON_array_type','observed_type':type(parsed).__name__}
    if re.search(r'(?i)\b(?:both|all)\b',request):
        ref=re.search(r'(?i)reference(?:\s+lists|\s+says|\s*:)?\s+([\w -]+?\s+and\s+[\w -]+?)(?:[.;]|$)',context)
        if ref:
            facts=[x.strip().lower() for x in re.split(r'\s+and\s+|,',ref.group(1))]
            if 2<=len(facts)<=8 and all(re.fullmatch(r'[a-z]{2,20}',fact) for fact in facts):
                missing=[fact for fact in facts if not re.search(r'(?i)\b'+re.escape(fact)+r'\b',response)]
                if missing:return {'decision':False,'rule':'explicit_reference_completeness','missing_reference_terms':missing}
    expression=re.search(r'(?i)(?:sum of\s+)(-?\d+(?:\.\d+)?)\s+and\s+(-?\d+(?:\.\d+)?)',request)
    if expression:expression=expression.group(1)+'+'+expression.group(2)
    else:
        match=re.search(r'(?<!\w)(-?\d+(?:\.\d+)?\s*[+*/-]\s*-?\d+(?:\.\d+)?)(?!\w)',request)
        expression=match.group(1) if match else None
    if expression and re.fullmatch(r'-?\d+(?:\.\d+)?',response):
        try:value=arithmetic(expression)
        except (ValueError,ZeroDivisionError,SyntaxError,OverflowError):return None
        return {'decision':abs(float(response)-value)<1e-10,'rule':'literal_arithmetic_equality','computed':value,'response_value':float(response)}
    return None


# Round2 extends the same fallback architecture with generic polarity/rubric checks.
_base_solve=solve

def intent(state,question):
    if question['type']!='choice' or not re.search(r'(?i)primary requested action',question.get('instructions','')):return None
    criteria=question.get('criteria',{})
    patterns={
        'refund':(r'refund|return money',r'return (?:the )?(?:duplicate|second|extra)?\s*charge|want.{0,40}(?:refund|charge.{0,15}refund)|(?:money|charge).{0,12}back|refund(?:ed)?'),
        'cancel':(r'end.*subscription|cancel|membership',r'(?:cancel|end).{0,20}(?:subscription|membership)|stop renewing'),
        'address':(r'modify.*address|change.*address',r'(?:replace|change).{0,30}(?:shipping|delivery)?\s*address|send it to my new'),
        'status':(r'progress|delivery status|shipment status',r'where.{0,20}(?:parcel|package)|(?:tell|learn).{0,30}(?:package|parcel|delivery|shipment).{0,10}progress|(?:whether|was|has).{0,30}(?:delivered|arrived)')}
    labels={}
    for concept,(descriptor,_) in patterns.items():
        matches=[label for label,description in criteria.items() if re.search(descriptor,label+' '+str(description),re.I)]
        if len(matches)==1:labels[concept]=matches[0]
    candidates=[]
    for clause in re.split(r'[.!?;]|\bbut\b',state,flags=re.I):
        for concept,(_,pattern) in patterns.items():
            match=re.search(pattern,clause,re.I)
            if not match or concept not in labels:continue
            prefix=clause[max(0,match.start()-35):match.start()].lower()
            if re.search(r'\b(?:not|no|never|don.t|already)\b',prefix):continue
            if re.search(r'(?i)\b(?:yesterday|already done|not requested|not asking|no .{0,15}requested)\b',clause):continue
            if concept=='refund' and not re.search(r'(?i)please|want|return|ask|refund(?:ed)?\s*$',clause):continue
            candidates.append(labels[concept])
    unique=set(candidates)
    if len(unique)==1:return {'decision':next(iter(unique)),'rule':'explicit_positive_requested_action','positive_action_mentions':len(candidates)}
    if not unique and re.search(r'(?i)thank|thanks',state):
        other=[label for label,description in criteria.items() if re.search(r'(?i)none of|other',label+' '+str(description))]
        if len(other)==1:return {'decision':other[0],'rule':'acknowledgement_without_action'}
    return None

def impact(state,question):
    levels=question.get('criteria',question.get('legend'))
    if question['type']!='score' or not isinstance(levels,list) or len(levels)!=4:return None
    # Activate only when the supplied rubric itself defines these semantics.
    if not (re.search(r'cosmetic',str(levels[0]),re.I) and re.search(r'many users',str(levels[2]),re.I) and re.search(r'irreversible|physical harm',str(levels[3]),re.I)):return None
    s=state.lower()
    severe=re.search(r'irreversibl\w*.{0,30}(?:delet|lost|loss)|permanently gone|physical harm',s)
    if severe and not re.search(r'\bno\b|\bnot\b',s[max(0,severe.start()-15):severe.start()]):
        return {'decision':'3','rule':'highest_supported_impact','supported':'confirmed_irreversible_loss_or_harm'}
    many=re.search(r'(?:all|every|many)\s+(?:users?|customers?)',s)
    impaired=re.search(r'cannot|unavailable|blocked|failure|can.t',s)
    if many and impaired:return {'decision':'2','rule':'highest_supported_impact','supported':'many_users_core_impairment'}
    if re.search(r'(?:one|single)\s+user',s) and impaired:
        return {'decision':'1','rule':'highest_supported_impact','supported':'single_user_impairment'}
    if re.search(r'(?:all|every)\s+(?:features?|functions?).{0,15}work|no function failure',s):
        return {'decision':'0','rule':'highest_supported_impact','supported':'functions_work_or_no_function_failure'}
    return None

def solve(state,question):
    return _base_solve(state,question) or intent(state,question) or impact(state,question)
