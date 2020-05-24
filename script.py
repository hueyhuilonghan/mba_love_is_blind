#!/usr/bin/env python
# coding: utf-8

"""
Written for MBA Love is Blind. Script to generate dating matching.

May 23 Update:
1. Added anonymous email in output
2. Handled outputting apostrophe
3. Randomly assign bisexual to a gender group instead of to both
4. Handling people that put multiple locations as Target City
"""

from random import randrange, choice
from math import ceil

import pandas as pd

__author__ = "Huey Huilong Han"
__date__ = "May 23, 2020."


###### define parameters for the script ######
HETERO_MIN_MATCH = 2
HOMO_MIN_MATCH = 3
MAX_MATCH = 5
LOC_REPLACEMENT = {"San Francisco / Bay Area": "San Francisco", "Washington DC": "Washington",
                "London": "New York", "Toronto": "New York", "Florida": "Miami", "Southeast": "Charlotte",
                "East Coast": "New York", "Canada": "Chicago", "toronto": "Chicago"}
HUBS = ["New York", "San Francisco", "Chicago", "Los Angeles", "Seattle", "Boston"]

###### load data and basic cleaning ######
# read in data
df = pd.read_csv("raw.csv")

# basic cleaning - drop rows and columns with all nans
df = df.dropna(how='all', axis=0)
df = df.dropna(how='all', axis=1)

# rename columns
df.columns = ["personal_email", "anon_email", "gender", "interested_gender", "business_school", "year", "target_city", "interest", "age"]

# drop duplicates - some people enter the form twice
df = df.drop_duplicates(subset='anon_email', keep="last")

# set anon_email as index
df.set_index("anon_email", inplace=True, drop=False)

###### wrangle locations ######
# TODO: currently manually wrangling locations
# need to improve Google Form to automate this
# load city coordinates
city_coordinates = pd.read_csv("uscities_coordinates/uscities.csv")
city_coordinates = city_coordinates[city_coordinates.population > 300000]

df.target_city = df.target_city.apply(lambda x: [x.strip() for x in x.split(",")])

# replace locations
for index, row in df.iterrows():
    for i, c in enumerate(row["target_city"]):
        if c not in city_coordinates.city.to_list() and c != "Undecided" and c != "Location does not matter":
            row["target_city"][i] = LOC_REPLACEMENT[c]

###### clustering based on locations ######
# define hub city
# TODO: in the future, automate hub selection
HUBS = {location:None for location in HUBS}

# get coordinates
for k in HUBS:
    tmp = city_coordinates[city_coordinates.city == k]
    HUBS[k] = (tmp.lat.values[0], tmp.lng.values[0])

# clustering cities into hub cities
for loc in df.target_city:
    for i, x in enumerate(loc):
        if x == "Undecided" or x == "Location does not matter":
            loc[i] = choice(list(HUBS.keys()))
        else:
            min_dist = 9999
            min_city = None
            tmp_lat = city_coordinates[city_coordinates.city == x].lat.values[0]
            tmp_lng = city_coordinates[city_coordinates.city == x].lng.values[0]
            for hub in HUBS:
                tmp_dist = (abs(tmp_lat - HUBS[hub][0]) + abs(tmp_lng - HUBS[hub][1]))
                if tmp_dist < min_dist:
                    min_dist = tmp_dist
                    min_city = hub
            loc[i] = min_city
    
    if "Undecided" in loc:
        loc.remove("Undecided")
    
    if "Location does not matter" in loc:
        loc.remove("Location does not matter")
    
# dedupe target_city
df.target_city = df.target_city.apply(lambda x: list(set(x)))


# randomly assign bisexual people
# figure out people's minimum match threshold
for index, row in df.iterrows():
    if row["interested_gender"] == "Interested in Both":
        row["interested_gender"] = choice(["Interested in Females", "Interested in Males"])

df["min_match"] = 0
for index, row in df.iterrows():
    if row["gender"] == "Male" and row["interested_gender"] == "Interested in Females":
        df.loc[index, "min_match"] = HETERO_MIN_MATCH
    elif row["gender"] == "Female" and row["interested_gender"] == "Interested in Males":
        df.loc[index, "min_match"] = HETERO_MIN_MATCH
    elif row["gender"] == "Male" and row["interested_gender"] == "Interested in Males":
        df.loc[index, "min_match"] = HOMO_MIN_MATCH
    elif row["gender"] == "Female" and row["interested_gender"] == "Interested in Females":
        df.loc[index, "min_match"] = HOMO_MIN_MATCH

