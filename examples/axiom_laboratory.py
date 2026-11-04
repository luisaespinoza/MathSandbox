"""Contradiction, protected repair, and an explicit alternative star model."""
from mathsandbox.ui.workbench import Workbench


def main():
    workbench = Workbench()
    workbench.axiom_create({'template': 'star-contradiction'})
    print('Foundations:', workbench.axiom_run({'operation': 'check'})['record']['status'])
    repair = workbench.axiom_run({'operation': 'repair'})['record']
    print('Repairs:', [candidate['remove'] for candidate in repair['details']['candidates']])
    workbench.axiom_apply_repair({'record_id': repair['id'], 'candidate': 0})
    model = workbench.axiom_run({'operation': 'projection'})['record']
    print('Real right projection:', model['status'])
    for law, evidence in model['details']['properties'].items():
        print(f'  {law}: {evidence["holds"]}')
    with open('axiom-laboratory-project.json', 'w', encoding='utf-8') as stream:
        stream.write(workbench.export())


if __name__ == '__main__':
    main()
