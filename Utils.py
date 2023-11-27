#!/usr/bin/env python3

from Filters import *
from Models.Game import Game

import json
import pandas
import pm4py

import pm4py.util.parameters
from pm4py.objects.conversion.log import converter as log_converter
from pm4py.objects.log.log import EventLog

from pm4py.algo.discovery.dfg import algorithm as dfg_discovery
from pm4py.visualization.dfg import visualizer as dfg_visualization
from pm4py.algo.filtering.log.variants import variants_filter

from pm4py.visualization.heuristics_net import visualizer as hn_visualizer


def import_csv(game):
    """
    Imports game achievement log

    Parameters
    -----------
    game
        The game whose log is to be imported

    Returns
    -----------
    event_log
        Imported event log
    """
    dataframe = pandas.read_csv(f'Logs/{game.name}_achievement_logs.csv', sep=',')
    dataframe = pm4py.format_dataframe(dataframe,
                                       case_id='CaseId',
                                       activity_key='Activity',
                                       timestamp_key='Timestamp',
                                       timest_format='%Y-%m-%d %H:%M:%S')

    dataframe = dataframe.sort_values('time:timestamp')
    event_log = pm4py.convert_to_event_log(dataframe)

    return event_log


def get_case_ids(event_log):
    """
    Extracts only case ids from the event log

    Parameters
    -----------
    event_log
        Event log from which case ids will be extracted

    Returns
    -----------
    case_ids
        a set of case ids
    """
    stream = log_converter.apply(event_log, variant=log_converter.TO_EVENT_STREAM)

    case_ids = set(map(lambda trace: trace['case:concept:name'], stream))

    return case_ids


def log_difference(log_a, log_b):
    """
    Computes a difference between two logs, by keeping only traces that are in log_a and
    not in log_b

    Parameters
    -----------
    log_a
        First event log
    log_b
        Second event log

    Returns
    -----------
    filtered_log
        Returns the filtered log
    """
    filtered_log = EventLog(list(), attributes=log_a.attributes, extensions=log_a.extensions,
                            classifiers=log_a.classifiers, omni_present=log_a.omni_present)
    for trace in log_a:
        if trace not in log_b:
            filtered_log.append(trace)
    return filtered_log


def find_average_playtime(game):
    """
    Loads the player stats file for the game and computes the average playtime among
    the players

    Parameters
    -----------
    game
        The game whose average playtime will be computed

    Returns
    -----------
    avg_playtime
        Average playtime
    """
    with open(f'Logs/{game.name}_player_stats.json', 'r') as stats_file:
        player_stats = json.load(stats_file)

        avg_playtime = sum([stats['playtime'] for stats in player_stats.values()]) / len(player_stats)
        return avg_playtime


def save_dfg(event_log, name, factor=1):
    """
    Saves the visualization of directly-follows graph of an event log

    Parameters
    -----------
    event_log
        Event log to be discovered, visualized and saved
    name : str
        Name of the graph to be saved
    factor
        Percentage of variants to keep
    """
    common_log = variants_filter.filter_log_variants_percentage(event_log, factor)

    dfg = dfg_discovery.apply(common_log)

    parameters = {dfg_visualization.Variants.PERFORMANCE.value.Parameters.FORMAT: 'svg'}
    gviz = dfg_visualization.apply(dfg, log=event_log, variant=dfg_visualization.Variants.FREQUENCY,
                                   parameters=parameters)
    dfg_visualization.view(gviz)

    dfg_visualization.save(gviz, f'Outputs/{name}_dfg.svg')


def save_heuristic_net(heu_net, game, output_name):
    """
    Saves the visualization of Heuristic net

    Parameters
    -----------
    heu_net
        Event log to be discovered, visualized and saved
    game
        Game whose achievements are in the event log
    """
    parameters = {hn_visualizer.Variants.PYDOTPLUS.value.Parameters.FORMAT: 'svg'}
    gviz = hn_visualizer.apply(heu_net, parameters=parameters)

    hn_visualizer.view(gviz)

    hn_visualizer.save(gviz, f'Outputs/{game.name}_hn_{output_name}.svg')


def view_dfg(event_log):
    """
    View a directly-follows-graph of the event log

    Parameters
    -----------
    event_log
        The event log to create dfg of
    """
    dfg = dfg_discovery.apply(event_log)
    gviz = dfg_visualization.apply(dfg, log=event_log)
    dfg_visualization.view(gviz)


def save_all_cheater_statistics():
    """
    Computes and saves cheating statistics and specific players for all saved games
    in a json file
    """
    cheaters = {}

    for game in Game:
        event_log = import_csv(game)
        cheater_log = filter_cheating_players(event_log, True)

        percentage = len(cheater_log) / len(event_log)

        cheaters[game.name] = {'percentage': f'{round(percentage, 3)}%',
                               'cheaters': list(get_case_ids(cheater_log))}

    with open(f'Outputs/cheater_statistics.json', 'w') as cheater_file:
        json.dump(cheaters, cheater_file, indent=0)
