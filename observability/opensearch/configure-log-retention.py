"""Install lifecycle only for NEW dated app indices; preserve legacy indices/data."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('tracing', ROOT / 'observability/verify-tracing.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--retention-days', type=int, default=30)
    parser.add_argument('--replicas', type=int, choices=(0, 1), default=0)
    args = parser.parse_args()
    assert args.retention_days >= 7, 'Retention must be at least seven days'
    model = json.loads(v.docker(*v.COMPOSE, 'config', '--format', 'json'))
    port = int(model['services']['opensearch']['ports'][0]['published'])

    def request(path, method='GET', body=None):
        status, _, value = v.request(port, path, method, body)
        assert status in (200, 201), 'OpenSearch operation failed: ' + path
        return value

    health = request('/_cluster/health')
    if args.replicas == 0:
        assert health['number_of_data_nodes'] == 1, 'Never reduce replicas on a multi-node cluster'
        assert model['services']['opensearch']['environment']['discovery.type'] == 'single-node'
    policy_id = 'springboot-dated-logs-retention'
    patterns = ['springboot-' + name + '-20*-logs' for name in ('user', 'learning', 'jwks')]
    policy = {'description': 'Retention for new dated Spring Boot application indices only; legacy indices excluded',
              'default_state': 'hot',
              'states': [{'name': 'hot', 'actions': [], 'transitions': [
                  {'state_name': 'delete', 'conditions': {'min_index_age': str(args.retention_days) + 'd'}}]},
                  {'name': 'delete', 'actions': [{'retry': {'count': 3, 'backoff': 'exponential', 'delay': '1m'},
                                                'delete': {}}], 'transitions': []}],
              'ism_template': [{'index_patterns': patterns, 'priority': 200}]}
    status, _, existing = v.request(port, '/_plugins/_ism/policies/' + policy_id)
    if status == 404:
        request('/_plugins/_ism/policies/' + policy_id, 'PUT', {'policy': policy})
    else:
        assert status == 200
        actual = existing['policy']
        assert all(actual.get(k) == value for k, value in policy.items() if k != 'ism_template'), 'Existing policy differs; review before changing it'
        assert [{k: item[k] for k in ('index_patterns', 'priority')} for item in actual['ism_template']] == policy['ism_template']
    for name, pattern in zip(('user', 'learning', 'jwks'), patterns):
        legacy = 'springboot-' + name + '-logs'
        mapping = request('/' + legacy + '/_mapping')[legacy]['mappings']
        template = {'index_patterns': [pattern], 'priority': 200,
                    'template': {'settings': {'number_of_shards': 1, 'number_of_replicas': args.replicas},
                                 'mappings': copy.deepcopy(mapping)}}
        request('/_index_template/springboot-dated-' + name, 'PUT', template)
        # Only the three named application indices, never system/unrelated indices.
        if args.replicas == 0:
            request('/' + legacy + '/_settings', 'PUT', {'index': {'number_of_replicas': 0}})
        explained = request('/_plugins/_ism/explain/' + legacy)
        assert explained[legacy].get('policy_id') is None, 'Legacy index unexpectedly managed'
        print('PASS: new dated template and preserved unmanaged legacy index:', legacy, flush=True)
    checked = request('/_plugins/_ism/policies/' + policy_id)['policy']
    assert [{k: item[k] for k in ('index_patterns', 'priority')} for item in checked['ism_template']] == policy['ism_template']
    print('PASS: supported ISM policy installed; no retroactive attachment or deletion; retention days:', args.retention_days)


if __name__ == '__main__':
    main()