# create clusering groups
location_groups = {}
for l in HUBS.keys():
    location_groups[l] = df[df.target_city.apply(lambda x: l in x)]


###### divide into gender-based groups ######
# define groups based on interested and interested_gender group
gender_loc_groups = {}

# iterate through locations
for l in location_groups:
    # get dataframe
    tmp = location_groups[l]
    
    # get heterosexual group
    hetero = tmp[((tmp.gender == "Male") & (tmp.interested_gender == "Interested in Females")) | ((tmp.gender == "Female") & (tmp.interested_gender == "Interested in Males"))]    
    key = l + "_heterosexual"
    gender_loc_groups[key] = hetero
    
    # get male-male group
    male_male = tmp[(tmp.gender == "Male") & (tmp.interested_gender == "Interested in Males")]
    key = l + "_male-male"
    gender_loc_groups[key] = male_male
    
    # get female-female group
    female_female = tmp[(tmp.gender == "Female") & (tmp.interested_gender == "Interested in Females")]
    key = l + "_female-female"
    gender_loc_groups[key] = female_female


###### certain groups are too small, if so, merge to another group ######

THRESHOLD = 10 # NOTE: this is a parameter to be defined by user

# delete groups with 0 members
for x in list(gender_loc_groups):
    if gender_loc_groups[x].shape[0] == 0:
        del gender_loc_groups[x]

# aggregate female-female since each location group is too small
female_female = None
for x in list(gender_loc_groups):
    if x.split("_")[1] == "female-female":
        if female_female is None:
            female_female = gender_loc_groups[x]
            del gender_loc_groups[x]
        else:
            female_female = pd.concat([female_female, gender_loc_groups[x]])
            del gender_loc_groups[x]
gender_loc_groups["All_female-female"] = female_female

# aggregate small male-male locations group if each location is too small
male_male = None
for x in list(gender_loc_groups):
    if x.split("_")[1] == "male-male":
        if gender_loc_groups[x].shape[0] > THRESHOLD:
            continue
        
        if male_male is None:
            male_male = gender_loc_groups[x]
            del gender_loc_groups[x]
        else:
            male_male = pd.concat([male_male, gender_loc_groups[x]])
            del gender_loc_groups[x]
if male_male is not None:
    gender_loc_groups["Other_male-male"] = male_male

###### generate matching for each location-gender based group ######

# load previous match
prev_match = pd.read_csv("master_match_list.csv")

# basic cleaning - drop rows and columns with all nans
prev_match = prev_match.dropna(how='all', axis=0)
prev_match = prev_match.dropna(how='all', axis=1)


# initialize matched_group
matched_group = {}

# initialize match in original df to keep track of matches
df['match'] = [[] for _ in range(df.shape[0])]

# iterate over gender_loc_groups
for g in gender_loc_groups:
    # get dataframe
    tmp = gender_loc_groups[g]
        
    # process heterosexual
    # heterosexual group needs to be processed different from other groups
    # since male must match female (and vice versa), which is not the
    # case for other groups
    if g.split("_")[1] == "heterosexual":
        
        # get people
        males = list(set(tmp[tmp.gender == "Male"].anon_email.to_list()))
        females = list(set(tmp[tmp.gender == "Female"].anon_email.to_list()))
        
        # calculate male-female ratio to generate dataframe
        # rows are always >= cols
        ratio = float(len(males))/float(len(females))
        if ratio < 1: # more female than male
            mat = pd.DataFrame(index=females, columns=males)
        else: # more males than females
            mat = pd.DataFrame(index=males, columns=females)
        
        # generate matrix
        mat = pd.DataFrame(index=females, columns=males)
        n_row = mat.shape[0]
        n_col = mat.shape[1]        
        
    # process other groups
    else:
        # get people
        people = list(set(tmp.anon_email.to_list()))
        
        # generate adjacency matrix
        mat = pd.DataFrame(index=people, columns=people)
        n_row = mat.shape[0]
        n_col = mat.shape[1]

    ##### generate solution #####
    
    # randomly shuffle the data
    mat = mat.sample(frac=1)

    # generate col num range to iterate over
    tmp_index = list(range(mat.shape[1])) * 1000
    
    # iterate on rows
    for index, row in mat.iterrows():
        # calculate min match for this person
        person = df[df.anon_email == index]
        min_match = ceil((person["min_match"].iloc[0]) / len(person["target_city"].iloc[0]))
        
        # iterate over index list
        for i in tmp_index:

            # if have enough matches break the loop
            if row.sum() >= min_match:
                break

            # pass if if it's the same person
            if index == row.index[i]:
                continue

            # pass if this match exists in previous matches
            p1 = index
            p2 = row.index[i]
            if prev_match[(prev_match.To == p1) & (prev_match.From == p2)].shape[0] != 0:
                continue
            
            # pass if this match exists in this round
            if p2 in df.loc[p1, "match"]:
                continue
            
            # pass if the other person has too many matches
            if len(df.loc[p2, "match"]) > MAX_MATCH-1:
                continue
            
            # break loop if this person has too many matches
            if len(df.loc[p1, "match"]) >= MAX_MATCH:
                break            

            # if all conditions pass, add matching to adjacency matrix and pandas dataframe
            mat.loc[p1, p2] = 1
            if g.split("_")[1] != "heterosexual":
                mat.loc[p2, p1] = 1
            
            df.loc[p1, "match"].append(p2)
            df.loc[p2, "match"].append(p1)

            # remove index from tmp_index
            tmp_index.remove(i)

    # add to matched group
    matched_group[g] = mat

