"""Orientation edits must work with positional styles and fixed reference matrices."""
import copy
import pytest
from output_schema import ChartSpec,ChartEditCommand
from research_chart_editing import apply_research_edit
from report_table import TableOptions,build_table
from test_table_layout import CASES

@pytest.mark.parametrize('case',CASES,ids=lambda c:c['id'])
@pytest.mark.parametrize('orientation',['periods','indicators'])
def test_orientation_rebuilds_axes_preserves_observations_and_previous_state(case,orientation):
    previous=ChartSpec(report_table=TableOptions.model_validate(case['options']))
    before=previous.model_dump(); source=copy.deepcopy(case['series'])
    # Force a transition even for a fixture whose current direction matches.
    if previous.report_table.orientation==orientation:
        previous.report_table.orientation='indicators' if orientation=='periods' else 'periods'
        before=previous.model_dump()
    updated=apply_research_edit(previous,ChartEditCommand(kind='STYLE_EDIT',operation='set_table',params={'patch':{'orientation':orientation}}),[s['label'] for s in source])
    document=build_table(source,updated.report_table,title=case['title'])
    assert previous.model_dump()==before and source==case['series']
    assert document['options']['orientation']==orientation
    for section in document['layoutSections']:
        if orientation=='periods':assert all(r['id'].startswith('period:') for r in section['layoutRows'])
        else:assert all(r['id'].startswith('series:') for r in section['layoutRows'])
    assert updated.report_table.layout.base==previous.report_table.layout.base
    # Undo can restore the full old options without losing matrix/style data.
    assert ChartSpec.model_validate(before)==previous

@pytest.mark.parametrize('case',CASES,ids=lambda c:c['id'])
@pytest.mark.parametrize('change',['recent','labels'])
def test_subset_selection_rebuilds_stale_cell_targets(case,change):
    source=copy.deepcopy(case['series']);previous=ChartSpec(report_table=TableOptions.model_validate(case['options']))
    patch={'recent_periods':2} if change=='recent' else {'labels':[source[0]['label']]}
    before=previous.model_dump()
    updated=apply_research_edit(previous,ChartEditCommand(kind='STYLE_EDIT',operation='set_table',params={'patch':patch}),[s['label'] for s in source])
    document=build_table(source,updated.report_table,title=case['title'])
    assert previous.model_dump()==before and source==case['series']
    if change=='recent':assert all(len(s['periods'])<=2 for s in document['sections'])
    else:assert document['options']['labels']==[source[0]['label']]
