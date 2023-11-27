#!/usr/bin/env python3

import Utils

import json

import pm4py
from pm4py.objects.log.log import Trace, EventLog, EventStream
from pm4py.algo.filtering.log.attributes import attributes_filter
from pm4py.algo.filtering.log.timestamp import timestamp_filter
from pm4py.objects.conversion.log import converter as log_converter


def filter_events_by_common_achievements(event_log, game):
    """
    Filter log by keeping only achievements that are the most common (max 20)

    Parameters
    -----------
    event_log
        Event log to be filtered
    game
        The game whose achievements are saved in the log

    Returns
    -----------
    filtered_log
        Filtered log
    """
    with open(f'Logs/{game.name}_common_achievements.json', 'r') as file:
        common_achievements = json.load(file)

        parameters = {attributes_filter.Parameters.ATTRIBUTE_KEY: 'concept:name'}

        filtered_log = attributes_filter.apply_events(event_log, common_achievements,
                                                      parameters)

    return filtered_log


def filter_players_by_game_completion(event_log, game, finished):
    """
    Filter log by keeping only traces of players that did / did not finish the game

    Parameters
    -----------
    event_log
        Trace log
    game
        Game whose achievements are saved in the log
    finished
        Bool value indicating whether to keep players that finished the game or vice versa

    Returns
    -----------
    filtered_log
        Filtered log
    """
    filtered_log = attributes_filter.apply(event_log, [game.end_achievement],
                                           {attributes_filter.Parameters.POSITIVE: finished,
                                            attributes_filter.Parameters.ATTRIBUTE_KEY: 'concept:name'})

    return filtered_log


def filter_achievements_by_first_playthrough(event_log, game):
    """
    Filter log by keeping only achievements that players unlocked before finishing the game

    Parameters
    -----------
    event_log
        Event log to be filtered; needs to contain only players who finished the game
        (traces that contain the 'endgame' achievement)
    game
        The game whose achievements are saved in the log

    Returns
    -----------
    filtered_log
        Filtered log
    """
    end_timestamps = {}

    stream = log_converter.apply(event_log, variant=log_converter.TO_EVENT_STREAM)

    for trace in stream:
        if trace['concept:name'] == game.end_achievement:
            end_timestamps[trace['case:concept:name']] = trace['time:timestamp']

    stream = EventStream(list(filter(lambda x: x['time:timestamp'].to_pydatetime()
                                               <= end_timestamps[x['case:concept:name']], stream)),
                         attributes=event_log.attributes,
                         extensions=event_log.extensions,
                         classifiers=event_log.classifiers,
                         omni_present=event_log.omni_present)

    filtered_log = log_converter.apply(stream)

    return filtered_log


def filter_main_achievements(event_log, game):
    """
    Filter log by keeping only the main achievements that mark passing of a level
    in the game

    Parameters
    -----------
    event_log
        Event log to be filtered
    game
        The game whose achievements are saved in the log

    Returns
    -----------
    filtered_log
        Filtered log
    """
    filtered_log = attributes_filter.apply_events(event_log, game.main_achievements,
                                                  {attributes_filter.Parameters.ATTRIBUTE_KEY: 'concept:name',
                                                   attributes_filter.Parameters.POSITIVE: True})

    return filtered_log


def filter_players_by_reviews(event_log, game, keep_positive):
    """
    Filter log by deleting players that wrote positive/negative review of the game

    Parameters
    -----------
    event_log
        Event log to be filtered
    game
        The game whose achievements are saved in the log
    keep_positive
        Bool value indicating whether to keep positive or negative reviews

    Returns
    -----------
    filtered_log
        Filtered log
    """
    filtered_log = EventLog(list(), attributes=event_log.attributes,
                            extensions=event_log.extensions,
                            classifiers=event_log.classifiers,
                            omni_present=event_log.omni_present)

    with open(f'Logs/{game.name}_player_stats.json', 'r') as player_stats_file:
        player_stats = json.load(player_stats_file)

        for trace in event_log:
            case_id = trace.attributes['concept:name']
            if player_stats[case_id]['left_positive_review'] == keep_positive:
                new_trace = trace
                filtered_log.append(new_trace)

    return filtered_log


