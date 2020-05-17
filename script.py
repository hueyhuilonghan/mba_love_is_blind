#!/usr/bin/env python
# coding: utf-8

"""
Written for MBA Love is Blind. Script to generate dating matching.

May 16 Update:
1. Fix bug in output list - showing interest.
2. Add .edu email as emailee.
3. Output Master match list using anonymous email. Separate master match list for the new batch. Include match both directions.
4. Two MIN_MATCH thresholds, one for heterosexual group the other for homosexual group.
"""

from random import randrange, choice
import pandas as pd

__author__ = "Huey Huilong Han"
__date__ = "Last Update: May 16, 2020."

###### load data and basic cleaning #####
# read in data
df = pd.read_csv("raw.csv")

# basic cleaning - drop rows and columns with all nans
df = df.dropna(how='all', axis=0)
df = df.dropna(how='all', axis=1)

# rename columns
df.columns = ["personal_email", "anon_email", "gender", "interested_gender", "business_school", "year", "target_city", "interest", "age"]

# drop duplicates - some people enter the form twice
df = df.drop_duplicates(subset='anon_email', keep="last")



###### wrangle locations #####
# TODO: currently manually wrangling locations
# need to improve Google Form to automate this
# load city coordinates
city_coordinates = pd.read_csv("uscities_coordinates/uscities.csv")
city_coordinates = city_coordinates[city_coordinates.population > 300000]

unfound_cities = []
for x in df.target_city.unique():
    if x not in city_coordinates.city.to_list() and x != "Undecided" and x != "Location does not matter":
        unfound_cities.append(x)

df.target_city.replace({"San Francisco / Bay Area": "San Francisco", "Philly": "Philadelphia",
                        "Atlanta, DC, Houston": "Atlanta", "New York or San Francisco": "New York",
                        "Phoenix / Scottsdale": "Phoenix", "Colorado": "Denver", "Washington DC": "Washington",
                        "Washington, DC": "Washington",
                        "London": "New York", "Toronto": "New York", "China": "New York", "Tokyo": "New York",
                        "Sydney, Australia": "New York", "Dallas ": "Dallas"}, inplace=True)

unfound_cities = []
for x in df.target_city.unique():
    if x not in city_coordinates.city.to_list() and x != "Undecided" and x != "Location does not matter":
        unfound_cities.append(x)
assert len(unfound_cities) == 0, "Some locations without corresponding locations still exist!"



### clustering based on locations
# define hub city
# TODO: in the future, automate hub selection
# HUBS = {"New York": None, "San Francisco": None, "Chicago": None} # using these locations to approximate east, west and central
HUBS = {"New York": None, "San Francisco": None,
        "Chicago": None, "Los Angeles": None,
        "Seattle": None, "Boston": None}



# get coordinates
for k in HUBS:
    tmp = city_coordinates[city_coordinates.city == k]
    HUBS[k] = (tmp.lat.values[0], tmp.lng.values[0])

# clustering cities into hub cities
clustering = {}
for x in df.target_city.unique():
    if x in HUBS or x == "Undecided" or x == "Location does not matter":
        continue
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
        clustering[x] = min_city

# clustering
df.target_city.replace(clustering, inplace=True)

# randomly assign "undecided" and "location does not matter" to hub
# TODO: need to discuss this with Anna
for index, row in df[(df.target_city == "Undecided") | (df.target_city == "Location does not matter")].iterrows():
    rand_hub = choice(list(HUBS.keys()))
    df.loc[index, 'target_city'] = rand_hub

# create clusering groups
location_groups = {}
for l in df.target_city.unique():
    location_groups[l] = df[df.target_city == l]

# check if size matches original dataframe
assert sum([location_groups[x].shape[0] for x in location_groups]) == df.shape[0], "The sum of location subgroups does not match the original data!"


###### divide into gender-based groups #####
# define groups based on interested and interested_gender group
gender_loc_groups = {}

# iterate through locations
for l in location_groups:
    # get dataframe
    tmp = location_groups[l]
    
    # get heterosexual group
    hetero = tmp[((tmp.gender == "Male") & (tmp.interested_gender == "Female")) | ((tmp.gender == "Female") & (tmp.interested_gender == "Male"))]    
    key = l + "_heterosexual"
    gender_loc_groups[key] = hetero
    
    # get male-male group
    male_male = tmp[(tmp.gender == "Male") & (tmp.interested_gender == "Male")]
    key = l + "_male-male"
    gender_loc_groups[key] = male_male
    
    # get female-female group
    female_female = tmp[(tmp.gender == "Female") & (tmp.interested_gender == "Female")]
    key = l + "_female-female"
    gender_loc_groups[key] = female_female

    # get both group
    ### TODO: figure out where to put "both" in the above category
    both = tmp[tmp.interested_gender == "Both"]
    key = l + "_both"
    gender_loc_groups[key] = both

