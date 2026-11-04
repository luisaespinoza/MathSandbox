"""Typed historical analysis decoding; no result populates an evaluation cache."""
from .records import AnalyticGerm, Coefficient, AnalysisRecord
from .registry import TransformationDefinition, BUILTINS


def restore(project,data,expression,provenance):
    for item in data.get('transform_registry',()):
        definition=TransformationDefinition(**{**item,**{key:expression(item[key]) if item.get(key) is not None else None for key in ('parameter','pattern','replacement')}})
        builtin=next((value for value in BUILTINS if value.id==definition.id),None)
        if builtin is not None:
            if definition!=builtin:
                raise ValueError("Modified builtin transformation semantics")
        else:
            project.transform_registry.register(definition)
    for item in data.get('analytic_germs',()):
        if item['kind'] not in ('taylor','laurent'):
            raise ValueError("Unknown germ type")
        coefficients=tuple(Coefficient(value['power'],expression(value['value'])) for value in item['coefficients'])
        if len(coefficients)>112 or any(type(value.power) is not int for value in coefficients):
            raise ValueError("Malformed germ coefficients")
        germ=AnalyticGerm(**{**item,'center':expression(item['center']),'variable':expression(item['variable']),
            'coefficients':coefficients,'exclusions':tuple(item['exclusions']),'provenance':provenance(item['provenance'])})
        if germ.id in project.analytic_germs:
            raise ValueError("Duplicate germ identity")
        project.analytic_germs[germ.id]=germ
    for item in data.get('analysis_records',()):
        if item['status'] not in ('exact-symbolic','conditional-symbolic-identity','numerically-computed','exploratory','unevaluated'):
            raise ValueError("Unknown analysis status")
        project.analysis_records.append(AnalysisRecord(**{**item,'result':expression(item['result']) if item['result'] else None,
            'assumptions':tuple(item['assumptions']),'exceptional_sets':tuple(item['exceptional_sets']),
            'provenance':provenance(item['provenance'])}))