# ###### generate output dataframe for emailing ######

output_df = {}

for g in matched_group:
    for index, row in matched_group[g].iterrows():
        if index not in output_df.keys():
            output_df[index] = set(row.dropna().index.to_list()) # using set to ensure unique values
        else: # else handles bisexual
            output_df[index] = output_df[index].union(set(row.dropna().index.to_list())) # using set to ensure unique values
    
    
    # if heterosexual, add columns as well
    if g.split("_")[1] == "heterosexual":
        for index in matched_group[g].columns:
            column = matched_group[g][index]
            if index not in output_df.keys():
                output_df[index] = set(column.dropna().index.to_list()) # using set to ensure unique values
            else: # else handles bisexual
                output_df[index] = output_df[index].union(set(column.dropna().index.to_list())) # using set to ensure unique values

# construct dataframe
output_df = pd.DataFrame.from_dict(output_df, orient='index')
output_df = output_df.dropna(axis=1, how='all')
columns = ["match_{}".format(i+1) for i in range(len(output_df.columns))]
output_df.columns = columns
output_df.index.set_names("emailee", inplace=True)

# output intermediate list for debugging purposes
output_df.to_csv("debugging_output.csv")


# output master match df
DATE = '2020-05-16'
ROUND = 'Round 8'

master_match_df = {}
master_match_df['To'] = []
master_match_df['From'] = []
master_match_df['Date'] = []
master_match_df['Round'] = []
for index, row in output_df.iterrows():
    match_list = row.dropna().to_list()
    master_match_df['From']+= match_list
    master_match_df['To']+=[index for _ in range(len(match_list))]
    master_match_df['Date'] = DATE
    master_match_df['Round'] = ROUND
pd.DataFrame(master_match_df).to_csv("master_match_new_batch.csv", index=False)


# replace email address with personal info, for emailing purposes
# read in data
tmp = pd.read_csv("raw.csv")
tmp = tmp.dropna(how='all', axis=0)
tmp = tmp.dropna(how='all', axis=1)
tmp.columns = ["personal_email", "anon_email", "gender", "interested_gender", "business_school", "year", "target_city", "interest", "age"]
tmp = tmp.drop_duplicates(subset='anon_email', keep="last")
tmp.fillna("", inplace=True)

# anon email replacement
emailee_replacement = tmp[["anon_email", "personal_email"]].set_index("anon_email")
emailee_replacement = emailee_replacement.to_dict()['personal_email']
output_df["emailee_anon_email"] = output_df.index
cols = output_df.columns.tolist()
cols = cols[-1:] + cols[:-1]
output_df = output_df[cols]
output_df.index = output_df.index.map(lambda x: emailee_replacement[x])

# construct concat string
tmp["concat_info"] = tmp["anon_email"] + " - " + tmp["gender"] + " - " + tmp["target_city"] + " - " + tmp["interest"]
tmp.set_index("anon_email", inplace=True)
tmp = tmp["concat_info"]
tmp = tmp.transpose().to_dict()

# replace values
output_df.iloc[:, 1:].replace(tmp, inplace=True)

# # writing to disk
output_df.to_csv("output.csv", encoding='utf-8-sig')