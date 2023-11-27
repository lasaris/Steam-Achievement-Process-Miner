#!/usr/bin/env python3

from Utils import *

from pm4py.algo.filtering.log.attributes import attributes_filter

from pm4py.algo.discovery.heuristics import algorithm as heuristics_miner
from pm4py.algo.discovery.heuristics.parameters import Parameters as hm_parameters

from pm4py.objects.conversion.heuristics_net import converter as hn_converter

from pm4py.algo.discovery.dfg import algorithm as dfg_discovery
from pm4py.visualization.dfg import visualizer as dfg_visualization
from pm4py.algo.discovery.dfg.parameters import Parameters as dfg_parameters

from pm4py.algo.conformance.tokenreplay import algorithm as token_replay
from pm4py.algo.conformance.tokenreplay.variants.token_replay import Parameters as tr_parameters

from pm4py.algo.conformance.alignments import algorithm as alignments
from pm4py.evaluation.replay_fitness import evaluator as replay_fitness_evaluator


def process_discovery(event_log, dependency_thresh=0.96,
                      cleaning_thresh=0.5, min_act_divisor=3):
    """
    Discovers a Heuristic net from the event log, with given parameters

    Parameters
    -----------
    event_log
        Event log
    dependency_thresh
        Dependency threshold of Heuristic miner
    cleaning_thresh
        Cleaning threshold of Heuristic miner
    min_act_divisor
        Divisor of event log length; the result is used as minimum activity percentage

    Returns
    -----------
    heu_net
        The discovered Heuristic net
    """
    parameters = {hm_parameters.DEPENDENCY_THRESH: dependency_thresh,
                  hm_parameters.DFG_PRE_CLEANING_NOISE_THRESH: cleaning_thresh,
                  hm_parameters.MIN_ACT_COUNT: len(event_log) / min_act_divisor}
    heu_net = heuristics_miner.apply_heu(event_log, parameters=parameters)

    return heu_net


def conformance_checking(event_log, heu_net):
    """
     Runs token replay on the Heuristic net and return the list of replayed traces

    Parameters
    -----------
    event_log
        Event log
    heu_net
        Heuristic net discovered from the event log

    Returns
    -----------
    replayed_traces
        A list of traces with information about whether they are fit or not
    """
    net, initial_marking, final_marking = hn_converter.apply(heu_net)

    parameters = {tr_parameters.CONSIDER_REMAINING_IN_FITNESS: False}
    replayed_traces = token_replay.apply(event_log, net, initial_marking, final_marking,
                                         parameters=parameters)

    return replayed_traces


def discover_model_and_save(event_log, game, output_name):
    """
    Discovers a Heuristic net from the event log and saves it to a file

    Parameters
    -----------
    event_log
        Event log
    game
        Game whose achievements are in the event log
    output_name
        The last part of the ouput file name

    Returns
    -----------
    fitness
        Fitness of the discovered Heuristic net
    """
    heu_net = process_discovery(event_log)
    save_heuristic_net(heu_net, game, output_name)

    fitness = check_fitness_token_replay(event_log, heu_net)
    return fitness


def check_fitness_token_replay(event_log, heu_net):
    """
    Uses token replay to compute event log fitness

    Parameters
    -----------
    event_log
        Event log
    heu_net
        Heuristic net discovered from the event log

    Returns
    -----------
    log_fitness
        The computed fitness
    """
    net, im, fm = hn_converter.apply(heu_net)

    fitness = replay_fitness_evaluator.apply(event_log, net, im, fm,
                                             variant=replay_fitness_evaluator.Variants.TOKEN_BASED)

    log_fitness = fitness['log_fitness']
    return log_fitness


def check_fitness_alignments(heu_net, event_log):
    """
    Uses alignments to compute event log fitness

    Parameters
    -----------
    event_log
        Event log
    heu_net
        Heuristic net discovered from the event log

    Returns
    -----------
    fitness
        a dictionary of fitness values
    """
    net, im, fm = hn_converter.apply(heu_net)

    aligned_traces = alignments.apply_log(event_log, net, im, fm)

    fitness = replay_fitness_evaluator.evaluate(aligned_traces,
                                                variant=replay_fitness_evaluator.Variants.ALIGNMENT_BASED)
    return fitness


