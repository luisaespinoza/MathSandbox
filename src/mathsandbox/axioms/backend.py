"""Optional Z3 translation. Finite failure is never a global inconsistency proof."""
import itertools
from .parser import variables,Parser
from .models import verify,counterexample


def require():
    try:import z3
    except ImportError:raise ValueError("Install the optional axiom backend: python -m pip install -e '.[workbench,axioms,dev]'") from None
    return z3


def compatible(universe):
    return universe.logic=='classical-equality' and universe.branch_policy=='uninterpreted-algebra' and universe.sort=='U'


class Translation:
    def __init__(self,universe,size=None,proof=False):
        if not compatible(universe): raise ValueError("Backend semantics incompatible with the requested logic/branches")
        self.z3=require();self.universe=universe;self.ctx=self.z3.Context(proof=proof)
        if size is None:self.sort=self.z3.DeclareSort('U',ctx=self.ctx);self.elements=None
        else:self.sort,self.elements=self.z3.EnumSort('U',[f'u{i}' for i in range(size)],ctx=self.ctx)
        self.constants={symbol.id:self.z3.Const(symbol.id,self.sort) for symbol in universe.signature if symbol.kind=='constant'}
        self.functions={symbol.id:self.z3.Function(symbol.id,*([self.sort]*symbol.arity),self.z3.BoolSort(ctx=self.ctx) if symbol.kind=='relation' else self.sort)
                        for symbol in universe.signature if symbol.kind!='constant'}
        self.solver=self.z3.Solver(ctx=self.ctx)

    def term(self,value,assignment):
        if value.kind=='variable':return assignment[value.symbol]
        if value.kind=='constant':return self.constants[value.symbol]
        return self.functions[value.symbol](*(self.term(arg,assignment) for arg in value.args))

    def formula(self,value,assignment):
        if value.kind in ('eq','ne'):
            a,b=[self.term(arg,assignment) for arg in value.terms]
            return a==b if value.kind=='eq' else a!=b
        if value.kind=='predicate':return self.functions[value.symbol](*(self.term(arg,assignment) for arg in value.terms))
        values=[self.formula(arg,assignment) for arg in value.operands]
        if value.kind=='and':return self.z3.And(*values)
        if value.kind=='or':return self.z3.Or(*values)
        if value.kind=='not':return self.z3.Not(values[0])
        if value.kind=='implies':return self.z3.Implies(*values)
        raise ValueError('Unsupported logical form')

    def close(self,value,label):
        names=sorted(variables(value))
        if self.elements is not None:
            rows=[self.formula(value,dict(zip(names,values))) for values in itertools.product(self.elements,repeat=len(names))]
            return self.z3.And(*rows) if rows else self.z3.BoolVal(True,ctx=self.ctx)
        assignment={name:self.z3.Const(label+':'+name,self.sort) for name in names}
        body=self.formula(value,assignment)
        return self.z3.ForAll(list(assignment.values()),body) if names else body

    def add_axioms(self,tracked=False):
        for axiom in self.universe.axioms:
            formula=self.close(axiom.formula,axiom.id)
            if tracked:self.solver.assert_and_track(formula,self.z3.Bool(axiom.id,ctx=self.ctx))
            else:self.solver.add(formula)

    def model(self):
        value=self.solver.model();indices={str(element):i for i,element in enumerate(self.elements)}
        constants={key:indices[str(value.eval(symbol,model_completion=True))] for key,symbol in self.constants.items()}
        tables={}
        for symbol in self.universe.signature:
            if symbol.kind=='constant':continue
            rows=[]
            for args in itertools.product(self.elements,repeat=symbol.arity):
                result=value.eval(self.functions[symbol.id](*args),model_completion=True)
                rows.append(self.z3.is_true(result) if symbol.kind=='relation' else indices[str(result)])
            tables[symbol.id]=rows
        return {'kind':'finite','size':len(self.elements),'elements':[str(value) for value in self.elements],
                'constants':constants,'tables':tables,
                'signature':[{'id':symbol.id,'name':symbol.name,'arity':symbol.arity,'kind':symbol.kind,'notation':symbol.notation} for symbol in self.universe.signature]}


