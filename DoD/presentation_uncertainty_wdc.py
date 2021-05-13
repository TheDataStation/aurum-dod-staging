from presentation_utils import *
from DoD import view_4c_analysis_baseline as v4c
from DoD import material_view_analysis as mva
from DoD.colors import Colors
from tqdm import tqdm
import random
from enum import Enum
import glob
import pandas as pd
import pprint
import numpy as np
from collections import defaultdict, namedtuple
from tabulate import tabulate
from pathlib import Path
import time

if __name__ == '__main__':

    root_dir = "/home/cc/experiments_wdc_5_9/"
    # root_dir = "./experiments_wdc_10000_2/"
    for query in range(5):
        query_dir = root_dir + "wdc_gt" + str(query) + "/"
        for noise in ["zero_noise", "mid_noise", "high_noise"]:
            noise_dir = query_dir + noise + "/"
            sample_dir = noise_dir + "sample0/"
            for pipeline in range(1, 4):

                #################################CONFIG#####################################

                dir_path = sample_dir + "result" + str(pipeline) + "/"
                print("\n\n")
                print("Running in dir: ", dir_path)

                # top percentile of view scores to include in window
                top_percentile = 25
                # top_percentiles = [25]
                # max size of candidate (composite) key
                candidate_key_size = 2
                # sampling 5 contradictory or complementary rows from each view to include in the presentation
                sample_sizes = [1, 5, 10]

                mode = Mode.optimal

                max_num_interactions = 100

                num_runs = 50

                initialize_scores = ["zero", "s4"]
                fact_bank_fractions = [10, 50, 100]
                # fact_bank_fraction = 1

                result_dir = dir_path.replace(root_dir, "/home/cc/zhiru/presentation_results_wdc_5_12_no_decrement/")
                # result_dir = dir_path.replace(root_dir, "./test_dir/")
                Path(result_dir).mkdir(parents=True, exist_ok=True)

                # initialize_score = "s4"
                # if pipeline == 1 or pipeline == 2:
                #     initialize_score = "s4"
                # print("Initialize score with ", initialize_score)

                ################################LOG FILE###################################

                log_path = dir_path + "log.txt"
                log_file = open(log_path, "r")
                lines = log_file.readlines()

                dod_score = {}
                s4_score = {}
                cur_view = None
                # cur_s4_score = None
                # cur_dod_score = None
                ground_truth_view = None
                time_before_view_pre = None
                for line in lines:
                    if line.startswith("view"):
                        cur_view = dir_path + line[:-1].replace("view", "view_") + ".csv"
                    if line.startswith("s4_score"):
                        if pipeline == 3:
                            lst = line.split(sep=", ")
                            cur_s4_score = float(lst[0].split(sep=": ")[1])
                            s4_score[cur_view] = cur_s4_score
                            cur_dod_score = float(lst[1].split(sep=": ")[1])
                            dod_score[cur_view] = cur_dod_score
                        else:
                            cur_s4_score = float(line.split(sep=": ")[1])
                            s4_score[cur_view] = cur_s4_score
                    if line.startswith("ground truth view"):
                        ground_truth_view = line.split(sep=": ")[1][:-1]
                        ground_truth_view = ground_truth_view.replace("view", "view_")

                    if line.startswith("total_time"):
                        time_before_view_pre = float(line.split(sep=": ")[1])
                log_file.close()

                ground_truth_path = dir_path + ground_truth_view

                #####################################4C#####################################

                start_time_4c = time.time()

                # Run 4C
                print(
                    Colors.CBOLD + "--------------------------------------------------------------------------" + Colors.CEND)
                print("Running 4C...")

                original_view_files = glob.glob(dir_path + "/view_*")
                if len(original_view_files) > len(s4_score):
                    for i in range(len(s4_score), len(original_view_files)):
                        view_to_remove = Path(dir_path + "view_" + str(i) + ".csv")
                        view_to_remove.unlink()
                original_view_files = glob.glob(dir_path + "/view_*")

                compatible_groups, contained_groups, complementary_groups, contradictory_groups, all_pair_contr_compl = \
                    v4c.main(dir_path, candidate_key_size)

                print()
                print(
                    Colors.CBOLD + "--------------------------------------------------------------------------" + Colors.CEND)

                print("Number of views: ", len(original_view_files))

                view_files = prune_compatible_views(original_view_files, compatible_groups)
                print("After pruning compatible views: ", len(view_files))
                num_views_after_prune_compatible = len(view_files)

                view_files = prune_contained_views(view_files, contained_groups)
                print("After pruning contained views: ", len(view_files))

                time_4c = time.time() - start_time_4c
                file_4c = open(result_dir + "log.txt", "w")
                file_4c.write("Total time before view presentation:" + str(time_before_view_pre) + "\n")
                file_4c.write("4c time(s):" + str(time_4c) + "\n")
                file_4c.write("original num of views:" + str(len(original_view_files)) + "\n")
                file_4c.write("After pruning compatible views:" + str(num_views_after_prune_compatible) + "\n")
                file_4c.write("After pruning contained views:" + str(len(view_files)) + "\n")
                file_4c.close()

                ############################################################################

                if ground_truth_path not in view_files:
                    for compatible_group in compatible_groups:
                        if ground_truth_path in compatible_group:
                            ground_truth_path = compatible_group[0]
                            break
                    for contained_group in contained_groups:
                        if ground_truth_path in contained_group:
                            max_size = 0
                            largest_view = contained_group[0]
                            for view in contained_group:
                                if len(view) > max_size:
                                    max_size = len(view)
                                    largest_view = view
                            ground_truth_path = largest_view
                            break

                fact_bank_df = None
                if mode == Mode.optimal:
                    print("Ground truth view: " + ground_truth_path)
                    fact_bank_df = pd.read_csv(ground_truth_path, encoding='latin1', thousands=',')
                    fact_bank_df = mva.curate_view_not_dropna(fact_bank_df)
                    fact_bank_df = v4c.normalize(fact_bank_df)

                for fact_bank_fraction in fact_bank_fractions:

                    print("fact_bank_fraction = ", str(fact_bank_fraction))

                    # fact_bank_df = fact_bank_df.sample(frac=fact_bank_fraction / 100)

                    # result_by_top_percentile = []
                    # time_by_top_percentile = []

                    # cur_max_interactions = 0
                    for initialize_score in initialize_scores:

                        print("initialize_score = ", initialize_score)

                        for sample_size in sample_sizes:

                            print("sample_size = ", sample_size)

                            times = np.empty(num_runs)
                            ground_truth_rank = np.empty((num_runs, max_num_interactions), dtype=int)
                            for run in range(num_runs):

                                # create a new fact bank for every run
                                fact_bank_df = fact_bank_df.sample(frac=fact_bank_fraction / 100)

                                start_time_run = time.time()
                                print("Run " + str(run))

                                print(
                                    Colors.CBOLD + "--------------------------------------------------------------------------" +
                                    Colors.CEND)
                                print("Creating signals...")

                                signals, candidate_keys = create_signals_multi_row(view_files, all_pair_contr_compl,
                                                                                   sample_size)

                                # Initialize ranking model
                                key_rank = {}
                                random.shuffle(candidate_keys)
                                for key in candidate_keys:
                                    key_rank[key] = 0

                                view_scores = {}
                                if initialize_score == "dod":
                                    for path in view_files:
                                        view_scores[path] = dod_score[path]
                                elif initialize_score == "s4":
                                    for path in view_files:
                                        view_scores[path] = s4_score[path]
                                elif initialize_score == "zero":
                                    for path in view_files:
                                        view_scores[path] = 0

                                num_interactions = 0
                                # ground_truth_rank_per_run = np.empty(max_num_interactions, dtype=int)
                                while num_interactions < max_num_interactions:
                                    print(
                                        Colors.CBOLD + "--------------------------------------------------------------------------" +
                                        Colors.CEND)

                                    # pick top key from key_rank
                                    candidate_best_keys = [key for (key, value) in key_rank.items() if
                                                           value == max(key_rank.values())]
                                    best_key = None
                                    if len(candidate_best_keys) > 0:
                                        best_key = random.choice(candidate_best_keys)

                                    if initialize_score == "zero" and num_interactions == 0:
                                        # consider all views
                                        best_signal = pick_best_signal_to_present(signals, best_key, view_scores, 0)
                                    else:
                                        best_signal = pick_best_signal_to_present(signals, best_key, view_scores,
                                                                                  top_percentile)

                                    if best_signal == None:
                                        # we have explored all the signals
                                        break
                                    signal_type, signal, best_key = best_signal

                                    # present options
                                    options = []
                                    options_to_print = []
                                    headers = []
                                    if signal_type == "contradictions" or signal_type == "complements":

                                        # print("Key = ", list(best_key))
                                        row1_df, row2_df, views1, views2 = signal

                                        options = [[1, row1_df, views1], [2, row2_df, views2]]
                                        options_to_print = [[1, row1_df.to_string(index=False), views1],
                                                            [2, row2_df.to_string(index=False), views2]]
                                        headers = ["Option", "", "Views"]
                                        if signal_type == "contradictions":
                                            headers[1] = "Contradictory Row"
                                        else:
                                            headers[1] = "Complementary Row"

                                    elif signal_type == "singletons":
                                        for i, t in enumerate(signal, 1):
                                            view, sample_df = t
                                            options.append([i, sample_df, [view]])
                                            options_to_print.append([i, sample_df.to_string(index=False), [view]])

                                        headers = ["Option", "Sample rows", "View"]

                                    # print(tabulate(options_to_print, headers, tablefmt="grid"))

                                    # select option
                                    option_picked = 0
                                    valid_options = [0] + [option for option, df, views in options]

                                    if mode == Mode.optimal:

                                        max_intersection_with_fact_back = 0
                                        for option, df, views in options:
                                            column_intersections = df.columns.intersection(fact_bank_df.columns)
                                            # print(column_intersections)
                                            if len(column_intersections) == fact_bank_df.shape[1]:
                                                df_object = df[list(column_intersections)].astype('object')
                                                fact_bank_object = fact_bank_df[list(column_intersections)].astype(
                                                    'object')
                                                # default to intersection
                                                intersection = pd.merge(left=df_object,
                                                                        right=fact_bank_object,
                                                                        on=None)
                                                # print(intersection)
                                                intersection = intersection.drop_duplicates()
                                                # print(intersection)
                                                if intersection.size > max_intersection_with_fact_back:
                                                    # Always selection the option that's more consistent with the fact bank
                                                    # if there's no intersection, then skip this option (select 0)
                                                    option_picked = option
                                                    max_intersection_with_fact_back = intersection.size
                                                    # print(str(max_intersection_with_fact_back) + " " + str(option_picked))
                                        print(
                                            Colors.CGREYBG + "Select option (or 0 if no preferred option): " + Colors.CEND)
                                        print("Optimal option = " + str(option_picked))

                                    elif mode == Mode.random:
                                        option_picked = random.choice(valid_options)
                                        print(
                                            Colors.CGREYBG + "Select option (or 0 if no preferred option): " + Colors.CEND)
                                        print("Random option = " + str(option_picked))

                                    else:
                                        option_picked = input(
                                            Colors.CGREYBG + "Select option (or 0 if no preferred option): " + Colors.CEND)

                                        if option_picked == "":
                                            break

                                        while not (option_picked.isdigit() and int(option_picked) in valid_options):
                                            option_picked = input(
                                                Colors.CGREYBG + "Select option (or 0 if no preferred option): " + Colors.CEND)

                                        option_picked = int(option_picked)

                                    # update rank
                                    if option_picked != 0:
                                        option, df, views = options[option_picked - 1]
                                        for view in views:
                                            view_scores[view] += 1
                                        if signal_type == "contradictions" or signal_type == "complements":
                                            key_rank[best_key] += 1
                                    else:
                                        # didn't select any option, decrement key's score
                                        # (not using this strategy) move down the current key's rank to the bottom (to make sure other keys get chances of being presented)
                                        if signal_type == "contradictions" or signal_type == "complements":
                                            key_rank[best_key] -= 1
                                            # key_rank.append(key_rank.pop(key_rank.index(best_key)))
                                        # views_to_decrement = set()
                                        # for option, df, views in options:
                                        #     for view in views:
                                        #         views_to_decrement.add(view)
                                        # for view in views_to_decrement:
                                        #     view_scores[view] -= 1

                                    # pprint.pprint(sort_view_by_scores(view_scores))

                                    # print(Colors.CREDBG2 + "Views in top " + str(top_percentile) + " percentile" + Colors.CEND)
                                    # top_views = get_sorted_views_in_top_percentile(view_scores, top_percentile)
                                    # pprint.pprint(top_views)

                                    if mode == Mode.optimal or mode == Mode.random:
                                        rank = get_view_rank_with_ties(view_scores, ground_truth_path)
                                        if rank != None:
                                            ground_truth_rank[run][num_interactions] = rank
                                            # ground_truth_rank_per_run.append(rank)
                                        else:
                                            print("ERROR!!! Did not find " + ground_truth_path + " in view rank")
                                            exit()

                                    num_interactions += 1

                                print(Colors.CREDBG2 + "Final Views" + Colors.CEND)
                                sorted_views = sort_view_by_scores(view_scores)
                                pprint.pprint(sorted_views)

                                if mode == Mode.optimal or mode == Mode.random:
                                    rank = get_view_rank_with_ties(view_scores, ground_truth_path)
                                    if rank != None:
                                        # pprint.pprint(sort_view_by_scores(view_scores))
                                        print("Ground truth view " + ground_truth_path + " is top-" + str(rank))
                                        print("Number of interactions: ", num_interactions)
                                        print(
                                            Colors.CBOLD + "--------------------------------------------------------------------------" +
                                            Colors.CEND)
                                    # ground_truth_rank.append(ground_truth_rank_per_run)

                                    # if len(ground_truth_rank_per_run) > cur_max_interactions:
                                    #     cur_max_interactions = len(ground_truth_rank_per_run)

                                    times[run] = time.time() - start_time_run

                            ground_truth_rank_np = np.array(ground_truth_rank)

                            # result_by_top_percentile.append(ground_truth_rank)
                            # time_by_top_percentile.append(times)

                            # result_by_top_percentile_new = []
                            # for ground_truth_rank in result_by_top_percentile:
                            #     ground_truth_rank_new = []
                            #     for ground_truth_rank_per_run in ground_truth_rank:
                            #         ground_truth_rank_per_run_new = ground_truth_rank_per_run
                            #         if len(ground_truth_rank_per_run) < cur_max_interactions:
                            #             ground_truth_rank_per_run_new += [np.nan] * (
                            #                         cur_max_interactions - len(ground_truth_rank_per_run))
                            #         ground_truth_rank_new.append(ground_truth_rank_per_run_new)
                            #     result_by_top_percentile_new.append(ground_truth_rank_new)

                            result_np_file_name = "result" + "_" + str(
                                fact_bank_fraction) + "_" + initialize_score + "_" + str(sample_size)
                            time_np_file_name = "time" + "_" + str(
                                fact_bank_fraction) + "_" + initialize_score + "_" + str(sample_size)
                            # if initialize_score == "zero":
                            #     result_np_file_name += "_zero"
                            #     time_np_file_name += "_zero"
                            # elif initialize_score == "s4":
                            #     result_np_file_name += "_s4"
                            #     time_np_file_name += "_s4"

                            # result_by_top_percentile_np = np.array(result_by_top_percentile_new)
                            np.save(result_dir + result_np_file_name, ground_truth_rank_np)

                            # time_by_top_percentile_np = np.array(time_by_top_percentile)
                            np.save(result_dir + time_np_file_name, times)