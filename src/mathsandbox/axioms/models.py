"""Independent exhaustive finite-model checking, without invoking Z3."""
import itertools
from .parser import variables


def term(value,assignment,model,signature):
    if value.kind=='variable': return assignment[value.symbol]
    symbol=signature[value.symbol]
    if value.kind=='constant': return model['constants'][value.symbol]
    args=[term(arg,assignment,model,signature) for arg in value.args]
    index=0
    for arg in args:index=index*model['size']+arg
    return model['tables'][symbol.id][index]


def formula(value,assignment,model,signature):
    if value.kind in ('eq','ne'):
        a,b=[term(arg,assignment,model,signature) for arg in value.terms]
        return (a==b) if value.kind=='eq' else (a!=b)
    if value.kind=='predicate':
        args=[term(arg,assignment,model,signature) for arg in value.terms];index=0
        for arg in args:index=index*model['size']+arg
        return model['tables'][value.symbol][index]
    values=[formula(arg,assignment,model,signature) for arg in value.operands]
    if value.kind=='and':return all(values)
    if value.kind=='or':return any(values)
    if value.kind=='not':return not values[0]
    if value.kind=='implies':return not values[0] or values[1]
    raise ValueError('Unknown logical formula')


def counterexample(value,model,signature):
    names=sorted(variables(value))
    for values in itertools.product(range(model['size']),repeat=len(names)):
        assignment=dict(zip(names,values))
        if not formula(value,assignment,model,signature):return assignment
    return None


def verify(universe,model):
    if universe.logic!='classical-equality' or universe.branch_policy!='uninterpreted-algebra' or universe.sort!='U':
        raise ValueError('Finite classical model checker is incompatible with this logic/branch policy')
    n=model.get('size')
    if type(n) is not int or not 1<=n<=4:raise ValueError('Finite model size must be 1..4')
    constants=model.get('constants',{});tables=model.get('tables',{})
    for symbol in universe.signature:
        if symbol.kind=='constant':
            value=constants.get(symbol.id)
            if type(value) is not int or not 0<=value<n:raise ValueError('Invalid constant interpretation')
        else:
            table=tables.get(symbol.id)
            if not isinstance(table,list) or len(table)!=n**symbol.arity:raise ValueError('Operation table is not total')
            if symbol.kind=='relation':
                if any(type(value) is not bool for value in table):raise ValueError('Relation table must contain booleans')
            elif any(type(value) is not int or not 0<=value<n for value in table):raise ValueError('Function table escapes the domain')
    signature={symbol.id:symbol for symbol in universe.signature}
    failures=[]
    for axiom in universe.axioms:
        assignment=counterexample(axiom.formula,model,signature)
        if assignment is not None:failures.append({'axiom':axiom.label,'assignment':assignment})
    return {'valid':not failures,'failures':failures,'checked_axioms':len(universe.axioms),
            'method':'Independent exhaustive enumeration over the entire finite structure'}
