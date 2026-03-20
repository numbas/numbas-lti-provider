from django.conf import settings
import json
from numbas_lti.models import Resource
from pathlib import Path

def load_structure():
    with open(Path(settings.MEDIA_ROOT) / 'ncl_data_science' / 'structure.json') as f:
        structure = json.load(f)

    for topic in structure['topics']:
        for subtopic in topic['subtopics']:
            subtopic['resource'] = Resource.objects.get(pk=subtopic['resource_pk'])

    topics_dict = {t['id']: t for t in structure['topics']}

    for case_study in structure['case_studies']:
        case_study['resource'] = Resource.objects.get(pk=case_study['resource_pk'])
        case_study['topics'] = [ topics_dict[t] for t in case_study['topics'] ]
        case_study['extension_topics'] = [ topics_dict[t] for t in case_study['extension_topics'] ]

    return structure