def unrestricted(universe,goal=None,timeout=1800):
    translated=Translation(universe,proof=True);translated.solver.set(timeout=timeout);translated.add_axioms(tracked=True)
    if goal is not None:translated.solver.assert_and_track(translated.z3.Not(translated.close(goal,'goal')),translated.z3.Bool('negated-goal',ctx=translated.ctx))
    result=translated.solver.check();details={'outcome':str(result),'scope':'Unrestricted nonempty first-order universe; no finite cardinality assumption','timeout_ms':timeout}
    if result==translated.z3.unsat:
        ids=[str(value.decl().name()) for value in translated.solver.unsat_core()]
        details['unsat_core']=[{'id':axiom.id,'label':axiom.label,'revision':axiom.revision,'text':axiom.text} for axiom in universe.axioms if axiom.id in ids]
        details['uses_negated_goal']='negated-goal' in ids
        try:
            proof=translated.solver.proof().sexpr()
            details.update(proof_artifact=proof[:18000],proof_truncated=len(proof)>18000,proof_status='Z3 proof artifact; not independently replayed or certified')
        except Exception:details['proof_status']='No independently checked proof certificate is available'
    elif result==translated.z3.unknown:details['reason']=translated.solver.reason_unknown()
    return details


def finite(universe,goal=None,max_size=4,timeout=500):
    attempts=[]
    for size in range(1,max_size+1):
        translated=Translation(universe,size);translated.solver.set(timeout=timeout);translated.add_axioms()
        if goal is not None:translated.solver.add(translated.z3.Not(translated.close(goal,'goal')))
        result=translated.solver.check();attempts.append({'size':size,'outcome':str(result)})
        if result==translated.z3.sat:
            model=translated.model();validation=verify(universe,model)
            if not validation['valid']:raise ValueError('Solver model failed independent axiom validation')
            witness=None
            if goal is not None:
                witness=counterexample(goal,model,{s.id:s for s in universe.signature})
                if witness is None:raise ValueError('Solver countermodel did not refute the conjecture')
            return {'model':model,'validation':validation,'attempts':attempts,'counterexample':witness}
    return {'model':None,'attempts':attempts,'scope':'No model found at tested sizes; consistency and unrestricted entailment remain undetermined'}


def real_projection(universe,timeout=150):
    if not compatible(universe): return {"valid":False,"reason":"Backend semantics incompatible"}
    z3=require();ctx=z3.Context();by_id={symbol.id:symbol for symbol in universe.signature}
    known={'add':2,'neg':1,'mul':2,'inv':1,'star':2,'zero':0,'one':0}
    if any(symbol.name not in known or known[symbol.name]!=symbol.arity or symbol.kind=='relation' for symbol in universe.signature):
        return {'valid':False,'reason':'The real projection interpretation does not license this signature'}
    def term(value,assignment):
        if value.kind=='variable':return assignment[value.symbol]
        symbol=by_id[value.symbol];name=symbol.name
        if value.kind=='constant':return z3.RealVal(0 if name=='zero' else 1,ctx=ctx)
        args=[term(arg,assignment) for arg in value.args]
        if name=='star':return args[1]
        if name=='add':return args[0]+args[1]
        if name=='neg':return -args[0]
        if name=='mul':return args[0]*args[1]
        if name=='inv':return z3.If(args[0]==0,z3.RealVal(0,ctx=ctx),1/args[0])
        raise ValueError('No real interpretation')
    def formula(value,assignment):
        if value.kind in ('eq','ne'):
            a,b=[term(arg,assignment) for arg in value.terms];return a==b if value.kind=='eq' else a!=b
        values=[formula(arg,assignment) for arg in value.operands]
        return {'and':lambda:z3.And(*values),'or':lambda:z3.Or(*values),'not':lambda:z3.Not(values[0]),'implies':lambda:z3.Implies(*values)}[value.kind]()
    checks=[]
    for axiom in universe.axioms:
        assignment={name:z3.Real('real:'+name,ctx=ctx) for name in variables(axiom.formula)}
        solver=z3.Solver(ctx=ctx);solver.set(timeout=timeout);solver.add(z3.Not(formula(axiom.formula,assignment)));outcome=solver.check()
        check={'label':axiom.label,'outcome':str(outcome)}
        if outcome==z3.sat:check['counterexample']={name:str(solver.model().eval(value,model_completion=True)) for name,value in assignment.items()}
        checks.append(check)
    return {'valid':all(check['outcome']=='unsat' for check in checks),'checks':checks,
            'model':{'kind':'ordinary-reals-right-projection','carrier':'ordinary real numbers','add':'ordinary addition','neg':'ordinary additive inverse',
                     'mul':'ordinary multiplication (distinct from star)','inv':'0 at zero, reciprocal otherwise','star':'star(a,b)=b','zero':'0','one':'1'},
            'validation':'Negation of each universal axiom checked unsatisfiable over Z3 real arithmetic; relative to that metatheory, not an absolute consistency certificate'}
