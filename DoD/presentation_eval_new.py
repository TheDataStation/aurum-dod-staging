import math

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
import matplotlib.pyplot as plt

plt.rcParams['figure.figsize'] = [12, 8]
plt.rcParams['figure.dpi'] = 200

if __name__ == '__main__':

    # root_dir = "/home/cc/experiments_chembl_5_13/"
    root_dir = "./experiments_chembl_5_13/"
    eval_file = open(root_dir + "eval.txt", "w")
    for query in range(5):
        query_dir = root_dir + "chembl_gt" + str(query) + "/"
        for noise in ["zero_noise", "mid_noise", "high_noise"]:
            noise_dir = query_dir + noise + "/"
            sample_dir = noise_dir + "sample0/"
            for pipeline in range(1, 4):

                if pipeline == 1 or pipeline == 2:
                    continue

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

                max_num_interactions = 10

                num_runs = 50

                initialize_scores = ["zero", "s4"]
                fact_bank_fractions = [10, 50, 100]
                # fact_bank_fraction = 1
                #####################################4C#####################################

                # Run 4C
                print(
                    Colors.CBOLD + "--------------------------------------------------------------------------" + Colors.CEND)
                print("Running 4C...")

                original_view_files = glob.glob(dir_path + "/view_*")

                compatible_groups, contained_groups, complementary_groups, contradictory_groups, all_pair_contr_compl = \
                    v4c.eval_main(dir_path, candidate_key_size)

                print()
                print(
                    Colors.CBOLD + "--------------------------------------------------------------------------" + Colors.CEND)

                print("Number of views: ", len(original_view_files))
                eval_file.write(str(len(original_view_files)) + ",")

                view_files = prune_compatible_views(original_view_files, compatible_groups)
                print("After pruning compatible views: ", len(view_files))
                num_views_after_prune_compatible = len(view_files)
                eval_file.write(str(num_views_after_prune_compatible) + ",")

                view_files = prune_contained_views(view_files, contained_groups)
                print("After pruning contained views: ", len(view_files))
                eval_file.write(str(len(view_files)) + ",")

                ############################################################################

                min_union_complementary_views = set()
                max_union_complementary_views = set()
                # union complementary views in each schema group
                for complementary_group, contradictory_group in zip(complementary_groups, contradictory_groups):
                    complementary_view_map = defaultdict(lambda: defaultdict(set))
                    contradictory_view_map = defaultdict(lambda: defaultdict(set))
                    candidate_keys = set()
                    for path1, path2, candidate_key_tuple, _, _ in complementary_group:
                        complementary_view_map[candidate_key_tuple][path1].add(path2)
                        complementary_view_map[candidate_key_tuple][path2].add(path1)
                        candidate_keys.add(candidate_key_tuple)
                    for path1, candidate_key_tuple, key_value_tuples, path2 in contradictory_group:
                        contradictory_view_map[candidate_key_tuple][path1].add(path2)
                        contradictory_view_map[candidate_key_tuple][path2].add(path1)
                        candidate_keys.add(candidate_key_tuple)

                    def can_union(view, candidate_key, current_union):
                        contradictory_view_set = contradictory_view_map[candidate_key][view]
                        return (contradictory_view_set.isdisjoint(current_union) and view in view_files)

                    min_union_per_schema = [None]*10000
                    max_union_per_schema = set()
                    for candidate_key in candidate_keys:
                        union_views_set = set()
                        for view1, complementary_view_set in complementary_view_map[candidate_key].items():
                            if can_union(view1, candidate_key, union_views_set):
                                union_views_set.add(view1)
                            for view2 in complementary_view_set:
                                if can_union(view2, candidate_key, union_views_set):
                                    union_views_set.add(view2)
                        if len(union_views_set) <= len(min_union_per_schema):
                            min_union_per_schema = union_views_set
                            # print("xxxxxxxxxxxxxxminxxxxxxxxxxxxxxxx")
                            # print(candidate_key)
                            # print("xxxxxxxxxxxxxxminxxxxxxxxxxxxxxxxxx")
                        if len(union_views_set) >= len(max_union_per_schema):
                            max_union_per_schema = union_views_set
                            # print("xxxxxxxxxxxxxxmaxxxxxxxxxxxxxxxxx")
                            # print(candidate_key)
                            # print("xxxxxxxxxxxxxxmaxxxxxxxxxxxxxxxxxxx")

                    min_union_complementary_views.update(min_union_per_schema)
                    max_union_complementary_views.update(max_union_per_schema)

                worst_case_has_union = 1
                if len(min_union_complementary_views) <= 1:
                    min_union_complementary_views = set()
                    worst_case_has_union = 0
                best_case_has_union = 1
                if len(max_union_complementary_views) <= 1:
                    max_union_complementary_views = set()
                    best_case_has_union = 0

                min_view_files = view_files - min_union_complementary_views
                max_view_files = view_files - max_union_complementary_views
                print("worst case num views after union complementary views: ", str(len(min_view_files)+worst_case_has_union))
                print("best case num views after union complementary views: ", str(len(max_view_files)+best_case_has_union))
                eval_file.write(str(len(min_view_files)+worst_case_has_union) + ",")
                eval_file.write(str(len(max_view_files)+best_case_has_union) + ",")
                # continue

                ############################################################################

                print(
                    Colors.CBOLD + "--------------------------------------------------------------------------" +
                    Colors.CEND)
                print("Creating signals...")

                worst_case = [len(min_view_files)+worst_case_has_union]
                best_case = [len(max_view_files)+best_case_has_union]
                for i in range(2):

                    num_interactions = 0
                    cur_min_views = min_view_files
                    cur_max_views = max_view_files
                    while num_interactions < max_num_interactions:

                        if i == 0:
                            if len(cur_min_views) == 0:
                                break
                            signals, candidate_keys = create_contradictory_signals_multi_row(cur_min_views, all_pair_contr_compl,
                                                                                             sample_size=5)
                        else:
                            if len(cur_max_views) == 0:
                                break
                            signals, candidate_keys = create_contradictory_signals_multi_row(cur_max_views, all_pair_contr_compl,
                                                                                            sample_size=5)
                        num_interactions += 1

                        best_signal = pick_best_signal_eval(signals)
                        if best_signal is None:
                            break

                        signal_type, signal, best_key = best_signal

                        # present options
                        options = []
                        options_to_print = []
                        headers = []
                        if signal_type == "contradictions" or signal_type == "complements":

                            row1_df, row2_df, views1, views2 = signal

                            print("Key = ", list(best_key))
                            options = [[1, row1_df, views1], [2, row2_df, views2]]
                            options_to_print = [[1, row1_df.to_string(index=False), views1],
                                                [2, row2_df.to_string(index=False), views2]]
                            headers = ["Option", "", "Views"]
                            if signal_type == "contradictions":
                                headers[1] = "Contradictory Row"
                            else:
                                headers[1] = "Complementary Row"
                            print(tabulate(options_to_print, headers, tablefmt="grid"))

                            if len(views1) > len(views2):
                                more_views = views1
                                less_views = views2
                            else:
                                more_views = views2
                                less_views = views1

                            if i == 0:
                                cur_min_views = cur_min_views - less_views
                                worst_case.append(len(cur_min_views)+worst_case_has_union)
                            else:
                                cur_max_views = cur_max_views - more_views
                                best_case.append(len(cur_max_views)+best_case_has_union)

                        elif signal_type == "singletons":
                            view_to_prune = random.choice(signal)[0]
                            if i == 0:
                                cur_min_views = cur_min_views - {view_to_prune}
                                worst_case.append(len(cur_min_views)+worst_case_has_union)
                            else:
                                cur_max_views = cur_max_views - {view_to_prune}
                                best_case.append(len(cur_max_views)+best_case_has_union)

                print("worst case num of views after pruning using contradictory signals: ", worst_case)
                print("best_case after pruning using contradictory signals: ", best_case)
                eval_file.write(str(worst_case) + ",")
                eval_file.write(str(best_case) + "\n")

                x_axis = [i for i in range(len(worst_case))]
                best_case += [np.nan] * (len(x_axis) - len(best_case))
                ax = plt.figure().gca()
                ax.yaxis.get_major_locator().set_params(integer=True)
                ax.plot(x_axis, worst_case, linestyle='-', marker='o', label="worst case")
                ax.plot(x_axis, best_case, linestyle='--', marker='o', label="best case")
                ax.legend()
                ax.set_xticks(x_axis)
                # y_ticks = [i for i in range(min(best_case), max(worst_case) + 1)]
                # plt.yticks(y_ticks)
                # plt.title("Number of views left at each step after pruning using contradictory signals")
                plt.tight_layout()
                plot_fn = root_dir + "q" + str(query+1) + "_" + noise
                plt.savefig(plot_fn)
                plt.close()

    eval_file.close()