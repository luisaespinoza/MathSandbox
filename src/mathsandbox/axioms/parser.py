"""Restricted universal equational/Horn language. No eval or SMT-LIB parsing."""
import ast
import re
from .records import Term, Formula, Axiom
from ..core.ir import identity


def variables(value):
    if isinstance(value,Term):
        result={value.symbol} if value.kind=='variable' else set()
        for arg in value.args: result.update(variables(arg))
        return result
    result=set()
    for term in value.terms: result.update(variables(term))
    for formula in value.operands: result.update(variables(formula))
    return result


class Parser:
    def __init__(self, signature):
        self.signature={symbol.name:symbol for symbol in signature}
        if len(self.signature)!=len(signature): raise ValueError('Duplicate signature names')
        self.by_id={symbol.id:symbol for symbol in signature}

    def term(self,node,depth=0):
        if depth>12: raise ValueError('Term depth exceeds 12')
        recurse=lambda item:self.term(item,depth+1)
        if isinstance(node,ast.Constant) and type(node.value) is int and node.value in (0,1):
            name='zero' if node.value==0 else 'one'
            if name not in self.signature or self.signature[name].kind!='constant': raise ValueError('Signature lacks the requested constant')
            return Term('constant',self.signature[name].id)
        if isinstance(node,ast.Name):
            if node.id in self.signature:
                symbol=self.signature[node.id]
                if symbol.kind!='constant': raise ValueError('Functions/relations need explicit arguments')
                return Term('constant',symbol.id)
            if not re.fullmatch(r'[a-z][a-z0-9_]{0,15}',node.id): raise ValueError('Variable names must be short lowercase identifiers')
            return Term('variable',node.id)
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and not node.keywords:
            symbol=self.signature.get(node.func.id)
            if symbol is None or symbol.kind!='function' or len(node.args)!=symbol.arity:
                raise ValueError('Unknown function or arity mismatch')
            return Term('application',symbol.id,tuple(recurse(arg) for arg in node.args))
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.USub):
            return self.application('neg',(recurse(node.operand),))
        if isinstance(node,ast.BinOp):
            a,b=recurse(node.left),recurse(node.right)
            if isinstance(node.op,ast.Sub): return self.application('add',(a,self.application('neg',(b,))))
            name={ast.Add:'add',ast.Mult:'mul'}.get(type(node.op))
            if name: return self.application(name,(a,b))
        raise ValueError('Unsupported term syntax; use declared operations, 0, 1, and variables')

    def application(self,name,args):
        symbol=self.signature.get(name)
        if symbol is None or symbol.kind!='function' or symbol.arity!=len(args):
            raise ValueError('Required operation is missing from the signature')
        return Term('application',symbol.id,args)

    def formula(self,text):
        if not isinstance(text,str) or not 0<len(text)<=1500: raise ValueError('Formula length must be 1..1500 characters')
        implication=re.split(r'=>|->',text)
        if len(implication)>2: raise ValueError('Use at most one implication per formula')
        if len(implication)==2:
            result=Formula('implies',operands=tuple(self.formula(part.strip()) for part in implication))
        else:
            normalized=re.sub(r'(?<![<>=!])=(?!=)','==',text)
            try: result=self.boolean(ast.parse(normalized.strip(),mode='eval').body)
            except (SyntaxError, RecursionError) as error: raise ValueError('Malformed formula syntax') from error
        if len(variables(result))>4: raise ValueError('The current backend supports at most four universally closed variables per formula')
        return result

    def boolean(self,node):
        if isinstance(node,ast.Compare) and len(node.ops)==1 and type(node.ops[0]) in (ast.Eq,ast.NotEq):
            return Formula('eq' if isinstance(node.ops[0],ast.Eq) else 'ne',(self.term(node.left),self.term(node.comparators[0])))
        if isinstance(node,ast.BoolOp):
            return Formula('and' if isinstance(node.op,ast.And) else 'or',operands=tuple(self.boolean(value) for value in node.values))
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.Not):
            return Formula('not',operands=(self.boolean(node.operand),))
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and not node.keywords:
            symbol=self.signature.get(node.func.id)
            if symbol is not None and symbol.kind=='relation' and len(node.args)==symbol.arity:
                return Formula('predicate',tuple(self.term(value) for value in node.args),symbol=symbol.id)
        raise ValueError('Use equality, inequality, and/or/not, implication, or declared relations')


def parse_axioms(signature,text,old=()):
    if not isinstance(text,str) or len(text)>30000: raise ValueError('Axiom editor text exceeds its budget')
    parser=Parser(signature);previous={axiom.label:axiom for axiom in old};result=[]
    for line in text.splitlines():
        line=line.strip()
        if not line or line.startswith('#'):continue
        if ':' not in line:raise ValueError('Use label: formula for every axiom')
        label,body=[part.strip() for part in line.split(':',1)]
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,39}',label) or any(a.label==label for a in result):
            raise ValueError('Duplicate or malformed axiom label')
        formula=parser.formula(body);prior=previous.get(label)
        result.append(Axiom(prior.id if prior else 'axiom:'+identity(),label,body,formula,
                            prior.revision+(prior.text!=body or prior.formula!=formula) if prior else 1))
    if len(result)>40:raise ValueError('At most 40 axioms are supported')
    return tuple(result)