def find_bottlenecks(event_log, game, output_name):
    """
    Creates a directly-follows-graph with performance information on the edges (the
    aggregate function used is median|, with the resulting graph saved to a file

    Parameters
    -----------
    event_log
        Event log to be divided
    game
        The game whose achievements are saved in the log
    output_name
        The last part of the output file name
    """
    params = {dfg_parameters.AGGREGATION_MEASURE: 'median'}
    dfg = dfg_discovery.apply(event_log, params, variant=dfg_discovery.Variants.PERFORMANCE)

    parameters = {dfg_visualization.Variants.PERFORMANCE.value.Parameters.FORMAT: "svg"}
    gviz = dfg_visualization.apply(dfg, log=event_log, variant=dfg_visualization.Variants.PERFORMANCE,
                                   parameters=parameters)
    dfg_visualization.save(gviz, f'Outputs/{game.name}_performance_{output_name}.svg')
    dfg_visualization.view(gviz)


def divide_unfinished_players_by_levels(event_log, game):
    """
    Divides players that did not finish the game by the last level they reached and assign the
    corresponding player reviews to levels. The output is saved to a json file.

    Parameters
    -----------
    event_log
        Event log to be divided
    game
        The game whose achievements are saved in the log
    """
    filtered_log = filter_players_by_game_completion(event_log, game, False)

    filtered_log = attributes_filter.apply(filtered_log, game.main_achievements)
    unfinished_log_length = len(filtered_log)

    players_level_endings = {}

    with open(f'Logs/{game.name}_player_stats.json', 'r') as review_file:
        reviews = json.load(review_file)

        for i in range(len(game.main_achievements) - 1):
            level_log = attributes_filter.apply(filtered_log, [game.main_achievements[i + 1]],
                                                {attributes_filter.Parameters.ATTRIBUTE_KEY: 'concept:name',
                                                 attributes_filter.Parameters.POSITIVE: False})

            level_case_ids = get_case_ids(level_log)

            level_reviews = list(map(lambda r: r[1], filter(lambda r: r[0] in level_case_ids,
                                                            reviews.items())))

            review_recommendations = list(map(lambda r: r[1]['left_positive_review'],
                                              filter(lambda r: r[0] in level_case_ids,
                                                     reviews.items())))
            neg_review_percent = 0
            if len(review_recommendations) > 0:
                neg_review_percent = len(list(filter(lambda r: not r, review_recommendations))) /\
                                     len(review_recommendations) * 100

            level_info = {'level_num_players': len(level_log),
                          'total_num_players': unfinished_log_length,
                          'negative_reviews_percentage': round(neg_review_percent, 2),
                          'reviews': level_reviews}

            players_level_endings[game.main_achievements[i]] = level_info

            filtered_log = log_difference(filtered_log, level_log)

    with open(f'Outputs/{game.name}_unfinished_divided_by_levels.json', 'w') as output_file:
        json.dump(players_level_endings, output_file, indent=1)


def compare_replayed_log_and_incorrect_log(event_log, heu_net, game):
    """
    Uses token replay to discover unfit traces, and manual filters to discover
    incorrect and cheating traces. Prints out the number of individual traces
    and the overlap between the traces.

    Parameters
    -----------
    event_log
        Event log
    heu_net
        Heuristic net discovered from the event log
    game
        Game whose achievements are saved in the event log
    """
    replayed_traces = conformance_checking(event_log, heu_net)

    fit_log = filter_log_by_trace_fitness(event_log, replayed_traces)
    correct_log = filter_incorrect_traces(event_log, game)
    no_cheater_log = filter_cheating_players(event_log)

    print(f'{game.name} :')
    print(f'Fit log: {len(fit_log)} / {len(event_log)}')
    print(f'Correct log: {len(correct_log)} / {len(event_log)}')
    print(f'No cheater log: {len(no_cheater_log)} / {len(event_log)}')

    incorrect_ids = get_case_ids(log_difference(event_log, correct_log))
    unfit_ids = get_case_ids(log_difference(event_log, fit_log))
    cheater_ids = get_case_ids(log_difference(event_log, no_cheater_log))

    not_in_unfit_count = len(list(filter(lambda case_id: case_id not in unfit_ids, incorrect_ids)))
    not_in_incorrect_count = len(list(filter(lambda case_id: case_id not in incorrect_ids, unfit_ids)))
    not_in_unfit_count_cheater = len(list(filter(lambda case_id: case_id not in unfit_ids, cheater_ids)))

    print(f'Traces in unfit and not in bug log: {not_in_incorrect_count} / {len(unfit_ids)}')
    print(f'Traces in incorrect and not in unfit log: {not_in_unfit_count} / {len(incorrect_ids)}')
    print(f'Traces in cheater and not in unfit log: {not_in_unfit_count_cheater} / {len(cheater_ids)}\n')


