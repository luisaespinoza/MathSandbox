from dataclasses import dataclass
from .compiler import center, number


@dataclass(frozen=True)
class AnalysisSettings:
    method: str = 'taylor'
    center_real: str = '0'
    center_imag: str = '0'
    order: int = 32
    coefficient_method: str = 'series'
    radius: str = '1/2'
    path: str = '0,0;2,0'
    dependent: str = 'y'
    parameters: str = 'a,b'

    def validate(self,project):
        if self.method not in ('taylor','laurent','cauchy','continue','parameter-constraint') and self.method not in project.transform_registry.definitions:
            raise ValueError("Unknown analysis method")
        if type(self.order) is not int or not 2<=self.order<=48:
            raise ValueError("Analysis order must be an integer from 2 to 48")
        if self.coefficient_method not in ('series','derivative','recurrence'):
            raise ValueError("Unknown coefficient method")
        center(self.center_real,self.center_imag)
        if not 0<number(self.radius)<=10:
            raise ValueError("Contour radius must be in (0,10]")
        if not isinstance(self.path,str) or len(self.path)>3000 or not isinstance(self.dependent,str) or not isinstance(self.parameters,str):
            raise ValueError("Malformed analysis controls")
