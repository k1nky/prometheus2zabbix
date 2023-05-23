# prometheus2zabbix

The tool to convert prometheus metrics to a zabbix template.

## Compatibility

Tested on Zabbix 6.0 (should work with Zabbix 6+).

## How it works

1. Run the tool to build a zabbix template in yaml format.
```
python prometheus2zabbix.py -u "http://my_host:9000/metrics" -n "My Awesome Application" > template.yaml
```
2. Go to "Configuration/Templates" in Zabbix UI and click "Import".
3. Select the generated file (step 1) and run "Import".

## Usage

```
prometheus2zabbix [-h] [-u METRICS_URL] [-n TEMPLATE_NAME] [-m ITEM_MASTER_KEY] [-t APPLICATION_TAG]
```
- `-u` - url to prometheus metrics. Default: http://localhost:9000/metrics.
- `-n` - template name. Default: Template My Application.
- `-m` - master item key (must be unique within a single host). All generated items, discovery rules, item prototypes will depend on this item. Default: http_raw_prometheus_metrics.
- `-t` - application tag value. All generated items and item prototypes will have the "Application: <specified_tag_value>" tag. Default: None.
- `-h` - show usage message.

### Example

```
python prometheus2zabbix.py -u "http://my_host:9000/metrics" -n "My Awesome Application" -m http_raw_my_awesome_app_metrics -t "Awesome Application" > template.yaml
```