def filter_log_by_trace_fitness(event_log, replayed_traces):
    """
    Filter log by deleting traces that were found fit by
    token replay algorithm.

    Parameters
    -----------
    event_log
        Event log to be filtered
    replayed_traces
        The result of token replay algorithm

    Returns
    -----------
    filtered_log
        Filtered log
    """
    filtered_log = EventLog(list(), attributes=event_log.attributes,
                            extensions=event_log.extensions,
                            classifiers=event_log.classifiers,
                            omni_present=event_log.omni_present)

    for i in range(len(event_log)):
        if replayed_traces[i]['trace_is_fit']:
            new_trace = event_log[i]
            filtered_log.append(new_trace)

    return filtered_log


def filter_achievements_by_level(event_log, start_achievement, end_achievement):
    """
    Filter log by deleting achievements that were not unlocked after the start_achievement
    and before the end_achievement.

    Parameters
    -----------
    event_log
        Event log to be filtered
    start_achievement
        Starting achievement
    end_achievement
        Ending achievement

    Returns
    -----------
    filtered_log
        Filtered log
    """
    new_log = EventLog(list(), attributes=event_log.attributes,
                       extensions=event_log.extensions,
                       classifiers=event_log.classifiers,
                       omni_present=event_log.omni_present)

    for trace in event_log:
        new_trace = Trace()

        add = False
        for achievement in trace:
            if achievement['concept:name'] == start_achievement:
                add = True

            if add and achievement['concept:name'] in ['Terraformer IV','Off The Hook','We are immortal!',
                                                       'Doom Importer','Magnetic Personality', 'Terraformer V']:
                new_trace.append(achievement)

            if achievement['concept:name'] == end_achievement:
                break

        new_log.append(new_trace)

    df = pm4py.convert_to_dataframe(new_log)
    df.to_csv('Logs/level_log.csv')

    return new_log


def filter_achievements_by_date(event_log, start_date='2008-01-01 00:00:00'):
    """
    Filter log by deleting traces that contain achievements unlocked before
    a specified starting time.

    Parameters
    -----------
    event_log
        Event log to be filtered
    start_date
        The date before which an achievement cannot be unlocked,
        default is the year that Steam achievements were introduced in

    Returns
    -----------
    filtered_log
        Filtered log
    """
    first_possible_date = '1970-01-01 00:00:00'   # equivalent to unix timestamp 0

    parameters = {timestamp_filter.Parameters.TIMESTAMP_KEY: 'time:timestamp'}
    incorrect_log = timestamp_filter.filter_traces_intersecting(event_log,
                                                                first_possible_date,
                                                                start_date,
                                                                parameters=parameters)

    filtered_log = Utils.log_difference(event_log, incorrect_log)
    return filtered_log


def filter_incorrect_traces(event_log, game):
    """
    Filter log by deleting traces that defy normal game behaviour; e.g.,
    wrong order of main achievements or several main achievements having the same timestamp

    Parameters
    -----------
    event_log
        Event log to be filtered
    game
        The game whose achievements are saved in the log;
        must contain progress achievements

    Returns
    -----------
    filtered_log
        Filtered log
    """
    filtered_log = EventLog(list(), attributes=event_log.attributes,
                            extensions=event_log.extensions,
                            classifiers=event_log.classifiers,
                            omni_present=event_log.omni_present)

    for trace in event_log:
        discard_trace = False
        timestamps = set()

        count = 0
        for achievement in trace:
            if achievement['concept:name'] in game.main_achievements:
                name = achievement['concept:name']
                timestamp = achievement['time:timestamp']

                if name != game.main_achievements[count] or timestamp in timestamps:
                    discard_trace = True
                    break

                timestamps.add(timestamp)
                count += 1

        if not discard_trace:
            new_trace = trace
            filtered_log.append(new_trace)

    return filtered_log


def filter_cheating_players(event_log, keep_cheating=False):
    """
    Filter log by deleting traces that show players that cheated
    the achievement system; i.e., all achievements were
    unlocked at the same time

    Parameters
    -----------
    event_log
        Event log to be filtered
    keep_cheating
        Bool value indicating whether to keep cheating traces or not

    Returns
    -----------
    filtered_log
        Filtered log
    """
    filtered_log = EventLog(list(), attributes=event_log.attributes,
                            extensions=event_log.extensions,
                            classifiers=event_log.classifiers,
                            omni_present=event_log.omni_present)

    for trace in event_log:
        timestamps = set()

        for event in trace:
            timestamps.add(event['time:timestamp'])

        identical_timestamps = len(timestamps) == 1 and len(trace) != 1

        if identical_timestamps == keep_cheating:
            new_trace = trace
            filtered_log.append(new_trace)

    return filtered_log
