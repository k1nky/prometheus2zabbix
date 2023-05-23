import yaml
import uuid
from prometheus_client.parser import text_string_to_metric_families
import requests
from urllib.parse import urlparse
from argparse import ArgumentParser

yaml.Dumper.ignore_aliases = lambda *args : True


DEFAULT_TEMPLATE_NAME = 'Template My Application'
DEFAULT_TEMPLATE_MASTER_KEY = 'http_raw_prometheus_metrics'
DEFAULT_TEMPLATE_APPLICATION_TAG = ''
DEFAULT_METRICS_URL = 'http://localhost:9000/metrics'


cmd_parser = ArgumentParser(
    prog='prometheus2zabbix',
    description='Convert prometheus metrics to a zabbix template'   
)
cmd_parser.add_argument('-u', '--url', metavar='METRICS_URL', action='store', default=DEFAULT_METRICS_URL)
cmd_parser.add_argument('-n', '--name', metavar='TEMPLATE_NAME', action='store', default=DEFAULT_TEMPLATE_NAME)
cmd_parser.add_argument('-m', '--master-key', metavar='ITEM_MASTER_KEY', action='store', default=DEFAULT_TEMPLATE_MASTER_KEY)
cmd_parser.add_argument('-t', '--tag', metavar='APPLICATION_TAG', action='store', default=DEFAULT_TEMPLATE_APPLICATION_TAG)
args = cmd_parser.parse_args()

def get_schema(url):
    metrics = requests.get(url).content
    schema = []
    for family in text_string_to_metric_families(metrics.decode('utf-8')):
        schema.append({
            'type': family.type,
            'name': family.samples[0].name,
            'help': family.documentation,
            'labels': family.samples[0].labels
        })
    return schema

def zbx_item_key(metric):
    labels_str = ",".join([f'{k}="{{#{k.upper()}}}"' for k in metric['labels'].keys()])
    return f"{metric['name']}[{labels_str}]"

def gen_uuid():
    return str(uuid.uuid4()).replace('-','')

class Zabbix60Template():

    def __init__(self, name=DEFAULT_TEMPLATE_NAME, master_key=DEFAULT_TEMPLATE_MASTER_KEY, tags=DEFAULT_METRICS_URL):
        self.name = name
        self.master_key = master_key
        self.tags = tags
        self.template = {
            'zabbix_export': {
                'version': '6.0',
                'groups': [{
                    'uuid': gen_uuid(),
                    'name': 'Templates/Application'
                }],
                'templates': [{
                    'uuid': gen_uuid(),
                    'template': self.name,
                    'name': self.name,
                    'groups': [{'name': 'Templates/Application'}],
                    'items': [],
                    'discovery_rules': []
                }],
            }
        }

    def to_yaml(self):
        return yaml.dump(self.template, default_flow_style=False)
    
    def build_item(self, metric):
        return {
            'uuid': gen_uuid(),
            'name': metric['name'],
            'type': 'DEPENDENT',
            'key': metric['name'],
            'delay': '0',
            'value_type': 'FLOAT',
            'preprocessing': [{
                'type': 'PROMETHEUS_PATTERN',
                'parameters': [metric['name'], 'value', '']
            }],
            'master_item': {'key': self.master_key},
            'tags': self.tags
        }
    
    def build(self, url=DEFAULT_METRICS_URL):

        schema = get_schema(url)
        parsed_url = urlparse(url)

        self.template['zabbix_export']['templates'][0]['items'].append({
            'uuid': gen_uuid(),
            'name': self.master_key,
            'type': 'HTTP_AGENT',
            'key': self.master_key,
            'trends': '0',
            'history': '0',
            'value_type': 'TEXT',
            'url': f'{parsed_url.scheme}://{{HOST.NAME}}:{parsed_url.port}{parsed_url.path}'
        })
        for prom_metric in schema:
            if len(prom_metric['labels']) == 0:
                self.template['zabbix_export']['templates'][0]['items'].append(self.build_item(prom_metric))
            else:
                self.template['zabbix_export']['templates'][0]['discovery_rules'].append(self.build_discovery_rule(prom_metric))

    def build_discovery_rule(self, metric):
        discovery_rule = {
            'uuid': gen_uuid(),
            'name': f'Discovery {metric["name"]}',
            'type': 'DEPENDENT',
            'key': f'{metric["name"]}.discovery',
            'delay': '0',
            'master_item': {
                'key': self.master_key
            },
            'preprocessing': [
                {
                    'type': 'PROMETHEUS_TO_JSON',
                    'parameters': [
                        metric["name"]
                    ]
                }
            ]
        }
        lld_macros = [
            {'lld_macro': '{#HELP}', 'path': '$["help"]'},
            {'lld_macro': '{#METRIC}', 'path': '$["name"]'}
        ]
        for label in metric["labels"]:
            lld_macros.append({
                'lld_macro': f'{{#{label.upper()}}}',
                'path': f'$.labels["{label}"]'
            })
        discovery_rule['lld_macro_paths'] = lld_macros
        labels_line = ",".join([f'{k}="{{#{k.upper()}}}"' for k in metric["labels"].keys()])
        discovery_rule['item_prototypes'] = [{
            'uuid': gen_uuid(),
            'name': zbx_item_key(metric),
            'type': 'DEPENDENT',
            'key': zbx_item_key(metric),
            'delay': '0',
            'trends': '0',
            'value_type': 'FLOAT',
            'description': '{#HELP}',
            'master_item': {
                'key': self.master_key
            },
            'tags': self.tags,
            'preprocessing': [
                {
                    'type': 'PROMETHEUS_PATTERN',
                    'parameters': [
                        '{#METRIC}{' + labels_line + '}',
                        'value',
                        ''
                        ]
                }
            ]
        }]
        return discovery_rule



tags = []
if len(args.tag) > 0:
    tags.append({
        'tag': 'Application',
        'value': args.tag
    })

template = Zabbix60Template(
    name=args.name,
    master_key=args.master_key,
    tags=tags
    )
template.build(args.url)
print(template.to_yaml())