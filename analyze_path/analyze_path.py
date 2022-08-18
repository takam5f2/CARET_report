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
Script to analyze path
"""
from __future__ import annotations
import sys
import os
import pathlib
import argparse
import logging
import yaml
import numpy as np
import pandas as pd
from bokeh.plotting import Figure, figure
from caret_analyze.runtime.path import Path
from caret_analyze import Architecture, Application
from caret_analyze.experiment import ResponseTime
from caret_analyze.plot import message_flow
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/..')
from common import utils

_logger: logging.Logger = None


def align_timeseries(timeseries: tuple[np.ndarray, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    """Adjust timeseries graph"""
    x_list = np.zeros(len(timeseries[0]), dtype='float')
    y_list = np.zeros(len(timeseries[1]), dtype='float')
    offset = timeseries[0][0]
    for i in range(len(timeseries[0])):
        x_list[i] = (timeseries[0][i] - offset) * 10**-9 # [sec]
        y_list[i] = timeseries[1][i] * 10**-6  # [msec]
    return x_list, y_list


def draw_response_time(hist: np.ndarray, bin_edges: np.ndarray,
                       timeseries: tuple[np.ndarray, np.ndarray]) -> tuple[Figure, Figure]:
    """Draw histogram and timeseries graphs of resopnse time"""
    bin_edges = bin_edges * 10**-6 # nanoseconds to milliseconds
    p_hist = figure(plot_width=600, plot_height=400, active_scroll='wheel_zoom',
                    x_axis_label='Response Time [ms]', y_axis_label='Frequency')
    p_hist.quad(top=hist, bottom=0, left=bin_edges[:-1], right=bin_edges[1:],
                line_color='white', alpha=0.5)

    p_timeseries = None
    if timeseries:
        p_timeseries = figure(plot_width=600, plot_height=400, active_scroll='wheel_zoom',
                       x_axis_label='Time [sec]', y_axis_label='Response Time [ms]')
        p_timeseries.y_range.start = 0
        p_timeseries.line(x=timeseries[0], y=timeseries[1])

    return p_hist, p_timeseries


def get_messageflow_durationtime(target_path: Path):
    """Get duration time [sec] of message flow"""
    dataframe = target_path.to_dataframe()
    duration = (dataframe.max()[-1] - dataframe.min()[0]) / 1e9
    if pd.isna(duration):
        return None
    return duration


def analyze_path(dest_dir: str, arch: Architecture, app: Application, target_path_name: str):
    """Analyze a path"""
    _logger.info(f'Processing: {target_path_name}')
    target_path = app.get_path(target_path_name)

    _logger.info('  Call message_flow')
    graph = message_flow(target_path, granularity='node',
                         treat_drop_as_delay=False, export_path='dummy.html')
    duration = get_messageflow_durationtime(target_path)
    if duration is None:
        _logger.warning(f'  Some parts are not running in the path: {target_path_name}')
        utils.export_graph(graph, dest_dir, f'{target_path_name}_messageflow', target_path_name)
        return None
    graph_short = message_flow(target_path, granularity='node', treat_drop_as_delay=False,
                lstrip_s=duration / 2,
                rstrip_s=duration / 2 - (3 + 0.1),
                export_path='dummy.html')
    graph.width = graph_short.width = 1400
    graph.height = graph_short.height = 800
    utils.export_graph(graph, dest_dir, f'{target_path_name}_messageflow', target_path_name)
    utils.export_graph(graph_short, dest_dir, f'{target_path_name}_messageflow_short', target_path_name)

    _logger.info('  Call ResponseTime')
    records = target_path.to_records()
    response_time = ResponseTime(records)

    _logger.debug('    Draw histogram (total)')
    hist, bin_edges = response_time.to_histogram(10**7) # binsize = 10ms
    p_hist, _ = draw_response_time(hist, bin_edges, None)
    utils.export_graph(p_hist, dest_dir, target_path_name + '_hist', target_path_name)
    sumval = 0
    for i in range(len(bin_edges) - 1):
        val = (bin_edges[i] + bin_edges[i+1]) / 2
        sumval += hist[i] * val
    total_avg = sumval / np.sum(hist)

    _logger.debug('    Draw histogram and timeseries (best)')
    hist, bin_edges = response_time.to_best_case_histogram(10**7) # binsize = 10ms
    timeseries = response_time.to_best_case_timeseries()
    timeseries = align_timeseries(timeseries)
    p_hist, p_timeseries = draw_response_time(hist, bin_edges, timeseries)
    utils.export_graph(p_hist, dest_dir, target_path_name + '_hist_best', target_path_name)
    utils.export_graph(p_timeseries, dest_dir, target_path_name + '_timeseries_best', target_path_name)
    best_avg = np.average(timeseries[1])
    best_min = np.min(timeseries[1])
    best_max = np.max(timeseries[1])

    _logger.debug('    Draw histogram and timeseries (worst)')
    hist, bin_edges = response_time.to_worst_case_histogram(10**7) # binsize = 10ms
    timeseries = response_time.to_worst_case_timeseries()
    timeseries = align_timeseries(timeseries)
    p_hist, p_timeseries = draw_response_time(hist, bin_edges, timeseries)
    utils.export_graph(p_hist, dest_dir, target_path_name + '_hist_worst', target_path_name)
    utils.export_graph(p_timeseries, dest_dir, target_path_name + '_timeseries_worst', target_path_name)
    worst_avg = np.average(timeseries[1])
    worst_min = np.min(timeseries[1])
    worst_max = np.max(timeseries[1])

    total_min = best_min
    total_max = worst_max

    _logger.info(f'---{target_path_name}---')
    _logger.info(f'worst_avg = {worst_avg}')
    _logger.info(f'worst_min = {worst_min}')
    _logger.info(f'worst_max = {worst_max}')
    _logger.info(f'best_avg = {best_avg}')
    _logger.info(f'best_min = {best_min}')
    _logger.info(f'best_max = {best_max}')
    _logger.info(f'total_avg = {total_avg}')
    _logger.info(f'total_min = {total_min}')
    _logger.info(f'total_max = {total_max}')

    stats = {
        'target_path_name': target_path_name,
        'node_names': arch.get_path(target_path_name).node_names,
        'worst_avg': float(worst_avg),
        'worst_min': float(worst_min),
        'worst_max': float(worst_max),
        'best_avg': float(best_avg),
        'best_min': float(best_min),
        'best_max': float(best_max),
        'total_avg': float(worst_avg),
        'total_min': float(total_min),
        'total_max': float(total_max),
        'filename_messageflow': f'{target_path_name}_messageflow',
        'filename_messageflow_short': f'{target_path_name}_messageflow_short',
        'filename_hist_total': f'{target_path_name}_hist',
        'filename_hist_best': f'{target_path_name}_hist_best',
        'filename_timeseries_best': f'{target_path_name}_timeseries_best',
        'filename_hist_worst': f'{target_path_name}_hist_worst',
        'filename_timeseries_worst': f'{target_path_name}_timeseries_worst'
    }
    return stats


def analyze(args, dest_dir):
    """Analyze all paths"""
    utils.make_destination_dir(dest_dir, args.force, _logger)
    lttng = utils.read_trace_data(args.trace_data[0], args.start_point, args.duration, False)
    arch = Architecture('yaml', args.architecture_file)
    app = Application(arch, lttng)

    stats_list = []

    # Verify each path
    for target_path_name in arch.path_names:
        path = arch.get_path(target_path_name)
        ret_verify = path.verify()
        _logger.info(f'path.verify {target_path_name}: {ret_verify}')
        if not ret_verify:
            sys.exit(-1)

    # Analyze each path
    for target_path_name in arch.path_names:
        stats = analyze_path(dest_dir, arch, app, target_path_name)
        if stats:
            stats_list.append(stats)

    # Save stats file
    stat_file_path = f'{dest_dir}/stats_path.yaml'
    with open(stat_file_path, 'w', encoding='utf-8') as f_yaml:
        yaml.safe_dump(stats_list, f_yaml, encoding='utf-8', allow_unicode=True, sort_keys=False)


def parse_arg():
    """Parse arguments"""
    parser = argparse.ArgumentParser(
                description='Script to analyze path')
    parser.add_argument('trace_data', nargs=1, type=str)
    parser.add_argument('architecture_file', nargs='?', type=str, default='architecture_path.yaml')
    parser.add_argument('-s', '--start_point', type=float, default=0.0,
                        help='Start point[sec] to load trace data')
    parser.add_argument('-d', '--duration', type=float, default=0.0,
                        help='Duration[sec] to load trace data')
    parser.add_argument('-f', '--force', action='store_true', default=False,
                        help='Overwrite report directory')
    parser.add_argument('-v', '--verbose', action='store_true', default=False)
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
    _logger.debug(f'architecture_file: {args.architecture_file}')
    _logger.debug(f'start_point: {args.start_point}, duration: {args.duration}')
    dest_dir = f'report_{pathlib.Path(args.trace_data[0]).stem}/path'
    _logger.debug(f'dest_dir: {dest_dir}')

    analyze(args, dest_dir)
    _logger.info('<<< OK. All target paths are analyzed >>>')


if __name__ == '__main__':
    main()
