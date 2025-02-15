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
Script to check gap b/w timer frequency and callback function wake-up frequency
"""
from __future__ import annotations
import sys
import os
from pathlib import Path
import argparse
import logging
import statistics
import yaml
from caret_analyze import Architecture, Application
from caret_analyze.runtime.callback import CallbackBase
from caret_analyze.plot import Plot
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/..')
from common import utils

_logger: logging.Logger = None


def create_stats(callback: CallbackBase, package_dict:dict, freq_timer,
                 freq_callback, num_huge_gap, graph_filename) -> dict:
    """Create stats"""
    stats = {
        'node_name': callback.node_name,
        'package_name': utils.nodename2packagename(package_dict, callback.node_name),
        'callback_name': callback.callback_name,
        'callback_displayname': utils.make_callback_displayname(callback),
        'freq_timer': freq_timer,
        'freq_callback': freq_callback,
        'num_huge_gap': num_huge_gap,
        'graph_filename': graph_filename
    }
    return stats


def analyze_callback(args, dest_dir, package_dict: dict, callback: CallbackBase) -> tuple(dict, bool):
    """Analyze a timer callback function"""
    _logger.debug(f'Processing: {callback.callback_name}')
    freq_timer = 1e9 / float(callback.timer.period_ns)
    freq_threshold = freq_timer * (1 - args.gap_threshold_ratio)
    p_timeseries = Plot.create_callback_frequency_plot([callback])
    try:
        figure = p_timeseries.show('system_time', export_path='dummy.html')
    except:
        _logger.warning(f'This callback is not called: {callback.callback_name}')
        return None, False
    figure.y_range.start = 0
    graph_filename = callback.callback_name.replace("/", "_")[1:]
    graph_filename = graph_filename[:250]
    utils.export_graph(figure, dest_dir, graph_filename, _logger)

    measurement = p_timeseries.to_dataframe().dropna()
    freq_callback_list = measurement.iloc[:-2, 1]  # remove the last data because freq becomes small
    if len(freq_callback_list) < 2:
        _logger.warning(f'Not enough data: {callback.callback_name}')
        return None, False
    freq_callback_avg = statistics.mean(freq_callback_list)
    num_huge_gap = sum(freq_callback <= freq_threshold for freq_callback in freq_callback_list)

    stats = create_stats(callback, package_dict, freq_timer, freq_callback_avg, num_huge_gap, graph_filename)

    is_warning = False
    if num_huge_gap >= args.count_threshold:
        is_warning = True
    return stats, is_warning


def analyze(args, dest_dir):
    """Analyze All"""
    utils.make_destination_dir(dest_dir, args.force, _logger)
    lttng = utils.read_trace_data(args.trace_data[0], args.start_point, args.duration, False)
    arch = Architecture('lttng', str(args.trace_data[0]))
    app = Application(arch, lttng)

    package_dict, ignore_list = utils.make_package_list(args.package_list_json, _logger)

    stats_all_list = []
    stats_warning_list = []

    callbacks = app.callbacks
    for callback in callbacks:
        if utils.check_if_ignore(package_dict, ignore_list, callback.callback_name):
            continue
        if 'timer_callback' == callback.callback_type.type_name:
            stats, is_warning = analyze_callback(args, dest_dir, package_dict, callback)
            if stats:
                stats_all_list.append(stats)
            if is_warning:
                stats_warning_list.append(stats)

    stats_all_list = sorted(stats_all_list, key=lambda x: x['callback_name'])
    stats_warning_list = sorted(stats_warning_list, key=lambda x: x['callback_name'])

    with open(f'{dest_dir}/stats_callback_timer.yaml', 'w', encoding='utf-8') as f_yaml:
        yaml.safe_dump(stats_all_list, f_yaml, encoding='utf-8',
                       allow_unicode=True, sort_keys=False)
    with open(f'{dest_dir}/stats_callback_timer_warning.yaml', 'w', encoding='utf-8') as f_yaml:
        yaml.safe_dump(stats_warning_list, f_yaml, encoding='utf-8',
                       allow_unicode=True, sort_keys=False)


def parse_arg():
    """Parse arguments"""
    parser = argparse.ArgumentParser(
                description='Script to check gap b/w timer frequency and callback function wake-up frequency')
    parser.add_argument('trace_data', nargs=1, type=str)
    parser.add_argument('--package_list_json', type=str, default='')
    parser.add_argument('-s', '--start_point', type=float, default=0.0,
                        help='Start point[sec] to load trace data')
    parser.add_argument('-d', '--duration', type=float, default=0.0,
                        help='Duration[sec] to load trace data')
    parser.add_argument('-r', '--gap_threshold_ratio', type=float, default=0.2,
                        help='Warning when callback_freq is less than "gap_threshold_ratio" * timer_period for "count_threshold" times')
    parser.add_argument('-n', '--count_threshold', type=int, default=10,
                        help='Warning when callback_freq is less than "gap_threshold_ratio" * timer_period for "count_threshold" times')
    parser.add_argument('-v', '--verbose', action='store_true', default=False)
    parser.add_argument('-f', '--force', action='store_true', default=False,
                        help='Overwrite report directory')
    args = parser.parse_args()
    return args


def main():
    """Main function"""
    args = parse_arg()

    global _logger
    if args.verbose:
        _logger = utils.create_logger(__name__, logging.DEBUG)
    else:
        _logger = utils.create_logger(__name__, logging.INFO)

    _logger.debug(f'trace_data: {args.trace_data[0]}')
    _logger.debug(f'package_list_json: {args.package_list_json}')
    _logger.debug(f'start_point: {args.start_point}, duration: {args.duration}')
    dest_dir = f'report_{Path(args.trace_data[0]).stem}/check_callback_timer'
    _logger.debug(f'dest_dir: {dest_dir}')
    _logger.debug(f'gap_threshold_ratio: {args.gap_threshold_ratio}')
    _logger.debug(f'count_threshold: {args.count_threshold}')

    analyze(args, dest_dir)
    _logger.info('<<< OK. All nodes are analyzed >>>')


if __name__ == '__main__':
    main()
