from uuid import UUID
from .records import Symbol,Term,Formula,Axiom,Universe,LogicRecord
from .parser import Parser,parse_axioms
from .universes import parse_signature,signature_text


def scoped_id(value,prefix):
    if not isinstance(value,str) or not value.startswith(prefix):raise ValueError('Malformed scoped logical identity')
    try:UUID(value[len(prefix):])
    except ValueError:raise ValueError('Logical identities cannot alias standard math universes') from None
    return value


def term(data):
    return Term(data['kind'],data['symbol'],tuple(term(value) for value in data['args']))


def formula(data):
    return Formula(data['kind'],tuple(term(value) for value in data['terms']),tuple(formula(value) for value in data['operands']),data['symbol'])


def universe(data):
    scoped_id(data['id'],'universe:')
    if type(data['revision']) is not int or data['revision']<1:raise ValueError('Invalid universe revision')
    signature=tuple(Symbol(**value) for value in data['signature'])
    for symbol in signature:scoped_id(symbol.id,'symbol:')
    if len({symbol.id for symbol in signature})!=len(signature):raise ValueError('Duplicate symbol identity')
    axioms=tuple(Axiom(**{**value,'formula':formula(value['formula'])}) for value in data['axioms'])
    result=Universe(**{**data,'signature':signature,'axioms':axioms})
    if parse_signature(signature_text(result),signature)!=signature:raise ValueError('Malformed signature')
    for axiom in axioms:
        scoped_id(axiom.id,'axiom:')
        if type(axiom.revision) is not int or axiom.revision<1:raise ValueError('Invalid axiom revision')
        if Parser(signature).formula(axiom.text)!=axiom.formula:raise ValueError('Axiom AST disagrees with source text')
    if len({a.id for a in axioms})!=len(axioms) or parse_axioms(signature,result.source_text,axioms)!=axioms:
        raise ValueError('Axiom editor text and records disagree')
    return result


def restore(project,data):
    for value in data.get('universes',()):
        item=universe(value)
        if item.id in project.universes:raise ValueError('Duplicate universe identity')
        project.universes[item.id]=item
    project.universe_history=[universe(value) for value in data.get('universe_history',())]
    statuses={'witnessed-contradiction','model-constructed','undetermined','backend-incompatible','repair-candidates',
              'blocked-inconsistent','countermodel-constructed','backend-entailment','conditional-entailment'}
    for value in data.get('logic_records',()):
        if value['status'] not in statuses:raise ValueError('Unknown logical outcome')
        project.logic_records.append(LogicRecord(**{**value,'axiom_dependencies':tuple(tuple(pair) for pair in value['axiom_dependencies'])}))
