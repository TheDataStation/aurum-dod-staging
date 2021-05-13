from presentation_utils import *
from DoD import view_4c_analysis_baseline as v4c
from DoD import material_view_analysis as mva
from tqdm import tqdm
import random
from enum import Enum
import glob
import pandas as pd
import pprint
import numpy as np

from DoD.colors import Colors

import server_config as config


class Mode(Enum):
    manual = 1,
    random = 2,
    optimal = 3


if __name__ == '__main__':

    #################################CONFIG#####################################
    dir_path = "./building/"
    # top-k views
    top_k = 10
    # epsilon-greedy
    epsilon = 0.1
    # max size of candidate (composite) key
    candidate_key_size = 2
    # sample size of contradictory and complementary rows to present
    sample_size = 5

    mode = Mode.optimal

    max_num_interactions = 1000

    num_runs = 100
    ############################################################################

    pd.set_option('display.max_columns', None)
    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_colwidth', None)
    pd.set_option('display.width', None)  # or 199

    msg_vspec = """
                    ######################################################################################################################
                    #                                              View Presentation                                                     #
                    #                    Goal: Help users find their preferred view among all generated views                            #                 
                    # 1. Run 4C algorithm that classifies the views into 4 categories:                                                   #
                    #    Compatible, Contained, Contradictory, Complementary                                                             #
                    # 2. Remove duplicates in compatible views and keep the view with the largest cardinality in contained views         #
                    # 3. Users choose the candidate key and its respective contradictory and complementary rows                          #
                    # 4. Exploitation vs exploration: exploit the knowledge based on user's previous selections                          #
                    #    and explore other options occasionally                                                                          #
                    # 5. Rank the views based on user's preference by keeping an inverted index from each row to the views containing it #                                                             #
                    ######################################################################################################################
                  """
    print(msg_vspec)

    # Run 4C
    print(Colors.CBOLD + "--------------------------------------------------------------------------" + Colors.CEND)
    print("Running 4C...")

    compatible_groups, contained_groups, complementary_groups, contradictory_groups, all_pair_contr_compl = \
        v4c.main(dir_path, candidate_key_size)

    # print(compatible_groups)
    # print(contained_groups)

    print()
    print(Colors.CBOLD + "--------------------------------------------------------------------------" + Colors.CEND)

    view_files = glob.glob(dir_path + "/view_*")
    print("Number of views: ", len(view_files))

    view_files = prune_compatible_views(view_files, compatible_groups)
    print("After pruning compatible views: ", len(view_files))

    view_files = prune_contained_views(view_files, contained_groups)
    print("After pruning contained views: ", len(view_files))

    print(Colors.CBOLD + "--------------------------------------------------------------------------" + Colors.CEND)
    print("Processing complementary and contradictory views...")

    contr_or_compl_view_pairs, non_contr_or_compl_views, row_to_path_dict = preprocess(view_files, all_pair_contr_compl,
                                                                                       sample_size)


    def print_option(option_num, df):
        print(Colors.CGREENBG2 + "Option " + str(option_num) + Colors.CEND)
        print(df)


    ground_truth_rank = np.empty((num_runs, len(contr_or_compl_view_pairs.keys()) + len(non_contr_or_compl_views)),
                                 dtype=int)

    sum_num_interactions = 0

    ground_truth_path = "./building/view_49"
    fact_bank_df = None
    optimal_candidate_key = ["Building Room", "Building Name"]
    if mode == Mode.optimal:
        print("Ground truth view: " + ground_truth_path)
        fact_bank_df = pd.read_csv(ground_truth_path, encoding='latin1', thousands=',')
        fact_bank_df = mva.curate_view(fact_bank_df)
        fact_bank_df = v4c.normalize(fact_bank_df)

    for run in range(num_runs):

        print("Run " + str(run))

        # ground_truth_path = random.choice(list(view_files))
        # fact_bank_df = None
        # optimal_candidate_key = ["Building Room", "Building Name"]
        # if mode == Mode.optimal:
        #     print("Ground truth view: " + ground_truth_path)
        #     fact_bank_df = pd.read_csv(ground_truth_path, encoding='latin1', thousands=',')
        #     fact_bank_df = mva.curate_view(fact_bank_df)
        #     fact_bank_df = v4c.normalize(fact_bank_df)

        # Initialize ranking model
        key_rank = {}
        row_rank = row_to_path_dict.copy()
        for row, path in row_rank.items():
            row_rank[row] = 0
        view_rank = {}
        for path in view_files:
            view_rank[path] = 0

        paths = list(contr_or_compl_view_pairs.keys())
        random.shuffle(paths)

        num_interactions = 0
        loop_count = 0

        non_contr_or_compl_views_copy = non_contr_or_compl_views.copy()

        # for path in paths:
        while num_interactions < max_num_interactions:

            if len(paths) <= 0 and len(non_contr_or_compl_views_copy) <= 0:
                break

            path = None
            single_view = None
            if len(paths) <= 0:
                single_view = non_contr_or_compl_views_copy.pop()
            elif len(non_contr_or_compl_views_copy) <= 0:
                path = paths.pop()
            else:
                p = random.random()
                if p < 0.5:
                    path = paths.pop()
                else:
                    single_view = non_contr_or_compl_views_copy.pop()

            print(
                Colors.CBOLD + "--------------------------------------------------------------------------" +
                Colors.CEND)

            count = 0
            option_dict = {}

            if single_view != None:
                # present the single view
                count += 1
                path, df = single_view
                sample_df = df
                if len(df) > sample_size:
                    sample_df = df.sample(n=sample_size)
                print(Colors.CBLUEBG2 + path + Colors.CEND)
                print_option(count, sample_df)
                option_dict[count] = (None, [sample_df], path)
            else:
                path1 = path[0]
                path2 = path[1]

                print(Colors.CBLUEBG2 + path1 + " - " + path2 + Colors.CEND)

                candidate_key_dict = contr_or_compl_view_pairs[path]

                for candidate_key_tuple, contr_or_compl_df_list in candidate_key_dict.items():

                    if candidate_key_tuple not in key_rank.keys():
                        key_rank[candidate_key_tuple] = 0

                    print("Candidate key " + Colors.CREDBG2 + str(candidate_key_tuple) + Colors.CEND + " is "
                          + Colors.CVIOLETBG2 + contr_or_compl_df_list[0] + Colors.CEND)

                    if contr_or_compl_df_list[0] == "contradictory":
                        # print(contr_or_compl_df_list)
                        row1_dfs = []
                        row2_dfs = []

                        skip_this_pair = False
                        preferred_view_set = set()

                        for row_tuple in contr_or_compl_df_list[1:]:
                            row1_dfs.append(row_tuple[0])
                            row2_dfs.append(row_tuple[1])

                        # concatenate all contradictory rows in both side
                        if len(row1_dfs) > 0 and len(row2_dfs) > 0:
                            contradictory_rows1 = pd.concat(row1_dfs)
                            count += 1
                            print_option(count, contradictory_rows1)
                            option_dict[count] = (candidate_key_tuple, row1_dfs, path1)

                            contradictory_rows2 = pd.concat(row2_dfs)
                            count += 1
                            print_option(count, contradictory_rows2)
                            option_dict[count] = (candidate_key_tuple, row2_dfs, path2)

                    if contr_or_compl_df_list[0] == "complementary":
                        # TODO: epsilon greedy for complementary rows?
                        #  But they are not really "choose one over the other" relationship

                        # concatenate all complementary (non-intersecting) rows in both side
                        complementary_df_tuple = contr_or_compl_df_list[1]

                        if len(complementary_df_tuple[0]) > 0:
                            count += 1
                            complementary_part1 = pd.concat(complementary_df_tuple[0])
                            print_option(count, complementary_part1)
                            option_dict[count] = (candidate_key_tuple, complementary_df_tuple[0], path1)
                        if len(complementary_df_tuple[1]) > 0:
                            count += 1
                            complementary_part2 = pd.concat(complementary_df_tuple[1])
                            print_option(count, complementary_part2)
                            option_dict[count] = (candidate_key_tuple, complementary_df_tuple[1], path2)

            if len(option_dict) > 0:

                num_interactions += 1

                option_picked = 0

                if mode == Mode.optimal:
                    max_intersection_with_fact_back = 0
                    for option, values in option_dict.items():
                        candidate_key = values[0]
                        # if set(candidate_key) == set(optimal_candidate_key):
                        row_dfs = values[1]
                        concat_row_df = pd.concat(row_dfs)
                        # because for singleton views I choose to not drop na, so I have to do it here in order to
                        # compare
                        concat_row_df = mva.curate_view(concat_row_df)
                        concat_row_df = v4c.normalize(concat_row_df)

                        column_intersections = concat_row_df.columns.intersection(fact_bank_df.columns)
                        if len(column_intersections) > 0:
                            # default to intersection
                            intersection = pd.merge(left=concat_row_df[list(column_intersections)],
                                                    right=fact_bank_df[list(column_intersections)],
                                                    on=None)
                            intersection = intersection.drop_duplicates()

                            if intersection.size > max_intersection_with_fact_back:
                                # Always selection the option that's more consistent with the fact bank
                                # if there's no intersection, then skip this option (select 0)
                                option_picked = option
                                max_intersection_with_fact_back = intersection.size
                                # print(str(max_intersection_with_fact_back) + " " + str(option_picked))
                    print(Colors.CGREYBG + "Select option (or 0 if no preferred option): " + Colors.CEND)
                    print("Optimal option = " + str(option_picked))

                elif mode == Mode.random:
                    option_picked = random.choice(list(option_dict.keys()))
                    print(Colors.CGREYBG + "Select option (or 0 if no preferred option): " + Colors.CEND)
                    print("Random option = " + str(option_picked))

                else:
                    option_picked = input(
                        Colors.CGREYBG + "Select option (or 0 if no preferred option): " + Colors.CEND)

                    if option_picked == "":
                        break

                    while not (option_picked.isdigit() and
                               (int(option_picked) in option_dict.keys() or int(option_picked) == 0)):
                        option_picked = input(
                            Colors.CGREYBG + "Select option (or 0 if no preferred option): " + Colors.CEND)

                    option_picked = int(option_picked)

                if option_picked != 0:
                    candidate_key_picked = option_dict[option_picked][0]
                    if candidate_key_picked != None:
                        key_rank[candidate_key_picked] += 1

                    # TODO： Add score for any view containing the contradictory or complementary row selected
                    # views_to_add_score = set()
                    rows_picked = option_dict[option_picked][1]
                    for row_df in rows_picked:
                        row_strs = row_df_to_string(row_df)

                        for row_str in row_strs:
                            if row_str in row_to_path_dict.keys():
                                paths_containing_row = row_to_path_dict[row_str]
                                for path in paths_containing_row:
                                    # views_to_add_score.add(path)
                                    view_rank[path] += 1

                            if row_str in row_rank.keys():
                                row_rank[row_str] += 1

                    # for path in views_to_add_score:
                    #     view_rank[path] += 1

            print(Colors.CBEIGEBG + "View rank" + Colors.CEND)
            sorted_view_rank = sort_view_by_scores(view_rank)
            pprint.pprint(sorted_view_rank)

            if mode == Mode.optimal or mode == Mode.random:
                # sorted_view_rank = sort_view_by_scores(view_rank)
                rank = get_view_rank_with_ties(view_rank, ground_truth_path)
                # print("rank = " + str(rank))
                if rank != None:
                    ground_truth_rank[run][loop_count] = rank
                else:
                    print("ERROR!!! Did not find " + ground_truth_path + " in view rank")
                    exit()

            loop_count += 1

        print(Colors.CBOLD + "--------------------------------------------------------------------------" + Colors.CEND)
        # print(Colors.CBEIGEBG + "Key rank" + Colors.CEND)
        # pprint.pprint(key_rank)
        # print(Colors.CBEIGEBG + "Row rank" + Colors.CEND)
        # pprint.pprint(row_rank)
        print(Colors.CREDBG2 + "Final Top-" + str(top_k) + " views" + Colors.CEND)
        sorted_view_rank = sort_view_by_scores(view_rank)
        pprint.pprint(sorted_view_rank[:top_k])
        print("Number of interactions = " + str(num_interactions))
        sum_num_interactions += num_interactions

        if mode == Mode.optimal or mode == Mode.random:
            rank = get_view_rank_with_ties(view_rank, ground_truth_path)
            if rank != None:
                print("Ground truth view " + ground_truth_path + " is top-" + str(rank))
                print(
                    Colors.CBOLD + "--------------------------------------------------------------------------" +
                    Colors.CEND)  # for i in range(len(sorted_view_rank)):
            #     view, score = sorted_view_rank[i]
            #     if ground_truth_path == view:
            #         print("Ground truth view is top-" + str(i+1))

    # avg_ground_truth_rank = np.mean(ground_truth_rank, axis=0)

    if mode == Mode.optimal or mode == Mode.random:
        print("Average number of interactions = " + str(sum_num_interactions / num_runs))

        import matplotlib.pyplot as plt

        plt.rcParams['figure.figsize'] = [12, 8]
        plt.rcParams['figure.dpi'] = 200

        # x_axis = np.linspace(1, max_num_interactions, num=max_num_interactions)
        # print(ground_truth_rank)
        # print(ground_truth_rank.shape)
        # fig, ax = plt.subplots()

        plt.boxplot(ground_truth_rank[:, ::2])
        if mode == Mode.optimal:
            plt.title("No exploration/exploitation, optimal mode")
        elif mode == Mode.random:
            plt.title("No exploration/exploitation, random mode")
        locs, labels = plt.xticks()
        # print(locs)
        # print(labels)
        # ax.set_xticks()
        plt.xticks(ticks=locs, labels=np.arange(1, ground_truth_rank.shape[1] + 1, step=2))
        plt.xlabel("Interaction num")
        plt.ylabel("Rank")
        plt.show()