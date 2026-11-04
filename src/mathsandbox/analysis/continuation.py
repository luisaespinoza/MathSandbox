"""Taylor transport with a rational differential recurrence, never endpoint resetting."""
import mpmath as mp
import sympy as sp
from .compiler import center, numeric
from .series import rational_coefficients


def parse_path(text):
    if not isinstance(text,str) or len(text)>3000:
        raise ValueError("Path must be semicolon-separated real,imaginary coordinate pairs")
    result=[]
    for item in text.split(';'):
        values=item.strip().split(',')
        if len(values)!=2:
            raise ValueError("Path format: 0,0; 1,0; 2,0")
        result.append(center(*[value.strip() for value in values]))
    if not 2<=len(result)<=32:
        raise ValueError("A path requires 2..32 waypoints")
    return result


def transport(compiler,c,order,digits,path_text):
    z,roots=compiler.analytic_source()
    if not compiler.expression.is_rational_function(z):
        raise ValueError("Continuation currently requires a rational source and its differential recurrence")
    p,q=sp.fraction(sp.cancel(compiler.expression))
    if sp.Poly(p,z).degree()>12 or sp.Poly(q,z).degree()>4:
        raise ValueError("Rational continuation is bounded to numerator degree 12 and denominator degree four")
    path=parse_path(path_text)
    if sp.simplify(path[0]-c)!=0:
        raise ValueError("The first path waypoint must equal the germ center")
    p_functions=[sp.lambdify(z,sp.diff(p,z,k)/sp.factorial(k),'mpmath') for k in range(max(0,sp.degree(p,z))+1)]
    q_functions=[sp.lambdify(z,sp.diff(q,z,k)/sp.factorial(k),'mpmath') for k in range(sp.degree(q,z)+1)]

    def run(n,dps):
        with mp.workdps(dps):
            poles=[numeric(root,dps) for root in roots]
            waypoints=[numeric(value,dps) for value in path]
            for a,b in zip(waypoints,waypoints[1:]):
                for pole in poles:
                    if a==b:
                        if abs(pole-a)<mp.mpf(10)**(-dps//2):
                            raise ValueError("Path meets a source exclusion")
                        continue
                    ratio=(pole-a)/(b-a)
                    if 0<=mp.re(ratio)<=1 and abs(mp.im(ratio))<mp.mpf(10)**(-dps//2):
                        raise ValueError("Path crosses or is too close to a source exclusion at the working precision")
            position=waypoints[0]
            coefficients=[numeric(value,dps) for value in rational_coefficients(compiler.expression,z,c,n)]
            steps=[]
            for target in waypoints[1:]:
                while abs(target-position)>mp.mpf(10)**(-dps+5):
                    if len(steps)>=128:
                        raise ValueError("Continuation exceeded 128 overlapping disks")
                    radius=min((abs(pole-position) for pole in poles),default=mp.inf)
                    if radius==0:
                        raise ValueError("Continuation center lies on a source exclusion")
                    distance=abs(target-position)
                    step=min(distance,mp.mpf('0.3')*radius,mp.mpf('0.5'))
                    if step<mp.mpf(10)**(-dps//2):
                        raise ValueError("Step collapsed near a source exclusion")
                    h=(target-position)*step/distance
                    value=mp.polyval(list(reversed(coefficients)),h)
                    indicator=max(abs(coefficients[-k]*h**(n-k)) for k in range(1,min(4,n)+1))
                    new_center=position+h
                    pp=[mp.mpc(function(new_center)) for function in p_functions]
                    qq=[mp.mpc(function(new_center)) for function in q_functions]
                    if qq[0]==0:
                        raise ValueError("New center is singular")
                    # d(Q*f-P)/dz=0: n>=1 coefficients obey Q0*a_n=P_n-sum(Qk*a_(n-k)).
                    # a0 is ONLY the transported value; P0/Q0 is not used to reset it.
                    renewed=[value]
                    for i in range(1,n):
                        renewed.append(((pp[i] if i<len(pp) else 0)-sum(qq[k]*renewed[i-k] for k in range(1,min(i,len(qq)-1)+1)))/qq[0])
                    invariant=qq[0]*value-(pp[0] if pp else 0)
                    steps.append({'from':mp.nstr(position,dps),'center':mp.nstr(new_center,dps),
                                  'from_coordinates':[float(mp.re(position)),float(mp.im(position))],
                                  'center_coordinates':[float(mp.re(new_center)),float(mp.im(new_center))],
                                  'new_radius_estimate':mp.nstr(min((abs(pole-new_center) for pole in poles),default=mp.inf),dps),
                                  'radius_estimate':mp.nstr(radius,dps),'step_length':mp.nstr(abs(h),dps),
                                  'retained_tail_indicator':mp.nstr(indicator,dps),
                                  'differential_invariant_residual':mp.nstr(abs(invariant),dps)})
                    position,coefficients=new_center,renewed
            return coefficients[0],steps

    low,low_steps=run(order,digits)
    value,steps=run(order+8,digits+10)
    with mp.workdps(digits+10):
        # Independent comparison occurs AFTER transport; it never seeds the result.
        reference=sp.lambdify(z,compiler.expression,'mpmath')(numeric(path[-1],digits+10))
        return {'value':mp.nstr(value,digits),'endpoint':compiler.display(path[-1]),
                'reference_value':mp.nstr(reference,digits),'reference_absolute_difference':mp.nstr(abs(value-reference),digits),
                'error_estimate':mp.nstr(abs(value-low),digits),'error_model':'Observed order/precision refinement difference; not a certified bound',
                'requested_order':order,'refined_order':order+8,'digits':digits,'working_digits':digits+10,
                'path':[compiler.display(value) for value in path], 'steps':steps,
                'method':'Taylor transport with d(Q*f-P)/dz=0; no exact-value resets at new centers',
                'branch_history':'Rational single-valued source; path and principal context retained; no multivalued continuation',
                'exclusions':[compiler.display(value) for value in roots], 'low_order_step_count':len(low_steps)}
