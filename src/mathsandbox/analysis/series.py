from dataclasses import asdict
import mpmath as mp
import math
import sympy as sp
from ..core.ir import identity
from .records import AnalyticGerm, Coefficient
from .compiler import numeric


def shifted(poly, z, value):
    return sp.Poly(poly,z,domain='EX').shift(value)


def rational_coefficients(expression, z, c, order, seed=None):
    p,q = sp.fraction(sp.cancel(expression))
    pp,qq = shifted(p,z,c),shifted(q,z,c)
    q0 = qq.nth(0)
    if q0 == 0:
        raise ValueError("A Taylor seed cannot be centered on a pole")
    coefficients=[]
    for n in range(order):
        if n == 0 and seed is not None:
            coefficients.append(seed)
        else:
            coefficients.append(sp.cancel((pp.nth(n)-sum(qq.nth(k)*coefficients[n-k] for k in range(1,min(n,qq.degree())+1)))/q0))
    return coefficients


def make_germ(compiler, provenance, kind, c, order, method='series'):
    if kind not in ('taylor','laurent') or type(order) is not int or not 2 <= order <= 48:
        raise ValueError("Choose Taylor/Laurent and a truncation order from 2 to 48")
    if method not in ('series','recurrence','derivative'):
        raise ValueError("Unknown coefficient method")
    z,exclusions=compiler.analytic_source()
    on_center=[root for root in exclusions if sp.simplify(root-c)==0]
    if kind=='taylor' and on_center:
        raise ValueError("Taylor center lies on a source exclusion; no removable extension is silently filled")
    rational=compiler.expression.is_rational_function(z)
    if method=='recurrence' and (not rational or kind!='taylor'):
        raise ValueError("Coefficient recurrence currently requires a rational Taylor germ")
    if method=='derivative' and kind!='taylor':
        raise ValueError("Derivative coefficients require a Taylor center")
    if method=='recurrence':
        values=rational_coefficients(compiler.expression,z,c,order)
        coefficients=tuple(Coefficient(i,compiler.reconstruct(value)) for i,value in enumerate(values))
    elif method=='derivative':
        values=[sp.simplify(sp.diff(compiler.expression,z,i).subs(z,c)/sp.factorial(i)) for i in range(order)]
        coefficients=tuple(Coefficient(i,compiler.reconstruct(value)) for i,value in enumerate(values))
    else:
        w=sp.Dummy('w')
        expansion=sp.series(compiler.expression.subs(z,w+c),w,0,order).removeO().expand()
        terms={}
        for term in sp.Add.make_args(expansion):
            coefficient,power=term.as_coeff_exponent(w)
            if not power.is_Integer or coefficient.has(w):
                raise ValueError("Expansion is outside the supported finite integer-power format (branched or infinite principal part)")
            terms[int(power)]=terms.get(int(power),0)+coefficient
        first=min(0,min(terms,default=0))
        if first < -64:
            raise ValueError("Laurent principal part exceeds the budget")
        coefficients=tuple(Coefficient(i,compiler.reconstruct(sp.simplify(terms.get(i,0)))) for i in range(first,order))
    others=[root for root in exclusions if sp.simplify(root-c)!=0]
    radius=sp.Min(*(sp.Abs(root-c) for root in others)) if others else sp.oo
    return AnalyticGerm(identity(),kind,compiler.reconstruct(c),compiler.obj.parameters[0],coefficients,
        '0',str(radius) if radius!=sp.oo else 'infinity',
        'Conservative source-domain radius; not a certified maximal convergence radius' if others else 'unbounded for the supported entire/punctured template',
        tuple(compiler.display(root) for root in exclusions),
        'Exact finite coefficients; truncated series has no certified global remainder',method,provenance)


def germ_details(compiler,germ,digits):
    rows=[]
    for coefficient in germ.coefficients:
        value=compiler.convert(coefficient.value)
        magnitude=abs(numeric(value,digits))
        rows.append({'power':coefficient.power,'coefficient':compiler.display(value),
                     'log_magnitude':float(mp.log10(1+magnitude)) if mp.log10(1+magnitude)<1e300 else None})
    _,exclusions=compiler.analytic_source()
    cc=numeric(compiler.convert(germ.center),digits)
    radius=min((abs(numeric(root,digits)-cc) for root in exclusions if sp.simplify(root-compiler.convert(germ.center))!=0),default=mp.inf)
    return {'radius_display':'unbounded' if not mp.isfinite(radius) else 'finite' if math.isfinite(float(radius)) else 'overflow',
            'radius_estimate':float(radius) if mp.isfinite(radius) and math.isfinite(float(radius)) else None,'germ_id':germ.id,'kind':germ.kind,'center':compiler.display(compiler.convert(germ.center)),
            'coefficients':rows,'inner_radius':germ.inner_radius,'outer_radius':germ.outer_radius,
            'radius_status':germ.radius_status,'exclusions':germ.exclusions,'error_model':germ.error_model,
            'coefficient_method':germ.coefficient_method}


def cauchy(compiler,c,order,radius,digits,references=None):
    z,exclusions=compiler.analytic_source()
    if any(sp.simplify(root-c)==0 for root in exclusions):
        raise ValueError("Cauchy Taylor coefficients require an analytic center")
    with mp.workdps(digits):
        cc=numeric(c,digits)
        rho=mp.mpf(radius)
        if not mp.isfinite(rho) or not 0 < rho <= 10:
            raise ValueError("Cauchy radius must be finite in (0,10]")
        nearest=min((abs(numeric(root,digits)-cc) for root in exclusions),default=mp.inf)
        if rho >= nearest*mp.mpf('0.8'):
            raise ValueError("Cauchy contour must remain safely inside the source-exclusion radius")
        function=sp.lambdify(z,compiler.expression,'mpmath')
        estimates=[]
        for n in range(min(order,8)):
            integrand=lambda theta: function(cc+rho*mp.exp(mp.j*theta))*mp.exp(-mp.j*n*theta)
            value,error=mp.quad(integrand,[0,mp.pi/2,mp.pi,3*mp.pi/2,2*mp.pi],error=True)
            coefficient=value/(2*mp.pi*rho**n)
            if not mp.isfinite(coefficient) or not mp.isfinite(error):
                raise ValueError("Nonfinite Cauchy quadrature result")
            row={'power':n,'coefficient':mp.nstr(coefficient,digits),
                 'quadrature_error_estimate':mp.nstr(error/(2*mp.pi*rho**n),digits)}
            if references is not None and n in references:
                row['symbolic_reference']=compiler.display(references[n])
                row['reference_absolute_difference']=mp.nstr(abs(coefficient-numeric(references[n],digits)),digits)
            estimates.append(row)
        return {'center':compiler.display(c),'radius':str(radius),'digits':digits,'coefficients':estimates,
                'orientation':'positive/counterclockwise','error_model':'mpmath quadrature heuristic, not a certified error bound'}
