# Copyright 2022 Tier IV, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Script to make report page
"""
from __future__ import annotations
import os
import argparse
from pathlib import Path
import yaml
import flask

app = flask.Flask(__name__)


def render_page(destination_path, template_path, report_name, package_list, stats_node_dict,
                stats_path, stats_cb_sub_warn, stats_cb_timer_warn):
    """Render html page"""
    with app.app_context():
        with open(template_path, 'r', encoding='utf-8') as f_html:
            template_string = f_html.read()
            rendered = flask.render_template_string(
                template_string,
                title=report_name,
                package_list=package_list,
                stats_node_dict=stats_node_dict,
                stats_path=stats_path,
                stats_cb_sub_warn=stats_cb_sub_warn,
                stats_cb_timer_warn=stats_cb_timer_warn,
            )

        with open(destination_path, 'w', encoding='utf-8') as f_html:
            f_html.write(rendered)


def get_package_list(report_dir: str) -> list[str]:
    """Create package name list in node analysis"""
    package_list = os.listdir(report_dir + '/node')
    package_list = [f for f in package_list if os.path.isdir(os.path.join(report_dir + '/node', f))]
    package_list.sort()
    return package_list


def get_stats_node(report_dir: str) -> dict:
    """Read stats"""
    stats_dict = {}
    package_list = get_package_list(report_dir)
    for package_name in package_list:
        with open(report_dir + '/node/' + package_name + '/stats_node.yaml', 'r', encoding='utf-8') as f_yaml:
            stats = yaml.safe_load(f_yaml)
            stats_dict[package_name] = stats
    return stats_dict


def get_stats_path(report_dir: str):
    """Read stats"""
    with open(report_dir + '/path/stats_path.yaml', 'r', encoding='utf-8') as f_yaml:
        stats = yaml.safe_load(f_yaml)
    return stats


def get_stats_callback_subscription(report_dir: str):
    """Read stats"""
    with open(report_dir + '/check_callback_sub/stats_callback_subscription.yaml', 'r', encoding='utf-8') as f_yaml:
        stats = yaml.safe_load(f_yaml)
    with open(report_dir + '/check_callback_sub/stats_callback_subscription_warning.yaml', 'r', encoding='utf-8') as f_yaml:
        stats_warn = yaml.safe_load(f_yaml)
    return stats, stats_warn


def get_stats_callback_timer(report_dir: str):
    """Read stats"""
    with open(report_dir + '/check_callback_timer/stats_callback_timer.yaml', 'r', encoding='utf-8') as f_yaml:
        stats = yaml.safe_load(f_yaml)
    with open(report_dir + '/check_callback_timer/stats_callback_timer_warning.yaml', 'r', encoding='utf-8') as f_yaml:
        stats_warn = yaml.safe_load(f_yaml)
    return stats, stats_warn


def find_latency_topk(package_name, stats_node, numk=20) -> None:
    """Find callback functions whose latency time is the longest(top5), and add this information into stats"""
    callback_latency_list = []
    for node_name, node_info in stats_node.items():
        callbacks = node_info['callbacks']
        for _, callback_info in callbacks.items():
            callback_latency_list.append({
                'link': 'node/' + package_name + '/index.html#' + node_name,
                'displayname': flask.Markup(node_name + '<br>' + callback_info['displayname']),
                'avg': callback_info['Latency']['avg'] if isinstance(callback_info['Latency']['avg'], (int, float)) else 0,
                'min': callback_info['Latency']['min'] if isinstance(callback_info['Latency']['min'], (int, float)) else 0,
                'max': callback_info['Latency']['max'] if isinstance(callback_info['Latency']['max'], (int, float)) else 0,
            })

    callback_latency_list = sorted(callback_latency_list, reverse=True, key=lambda x: x['avg'])
    callback_latency_list = callback_latency_list[:numk]
    stats_node['latency_topk'] = callback_latency_list


def make_report(report_dir: str, index_filename: str='index'):
    """Make report page"""
    report_name = report_dir.split('/')[-1]

    package_list = get_package_list(report_dir)
    stats_node_dict = get_stats_node(report_dir)
    for package_name in package_list:
        find_latency_topk(package_name, stats_node_dict[package_name])

    stats_path = get_stats_path(report_dir)
    _, stats_cb_sub_warn = get_stats_callback_subscription(report_dir)
    _, stats_cb_timer_warn = get_stats_callback_timer(report_dir)

    destination_path = f'{report_dir}/{index_filename}.html'
    template_path = f'{Path(__file__).resolve().parent}/template_report_top.html'
    render_page(destination_path, template_path, report_name, package_list, stats_node_dict,
                stats_path, stats_cb_sub_warn, stats_cb_timer_warn)


def parse_arg():
    """Parse arguments"""
    parser = argparse.ArgumentParser(
                description='Script to make report page')
    parser.add_argument('report_directory', nargs=1, type=str)
    args = parser.parse_args()
    return args


def main():
    """Main function"""
    args = parse_arg()
    report_dir = str(Path(args.report_directory[0]))
    make_report(report_dir, 'index')
    print('<<< OK. report page is created >>>')


if __name__ == '__main__':
    main()