# check if size matches original dataframe
assert sum([gender_loc_groups[x].shape[0] for x in gender_loc_groups]) == df.shape[0], "The sum of gender subgroups does not match the original data!"


###### certain groups are too small, if so, merge to another group #####

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

# check if size matches original dataframe
assert sum([gender_loc_groups[x].shape[0] for x in gender_loc_groups]) == df.shape[0], "The sum of gender subgroups does not match the original data!"

# assign both to local heterosexual and corresponding gender group
# e.g. New York male who clicked "both" would be assigned to New York hetero and New York male-male
# New York female who clicked "both" would be assigned to New York hetero and New York female-female
# TODO: discuss this with Anna
for x in list(gender_loc_groups):
    if x.split("_")[1] == "both":
        # get dataframe
        tmp = gender_loc_groups[x]
        
        # extract location
        location = x.split("_")[0]
        
        # add to heterosexual group of that location
        new_x = location + "_heterosexual"
        gender_loc_groups[new_x] = pd.concat([gender_loc_groups[new_x], tmp])
        
        for index, row in tmp.iterrows():
            if row.gender == "Male": # if male, add to male-male group of that location
                new_x = location + "_male-male"
                if new_x in gender_loc_groups.keys():
                    gender_loc_groups[new_x] = pd.concat([gender_loc_groups[new_x], tmp])
                else: # if that location does not exist, add to "Other_male-male group"
                    new_x = location + "Other_male-male"
                    gender_loc_groups[new_x] = pd.concat([gender_loc_groups[new_x], tmp])
            
            elif row.gender == "Female": # if female, add to female-female group
                new_x = "All_female-female"
                gender_loc_groups[new_x] = pd.concat([gender_loc_groups[new_x], tmp])
            else:
                raise ValueError("Gender not recognized!")
        
        # delete this group from the dictionary
        del gender_loc_groups[x]


###### generate matching for each location-gender based group #####

# load previous match
prev_match = pd.read_csv("master_match_list.csv")

# basic cleaning - drop rows and columns with all nans
prev_match = prev_match.dropna(how='all', axis=0)
prev_match = prev_match.dropna(how='all', axis=1)

# define min number of matches for every person
HETERO_MIN_MATCH = 2 # NOTE: this is a parameter defined by user
HOMO_MIN_MATCH = 3 # NOTE: this is a parameter defined by user


# initialize matched_group
matched_group = {}

# iterate over gender_loc_groups
for g in gender_loc_groups:
    if g.split("_")[1] == "heterosexual":
        min_match = HETERO_MIN_MATCH
    else:
        min_match = HOMO_MIN_MATCH
    
    # get dataframe
    tmp = gender_loc_groups[g]
        
    # process heterosexual
    # heterosexual group needs to be processed different from other groups
    # since male must match female (and vice versa), which is not the
    # case for other groups
    if g.split("_")[1] == "heterosexual":
        
        # get people
        males = tmp[tmp.gender == "Male"].anon_email.to_list()
        females = tmp[tmp.gender == "Female"].anon_email.to_list()
        
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
        people = tmp.anon_email.to_list()
        
        # generate adjacency matrix
        mat = pd.DataFrame(index=people, columns=people)
        n_row = mat.shape[0]
        n_col = mat.shape[1]
        
    ##### generate solution #####
    
    # randomly shuffle the data
    mat = mat.sample(frac=1)

    # generate col num range to iterate over
    tmp_index = list(range(mat.shape[1])) * (100 * min_match) # debug
    
    # iterate on rows
    for index, row in mat.iterrows():
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
            
            # pass if it's non-heterosexual and the other person has too many matches
            if g.split("_")[1] != "heterosexual":
                if mat[row.index[i]].sum() > min_match:
                    continue

            # if all conditions pass, add matching to adjacency matrix
            mat.loc[index, row.index[i]] = 1
            if g.split("_")[1] != "heterosexual":
                mat.loc[row.index[i], index] = 1

            # remove index from tmp_index
            tmp_index.remove(i)
            
    # add to matched group
    matched_group[g] = mat

    
###### generate output dataframe for emailing #####

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
output_df.index = output_df.index.map(lambda x: emailee_replacement[x])

# construct concat string
tmp["concat_info"] = tmp["anon_email"] + " - " + tmp["gender"] + " - " + tmp["target_city"] + " - " + tmp["interest"]
tmp.set_index("anon_email", inplace=True)
tmp = tmp["concat_info"]
tmp = tmp.transpose().to_dict()

# replace values
output_df.replace(tmp, inplace=True)

###### writing to disk #####
output_df.to_csv("output.csv")