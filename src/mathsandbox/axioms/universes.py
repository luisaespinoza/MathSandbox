from dataclasses import asdict,replace
import hashlib
import json
from ..core.ir import identity
from .records import Symbol,Universe
from .parser import parse_axioms

DEFAULT_SIGNATURE=(('zero',0,'constant','0'),('one',0,'constant','1'),('add',2,'function','+'),('neg',1,'function','−'),
                   ('mul',2,'function','·'),('inv',1,'function','inverse'),('star',2,'function','⋆'))

GROUP='''add_assoc: add(add(a,b),c)=add(a,add(b,c))
add_left_zero: add(0,a)=a
add_right_zero: add(a,0)=a
add_left_inverse: add(neg(a),a)=0
add_right_inverse: add(a,neg(a))=0'''
ABELIAN=GROUP+'\nadd_commute: add(a,b)=add(b,a)'
SEMIGROUP='star_assoc: star(star(a,b),c)=star(a,star(b,c))'
MONOID=SEMIGROUP+'\nstar_left_unit: star(1,a)=a\nstar_right_unit: star(a,1)=a'
RING=ABELIAN+'''\nmul_assoc: mul(mul(a,b),c)=mul(a,mul(b,c))
mul_commute: mul(a,b)=mul(b,a)
mul_left_unit: mul(1,a)=a
mul_right_unit: mul(a,1)=a
mul_left_dist: mul(a,add(b,c))=add(mul(a,b),mul(a,c))
mul_right_dist: mul(add(a,b),c)=add(mul(a,c),mul(b,c))'''
FIELD=RING+'\ndistinct: 0!=1\nfield_inverse: a!=0 => mul(a,inv(a))=1'
STAR=ABELIAN+'\ndistinct: 0!=1\n'+SEMIGROUP+'''
star_left_dist: star(a,add(b,c))=add(star(a,b),star(a,c))
star_right_dist: star(add(a,b),c)=add(star(a,c),star(b,c))
star_10: star(1,0)=0
star_01: star(0,1)=1'''
TEMPLATES={'semigroup':SEMIGROUP,'monoid':MONOID,'group':GROUP,'ring':RING,'field':FIELD,
           'star-contradiction':STAR,'projection': '\n'.join(line for line in STAR.splitlines() if not line.startswith('star_right_dist:'))}


def fingerprint(universe):
    return hashlib.sha256(json.dumps(asdict(universe),sort_keys=True,separators=(',',':')).encode()).hexdigest()


def create(template='star-contradiction',name=None):
    signature=tuple(Symbol('symbol:'+identity(),*values) for values in DEFAULT_SIGNATURE)
    policy='uninterpreted-algebra'
    if template in ('principal-root','multivalued-root'):
        signature+=(Symbol('symbol:'+identity(),'iota',0,'constant','ι'),)
        if template=='principal-root':
            signature+=(Symbol('symbol:'+identity(),'root',1,'function','√'),)
            text='iota_definition: iota=root(neg(iota))';policy='principal-complex-root'
        else:
            signature+=(Symbol('symbol:'+identity(),'Root',2,'relation','root relation'),)
            text='iota_definition: Root(neg(iota),iota)\nroot_square: Root(a,b) => mul(b,b)=a';policy='multivalued-complex-root'
    elif template in TEMPLATES:text=TEMPLATES[template]
    else:raise ValueError('Unknown universe template')
    return Universe('universe:'+identity(),name or template,signature,parse_axioms(signature,text),text,branch_policy=policy)


def edit(universe,text,*,name=None,logic=None,branch_policy=None):
    axioms=parse_axioms(universe.signature,text,universe.axioms)
    values=dict(source_text=text,axioms=axioms,name=name or universe.name,logic=logic or universe.logic,
                branch_policy=branch_policy or universe.branch_policy)
    if all(getattr(universe,key)==value for key,value in values.items()):return universe
    return replace(universe,revision=universe.revision+1,**values)


def fork(universe,name=None):
    return replace(universe,id='universe:'+identity(),revision=1,parent_id=universe.id,name=name or universe.name+' (fork)')


def drop(universe,labels):
    if not labels or len(labels)!=len(set(labels)) or any(label not in {a.label for a in universe.axioms} for label in labels):
        raise ValueError('Choose existing, distinct axiom labels to remove')
    axioms=tuple(a for a in universe.axioms if a.label not in labels)
    return replace(universe,axioms=axioms,source_text='\n'.join(a.label+': '+a.text for a in axioms))


def signature_text(universe):
    return ', '.join(symbol.name+('?' if symbol.kind=='relation' else '')+'/'+str(symbol.arity) for symbol in universe.signature)


def parse_signature(text,old=()):
    import re
    if not isinstance(text,str) or len(text)>1000:raise ValueError('Malformed signature')
    prior={(s.name,s.arity,s.kind):s for s in old};result=[]
    for piece in text.split(','):
        match=re.fullmatch(r'\s*([A-Za-z][A-Za-z0-9_]{0,19})(\?)?\s*/\s*([0-3])\s*',piece)
        if not match:raise ValueError('Signature format: zero/0, one/0, star/2, Root?/2')
        name,relation,arity=match.groups();arity=int(arity);kind='relation' if relation else 'constant' if arity==0 else 'function'
        if any(s.name==name for s in result):raise ValueError('Duplicate signature name')
        result.append(prior.get((name,arity,kind)) or Symbol('symbol:'+identity(),name,arity,kind,name))
    if not 1<=len(result)<=12:raise ValueError('Signature supports 1..12 symbols')
    return tuple(result)


def update(universe,text,signature,*,name=None,logic=None,branch_policy=None):
    symbols=parse_signature(signature,universe.signature)
    # Reparse first, so a failed signature/axiom edit leaves the original untouched.
    axioms=parse_axioms(symbols,text,universe.axioms)
    values=dict(signature=symbols,axioms=axioms,source_text=text,name=name or universe.name,
                logic=logic or universe.logic,branch_policy=branch_policy or universe.branch_policy)
    if all(getattr(universe,key)==value for key,value in values.items()):return universe
    return replace(universe,revision=universe.revision+1,**values)