def typical_playthrough():
    """
    Discovers Heuristic nets of all games to discover typical game playthrough;
    saves fitness records of all games into a json file
    """
    log_fitness_records = {}

    for game in Game:
        log = import_csv(game)
        if game.main_achievements:
            log = filter_incorrect_traces(log, game)

        fitness = discover_model_and_save(log, game, 'typical_playthrough')
        log_fitness_records[game.name] = fitness

    with open(f'Outputs/typical_playthrough_fitness_records.json', 'w') as file:
        json.dump(log_fitness_records, file)


def comparison_of_all_games():
    """
    Discovers Heuristic nets of all games when filtered by positive/negative reviews,
    and finished/unfinished players if the game has an end achievement; saves the
    fitness records of all nets into a json file
    """
    log_fitness_records = {}

    for game in Game:
        log = import_csv(game)
        if game.main_achievements:
            log = filter_incorrect_traces(log, game)

        positive_log = filter_players_by_reviews(log, game, True)
        negative_log = filter_players_by_reviews(log, game, False)

        fitness_positive = discover_model_and_save(positive_log, game, 'positive')
        fitness_negative = discover_model_and_save(negative_log, game, 'negative')

        fitness_finished = 0
        fitness_unfinished = 0

        if game.end_achievement:
            finished_log = filter_players_by_game_completion(log, game, True)
            finished_log = filter_achievements_by_first_playthrough(finished_log, game)
            unfinished_log = filter_players_by_game_completion(log, game, False)

            fitness_finished = discover_model_and_save(finished_log, game, 'finished')
            fitness_unfinished = discover_model_and_save(unfinished_log, game, 'unfinished')

        log_fitness_records[game.name] = {'positive_fitness': fitness_positive,
                                          'negative_fitness': fitness_negative,
                                          'finished_fitness': fitness_finished,
                                          'unfinished_fitness': fitness_unfinished}

    with open(f'Outputs/fitness_records_for_comparison.json', 'w') as file:
        json.dump(log_fitness_records, file)


def bottleneck_analysis():
    """
    For selected games, logs are filtered to contain only main (progress) achievements
    and performance models are discovered for all of them and saved; the division of
    players who quit the game along with their reviews is also saved into a json file
    """
    for game in [Game.GRIS, Game.HADES, Game.BLACK_MIRROR, Game.PER_ASPERA]:
        log = import_csv(game)

        if game == Game.PER_ASPERA:
            new_log = filter_achievements_by_level(log, Game.PER_ASPERA.main_achievements[3],
                                                   Game.PER_ASPERA.main_achievements[4])
            new_log = variants_filter.filter_log_variants_percentage(new_log, 0.8)
            find_bottlenecks(new_log, Game.PER_ASPERA, 'one_level_bottleneck')

        log = filter_incorrect_traces(log, game)
        log = filter_main_achievements(log, game)

        divide_unfinished_players_by_levels(log, game)
        find_bottlenecks(log, game, 'level_bottlenecks')


def noise_detection(game):
    """
     For selected game, the method compares unfit, incorrect and cheating traces.
     """
    log = import_csv(game)
    heu_net = process_discovery(log, 0.99, 0.05, len(log))
    compare_replayed_log_and_incorrect_log(log, heu_net, game)


if __name__ == '__main__':
    typical_playthrough()
    comparison_of_all_games()
    bottleneck_analysis()
    save_all_cheater_statistics()
    noise_detection(Game.HADES)