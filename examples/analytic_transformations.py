"""Run: python examples/analytic_transformations.py"""
from pathlib import Path
from mathsandbox import Project, save
from mathsandbox.adapters.complex_numeric import COMPLEX_CONTEXT
from mathsandbox.analysis.engine import run


def main():
    project=Project()
    project.define('f(z)=1/(1+z^2)',COMPLEX_CONTEXT)
    germ=run(project,'f','taylor',order=10,coefficient_method='recurrence')
    print('Taylor:',[(row['power'],row['coefficient']) for row in germ.details['coefficients']])
    print('Conservative source-domain radius:',germ.details['outer_radius'])
    cauchy=run(project,'f','cauchy',order=4,digits=35)
    print('Cauchy estimates:',cauchy.details['cauchy']['coefficients'])
    continued=run(project,'f','continue',order=32,digits=40,path='0,0;2,0')
    value=continued.details['continuation']
    print('Numerically continued to 2:',value['value'])
    print('Independent reference:',value['reference_value'])
    print('Observed refinement difference (not a certified bound):',value['error_estimate'])
    project.define('F(x,y,a,b)=y^2-a*x^3+b*x')
    constraint=run(project,'F','parameter-constraint')
    print('Necessary parameter identity:',constraint.details['constraint'])
    print('Assumptions:',constraint.assumptions)
    print('Reconstruction:',constraint.reconstruction)
    project.define('pole(z)=1/z',COMPLEX_CONTEXT)
    laurent=run(project,'pole','laurent',order=6)
    print('Laurent:',[(row['power'],row['coefficient']) for row in laurent.details['coefficients']])
    path=Path('/tmp/mathsandbox-analytic-transformations.json')
    save(project,path)
    print('Saved typed germs and analysis records to',path)


if __name__=='__main__':main()
